"""Tool round-trip: dispatch a native function call and feed the result back.

When Gemini emits a function call, the agent in ``app/agent/agent.py`` hands the
``ToolCallEvent`` here. This module owns the whole round-trip: validate args
against each tool's Pydantic schema, dispatch to the right tool (``retrieve`` or
``graph_search``), catch failures and turn them into a recovery message for the
model, and build the two conversation turns Gemini requires after a function call.
The tools themselves live in ``retrieve.py`` and ``graph_search.py``.
"""

from __future__ import annotations

import asyncio

import logfire
from google.genai import types
from langfuse import observe
from pydantic import ValidationError

from app.schema.agent import ToolCallEvent
from app.tools.graph_search import GraphSearchArgs, graph_search
from app.tools.retrieve import RetrieveArgs, retrieve


@observe(name="tool-dispatch", as_type="span")
def run_tool(
    name: str,
    args: dict,
    api_key: str | None = None,
    book_id: str | None = None,
    *,
    final_top_k: int | None = None,
    fused_top_k: int | None = None,
    passage_max_chars: int | None = None,
) -> str:
    """Dispatch a native function call from the agent.

    ``args`` is validated against the tool's Pydantic schema; an invalid call is
    returned to the model as a recoverable error string instead of raising.
    ``api_key`` is the caller's own key, forwarded to tools that hit Gemini;
    ``book_id`` scopes ``retrieve``/``graph_search`` to the user's selected book.
    The ``*_top_k``/``passage_max_chars`` overrides carry the active model's
    retrieval profile into ``retrieve`` (``None`` = use the global defaults).
    """
    if name == "retrieve":
        try:
            parsed = RetrieveArgs.model_validate(args)
        except ValidationError as e:
            return f"Invalid arguments for 'retrieve' ({e}). Provide a non-empty 'query' string."
        return retrieve(
            parsed.query,
            top_k=final_top_k,
            api_key=api_key,
            book_id=book_id,
            fused_top_k=fused_top_k,
            passage_max_chars=passage_max_chars,
        )

    if name == "graph_search":
        try:
            gargs = GraphSearchArgs.model_validate(args)
        except ValidationError as e:
            return (
                f"Invalid arguments for 'graph_search' ({e}). Provide a non-empty "
                "'query' string and optional 'mode' of 'local' or 'global'."
            )
        return graph_search(
            gargs.query, gargs.mode, api_key=api_key, book_id=book_id
        )

    return (
        f"Unknown tool '{name}'. Available tools are 'retrieve' (passage search) "
        "and 'graph_search' (knowledge-graph search)."
    )


@observe(name="execute_tool_call", as_type="tool")
async def execute_tool_call(
    event: ToolCallEvent,
    *,
    api_key: str | None = None,
    book_id: str | None = None,
    final_top_k: int | None = None,
    fused_top_k: int | None = None,
    passage_max_chars: int | None = None,
) -> tuple[str, list[types.Content]]:
    """Run a tool the model requested; return its result and the history turns.

    Returns ``(result, turns)``: the result string is both surfaced to the
    client (as a ``tool_result`` event) and fed back to the model as the
    function response, so the caller gets it once and uses it twice.

    Owns the full tool round-trip so the agent loop doesn't have to:
      - dispatch via ``run_tool`` off the event loop (it does blocking I/O);
      - catch any failure and turn it into a recovery message for the model
        (what broke + how to recover) instead of crashing the stream;
      - build the two conversation turns Gemini requires after a function call:
        the model's original function-call part (echoed verbatim so the Gemini
        3.x ``thought_signature`` survives) followed by the function response.

    The ``*_top_k``/``passage_max_chars`` overrides are the active model's
    retrieval profile, forwarded to ``retrieve`` (``None`` = global defaults).
    """
    name, args = event.name, event.args
    logfire.info("tool call: {tool} {args}", tool=name, args=args)
    try:
        with logfire.span("tool.execute", tool=name, tool_args=args):
            result = await asyncio.to_thread(
                lambda: run_tool(
                    name,
                    args,
                    api_key,
                    book_id,
                    final_top_k=final_top_k,
                    fused_top_k=fused_top_k,
                    passage_max_chars=passage_max_chars,
                )
            )
    except Exception as exc:  # noqa: BLE001 - surface to the model, don't kill the stream
        logfire.exception("tool {tool} failed", tool=name)
        result = (
            f"The '{name}' tool failed with an error: {exc!r}. This is most "
            "likely a transient backend problem (e.g. the document store or "
            "embedding service was briefly unreachable), not a problem with "
            "your query. Retry the same call once. If it fails again, tell the "
            "user you can't search the documents right now and do NOT invent an "
            "answer."
        )

    turns = [
        types.Content(role="model", parts=[event.part]),
        types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name, response={"result": result}
                    )
                )
            ],
        ),
    ]
    return result, turns
