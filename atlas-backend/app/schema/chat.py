from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """One prior turn the client replays in client-side storage mode. The whole
    transcript (oldest first, excluding the current prompt) is sent in
    ``ChatRequest.messages`` so the stateless backend can still give the agent
    conversational context. Ignored in DB mode, where the server loads its own
    history from Postgres."""

    role: Literal["user", "assistant"]
    content: str


class Attachment(BaseModel):
    """A file the user attached to a chat message. ``data`` is base64-encoded
    bytes; the server decodes it, enforces the per-file size cap, and turns it
    into a Gemini input part — images/PDF sent natively, Word/Excel as extracted
    text (see ``app.agent.attachments``)."""

    filename: str = "attachment"
    # The file's MIME type (e.g. ``image/png``, ``application/pdf``). Optional —
    # the server falls back to the filename extension when it's absent.
    mime_type: str | None = None
    data: str  # base64-encoded file bytes


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    system: str | None = None
    temperature: float = 0.2
    max_output_tokens: int | None = None
    # Optional client-supplied id so the client can later POST /chat/cancel for
    # this stream. If omitted, the server generates one and echoes it back as
    # the first SSE event.
    session_id: str | None = None
    # Files attached to this message (images, PDF, Word, Excel). Empty for a
    # plain text turn.
    attachments: list[Attachment] = []
    # Prior conversation turns (oldest first, excluding this prompt). Sent only
    # in client-side storage mode so the stateless backend can replay context
    # into the agent. Empty/ignored in DB mode (the server loads its own history).
    messages: list[ChatMessage] = []


class CancelRequest(BaseModel):
    # Optional: the session id is normally supplied via the X-Session-Id header.
    session_id: str | None = None


class ChatSessionSummary(BaseModel):
    """One conversation in the history list."""

    session_id: str
    title: str | None = None  # the first user prompt
    book_id: str | None = None  # the book this conversation is scoped to
    n_turns: int
    started_at: datetime
    last_at: datetime


class ChatTurn(BaseModel):
    """One turn of a conversation: prompt → agent steps → answer."""

    turn_id: str
    prompt: str
    answer: str
    # The coalesced agent step trace (thought / tool_call / tool_result / usage
    # / text), each item the same shape as the matching SSE event.
    steps: list[dict[str, Any]] = []


class ChatConversation(BaseModel):
    session_id: str
    turns: list[ChatTurn]
