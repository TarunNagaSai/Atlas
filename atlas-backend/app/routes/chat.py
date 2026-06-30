from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import logfire
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.agent.agent import run_agent
from app.agent.attachments import AttachmentError, build_attachment_parts
from app.agent.cancellation import GenerationCancelled, get_cancellation_registry
from app.history.store import get_chat_history
from langfuse import propagate_attributes

from app.observability.langfuse import get_langfuse_client
from app.schema.agent import AgentEvent, TextEvent, UsageEvent
from app.schema.chat import (
    CancelRequest,
    ChatConversation,
    ChatRequest,
    ChatSessionSummary,
)
from app.schema.llm_settings import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])

# Shown to the user when anything goes wrong server-side. The real exception is
# logged (Logfire) and attached to the Langfuse trace for debugging; the client
# never sees raw error text (model 503s, stack traces, DB errors, etc.).
_USER_FACING_ERROR = (
    "Sorry — I can't process your request right now. Please try again in a moment."
)

# Shown when Gemini rejects the visitor's own API key, so the frontend can prompt
# them to re-enter it (carries a stable ``code`` for that branch).
_INVALID_KEY_ERROR = (
    "Your Gemini API key was rejected. Please check the key and try again."
)

# Shown when Gemini is overloaded (503 UNAVAILABLE — "high demand"). It's
# transient and not the user's fault, so the message says to retry shortly and
# carries a stable ``code`` the frontend can use to offer a one-click retry.
_MODEL_OVERLOADED_ERROR = (
    "The model is currently experiencing high demand. This is usually "
    "temporary — please try again in a moment."
)


def _is_auth_error(exc: Exception) -> bool:
    """True when an exception looks like Gemini rejecting the API key (vs a
    transient/backend failure), so the route can ask the user to re-enter it."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (401, 403):
        return True
    blob = f"{getattr(exc, 'message', '')} {exc}".lower()
    return any(
        s in blob
        for s in ("api key not valid", "api_key_invalid", "permission_denied", "invalid authentication")
    )


def _is_overloaded_error(exc: Exception) -> bool:
    """True when Gemini is temporarily overloaded (503 UNAVAILABLE / "high
    demand"), so the route can tell the user to retry instead of showing the
    generic failure message."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 503:
        return True
    blob = f"{getattr(exc, 'message', '')} {exc}".lower()
    return any(
        s in blob
        for s in ("unavailable", "overloaded", "high demand", "try again later")
    )


@router.post("/stream")
async def stream_chat(
    body: ChatRequest,
    x_session_id: str | None = Header(default=None),
    x_gemini_api_key: str | None = Header(default=None),
    x_book_id: str | None = Header(default=None),
    x_chat_storage: str | None = Header(default=None),
) -> StreamingResponse:
    # BYO-key demo: every chat runs on the visitor's own Gemini key. It is used
    # for this request only and never stored. Require it up front.
    api_key = (x_gemini_api_key or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="A Gemini API key is required. Provide it via the X-Gemini-Api-Key header.",
        )
    # The frontend sends the model directly; fall back to the server default
    # only when it omits one.
    resolved_model = body.model or get_settings().gen_model
    # The selected book (X-Book-Id) scopes retrieval to that book's embeddings;
    # blank/absent means search across all books.
    book_id = (x_book_id or "").strip() or None
    # Decode + validate attachments up front (off the event loop — DOCX/XLSX
    # parsing is blocking) so a bad file is a clean 400 with a stable ``code``,
    # not a mid-stream error. Built once here, reused across every agent hop.
    try:
        attachment_parts = await asyncio.to_thread(
            build_attachment_parts, body.attachments
        )
    except AttachmentError as e:
        raise HTTPException(
            status_code=400, detail={"code": e.code, "message": str(e)}
        )
    # Canonical source is the X-Session-Id header (the client's contract); fall
    # back to the body, then generate one and echo it back as the first event.
    session_id = x_session_id or body.session_id or uuid4().hex
    # One id per request, shared by the user row, the assistant row, and every
    # agent-step row of this turn so the whole turn is queryable as a unit.
    turn_id = str(uuid4())
    registry = get_cancellation_registry()
    history = get_chat_history()
    # Storage mode is a frontend decision, sent per request (no server env flag):
    #   ``db``     — the server persists this turn and loads prior turns from
    #                Postgres to give the agent memory.
    #   ``client`` — the browser owns the transcript and replays it in the request
    #                body; the server persists nothing.
    # Default ``db`` keeps older clients (no header) on the existing behavior.
    mode = (x_chat_storage or "db").strip().lower()
    persist = mode == "db" and history.enabled
    # Prior conversation for the agent: from the DB in ``db`` mode, from the
    # client's replayed messages in ``client`` mode. DB read is blocking psycopg2,
    # so run it off the event loop.
    if body.messages:
        prior = [m.model_dump() for m in body.messages]
    elif persist:
        prior = await asyncio.to_thread(history.load_messages, session_id)
    else:
        prior = []

    async def event_gen() -> AsyncIterator[str]:
        # Register before streaming so a /chat/cancel that races in right after
        # the client reads the session id always finds an active stream.
        registry.register(session_id)
        # Echo the session id first so the client knows what to POST to /chat/cancel.
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        client = get_langfuse_client()
        # One trace per query (this whole query -> tools -> final answer cycle).
        # Seed the trace id from turn_id so it is deterministic: known up front,
        # reproducible, and correlatable with the persisted turn row (same id) —
        # no need to store the trace id separately, it is derivable from turn_id.
        trace_id = client.create_trace_id(seed=turn_id)
        # Surface it to the client so the frontend can deep-link to the trace.
        yield f"data: {json.dumps({'type': 'trace', 'trace_id': trace_id})}\n\n"
        # Stamp the session id on the whole trace (and every child span the agent
        # and tools create) so Langfuse can group a conversation's turns and
        # aggregate by session. Entered before the root observation so it covers
        # the entire trace — propagate_attributes only affects current + future spans.
        with propagate_attributes(session_id=session_id), client.start_as_current_observation(
            trace_context={"trace_id": trace_id},
            name="agent-stream",
            as_type="generation",
            model=resolved_model,
            input=body.prompt,
        ) as gen:
            # Only the answer text feeds the Langfuse output; thoughts, tool
            # calls/results and usage events stream to the client but aren't the
            # generation's "output".
            pieces: list[str] = []
            # Every agent event, kept to persist the turn's full step trace. The
            # answer text is reassembled from ``pieces``.
            collected: list[AgentEvent] = []
            usage_details: dict[str, int] | None = None

            async def _persist() -> None:
                # Best-effort: a history-write failure must never break the
                # stream the user already received. DB I/O is blocking psycopg2,
                # so run it off the event loop. Only DB mode persists — in
                # client-side mode the browser owns the transcript.
                if not persist:
                    return
                try:
                    await asyncio.to_thread(
                        history.record_turn,
                        session_id=session_id,
                        turn_id=turn_id,
                        prompt=body.prompt,
                        answer="".join(pieces),
                        events=collected,
                        book_id=book_id,
                    )
                except Exception as e:  # noqa: BLE001
                    logfire.exception("failed to persist chat turn: {error}", error=str(e))

            try:
                async for event in run_agent(
                    body.prompt,
                    session_id=session_id,
                    api_key=api_key,
                    model=resolved_model,
                    book_id=book_id,
                    attachment_parts=attachment_parts,
                    history=prior,
                ):
                    collected.append(event)
                    if isinstance(event, TextEvent):
                        pieces.append(event.text)
                    elif isinstance(event, UsageEvent) and event.scope == "total":
                        # Thinking tokens are billed as output, so fold them into
                        # ``output`` — this keeps input + output == total in the
                        # Langfuse generation (and its cost math).
                        usage_details = {
                            "input": event.prompt_tokens,
                            "output": event.output_tokens + event.thoughts_tokens,
                            "total": event.total_tokens,
                        }
                    # Each event carries its own ``type``; forward it verbatim.
                    yield f"data: {json.dumps(event.model_dump())}\n\n"
                gen.update(output="".join(pieces), usage_details=usage_details)
                await _persist()
                yield "data: [DONE]\n\n"
            except GenerationCancelled:
                # Cooperative stop via /chat/cancel — a clean end, not an error.
                # run_agent (and aclosing) has already torn the Gemini socket down.
                # The partial turn is still recorded (steps + whatever answered).
                gen.update(output="".join(pieces), status_message="cancelled by user")
                await _persist()
                yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                # Client hung up (e.g. AbortController.abort()). Record it, then
                # re-raise so the task unwinds cleanly and the Gemini socket is
                # torn down via aclosing. Swallowing this would leak the task.
                gen.update(
                    output="".join(pieces),
                    level="WARNING",
                    status_message="client disconnected",
                )
                raise
            except Exception as e:  # noqa: BLE001
                # Log the real error for us; send only a smooth message to the user.
                logfire.exception("chat stream failed: {error}", error=str(e))
                gen.update(
                    output="".join(pieces),
                    level="ERROR",
                    status_message=str(e),
                )
                # A rejected BYO key gets its own coded error so the frontend can
                # re-prompt for the key rather than show a generic retry message.
                if _is_auth_error(e):
                    payload = {
                        "type": "error",
                        "code": "invalid_api_key",
                        "message": _INVALID_KEY_ERROR,
                    }
                # A 503 (model overloaded) is transient — surface a distinct
                # coded message so the frontend can prompt a retry.
                elif _is_overloaded_error(e):
                    payload = {
                        "type": "error",
                        "code": "model_overloaded",
                        "message": _MODEL_OVERLOADED_ERROR,
                    }
                else:
                    payload = {"type": "error", "message": _USER_FACING_ERROR}
                yield f"data: {json.dumps(payload)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                # Drop registry state on every exit (success, cancel, error, disconnect).
                registry.release(session_id)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/cancel")
async def cancel_chat(
    body: CancelRequest | None = None,
    x_session_id: str | None = Header(default=None),
) -> dict[str, str]:
    """Signal an in-flight /chat/stream to stop. The session id comes from the
    X-Session-Id header (matching /chat/stream) or, failing that, the body.

    Returns 404 if no such stream is currently active on this worker (it may have
    already finished, or be served by a different worker — see
    CancellationRegistry's single-process note).
    """
    session_id = x_session_id or (body.session_id if body else None)
    if not session_id:
        raise HTTPException(
            status_code=422,
            detail="Provide a session id via the X-Session-Id header or request body.",
        )
    if not get_cancellation_registry().request_cancel(session_id):
        raise HTTPException(
            status_code=404, detail="No active stream for that session id."
        )
    return {"status": "cancelling", "session_id": session_id}


@router.get("/sessions", response_model=list[ChatSessionSummary])
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_book_id: str | None = Header(default=None),
) -> list[ChatSessionSummary]:
    """The chat history list: one entry per conversation, most recent first.

    Scoped to the selected book (X-Book-Id) when present, so the frontend shows
    only the conversations about the book the user is currently viewing; absent
    means all conversations across every book."""
    book_id = (x_book_id or "").strip() or None
    rows = await asyncio.to_thread(
        get_chat_history().list_sessions, limit=limit, offset=offset, book_id=book_id
    )
    return [ChatSessionSummary(**row) for row in rows]


@router.get("/sessions/{session_id}", response_model=ChatConversation)
async def get_conversation(session_id: str) -> ChatConversation:
    """A full conversation: every turn with its prompt, answer, and step trace."""
    turns = await asyncio.to_thread(
        get_chat_history().get_conversation, session_id
    )
    if turns is None:
        raise HTTPException(status_code=404, detail="No conversation for that session id.")
    return ChatConversation(session_id=session_id, turns=turns)