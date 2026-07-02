"""Import one client-side (localStorage) chat transcript into the Postgres history.

In ``client`` storage mode the browser owns every transcript: a conversation's
full ``Message[]`` lives in localStorage under ``atlas.chat.<id>``, and the
backend stores nothing. This script moves ONE such transcript into the DB tables
(``chats`` + ``chat_steps``) so it shows up in ``db`` mode — in the ``/chat/sessions``
sidebar and replayable via ``/chat/sessions/{id}`` — exactly like a natively
persisted conversation.

It reverses the frontend's replay mapping (``turnsToMessages`` /
``thinkingFromConversation`` in ``app/page.tsx``): the flat ``Message[]`` is paired
back into turns (one ``user`` + one ``assistant`` under a shared ``turn_id``), and
each assistant message's ``thinking[]`` timeline is written back to ``chat_steps``
with the same payload shape the UI reads on replay (``plan`` / ``thought`` /
``tool_call`` / ``tool_result``), plus a reconstructed ``sources`` step from any
stored citations.

Getting the transcript out of the browser (do this in the app's DevTools console):

    // list your local chats to find the one you want (id + title)
    JSON.parse(localStorage.getItem("atlas.chats.index"))
    // then copy the transcript for that id into a file:
    copy(localStorage.getItem("atlas.chat.<THE_ID>"))

Save that into a .json file. It is a raw ``Message[]`` array; this script also
accepts a ``{ "id", "title", "messages": [...] }`` wrapper.

Prereqs:
  - DATABASE_URL must be set (.env) and point at the same Postgres the app uses.

Usage:
  uv run python scripts/import_local_chat.py chat.json --session-id <THE_ID>
  uv run python scripts/import_local_chat.py chat.json --book-id <BOOK> --dry-run
  uv run python scripts/import_local_chat.py chat.json                 # mints a session id

Flags:
  --session-id ID   Session id to store under (default: the wrapper's "id", else a
                    fresh uuid4). Reuse the local chat id to keep it stable.
  --book-id BID     Scope the conversation to a book (shows under that book's
                    history). Omit for an all-books conversation.
  --force           Import even if a conversation already exists for the session id
                    (appends turns; may duplicate). Default: refuse and exit.
  --dry-run         Parse + map + print what WOULD be written; touch no rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Running a file inside scripts/ puts that dir on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schema.llm_settings import get_settings

# The chat_steps.type CHECK constraint only permits this set. The replay UI reads
# a step's kind from the payload JSON (get_conversation returns payload, not the
# column), so we can keep the true type (e.g. "plan"/"sources") inside the payload
# and just give the constrained column an allowed stand-in.
_ALLOWED_STEP_TYPES = {"thought", "text", "tool_call", "tool_result", "usage"}
_COL_TYPE_FALLBACK = {"plan": "thought", "sources": "text"}


def _col_type(step_type: str) -> str:
    if step_type in _ALLOWED_STEP_TYPES:
        return step_type
    return _COL_TYPE_FALLBACK.get(step_type, "thought")


class Turn:
    """One paired turn ready to write: a user prompt, an assistant answer, and the
    coalesced step payloads (in the exact shape the replay UI reads back)."""

    def __init__(self) -> None:
        self.prompt: str = ""
        self.answer: str = ""
        self.steps: list[dict[str, Any]] = []
        self.prompt_at: datetime | None = None
        self.answer_at: datetime | None = None


def _ts(created_at: Any) -> datetime | None:
    """A stored ``createdAt`` (epoch ms) → aware UTC datetime, or None if absent."""
    if not isinstance(created_at, (int, float)):
        return None
    return datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)


def _steps_from_message(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild an assistant message's persisted step trace from its localStorage
    ``thinking`` timeline (+ ``citations``), matching what ``chat.py`` would have
    written and what ``app/page.tsx`` reads on replay."""
    steps: list[dict[str, Any]] = []
    for entry in msg.get("thinking") or []:
        kind = entry.get("kind")
        if kind in ("plan", "thought"):
            steps.append({"type": kind, "text": entry.get("text", "")})
        elif kind == "tool_call":
            steps.append(
                {
                    "type": "tool_call",
                    "name": entry.get("name", ""),
                    "args": entry.get("args") or {},
                }
            )
        elif kind == "tool_result":
            steps.append(
                {
                    "type": "tool_result",
                    "name": entry.get("name", ""),
                    "result": entry.get("result", ""),
                }
            )

    # Reconstruct the `sources` step the frontend reads for citations. The stored
    # Citation is {id:"cN", source, snippet, page}; the replay path (citationsFromSteps
    # -> toCitation) wants StreamSource {n, citation, cited} and re-parses the source
    # string as "source#page". The snippet isn't recoverable (replay sets it ""),
    # so this restores the citation list, not the snippet text.
    sources = []
    for c in msg.get("citations") or []:
        cid = str(c.get("id") or "")
        n = int("".join(ch for ch in cid if ch.isdigit()) or len(sources) + 1)
        src = c.get("source") or ""
        page = c.get("page")
        citation = f"{src}#{page}" if page not in (None, "") else src
        sources.append({"n": n, "citation": citation, "cited": True})
    if sources:
        steps.append({"type": "sources", "sources": sources})
    return steps


def _pair_into_turns(messages: list[dict[str, Any]]) -> list[Turn]:
    """Fold a flat ``Message[]`` back into user/assistant turns.

    The transcript alternates user → assistant. We open a turn on each user
    message and close it on the following assistant message. A trailing user with
    no answer (rare — ``saveLocalChat`` drops still-``pending`` bubbles) is kept as
    a user-only turn so nothing is silently lost."""
    turns: list[Turn] = []
    cur: Turn | None = None
    for msg in messages:
        if msg.get("pending"):
            continue  # never persist a half-streamed bubble
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "user":
            if cur is not None:
                turns.append(cur)
            cur = Turn()
            cur.prompt = content
            cur.prompt_at = _ts(msg.get("createdAt"))
        elif role == "assistant":
            if cur is None:
                cur = Turn()  # assistant with no preceding user; keep it anyway
            cur.answer = content
            cur.answer_at = _ts(msg.get("createdAt"))
            cur.steps = _steps_from_message(msg)
            turns.append(cur)
            cur = None
    if cur is not None:
        turns.append(cur)
    return turns


def _load_messages(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Read the export file → (messages, wrapper_id). Accepts a raw ``Message[]``
    array or a ``{id, title, messages}`` wrapper."""
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"], data.get("id")
    raise SystemExit(
        "Unrecognized transcript file: expected a Message[] array or a "
        '{ "messages": [...] } object.'
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Import a localStorage chat into Postgres.")
    ap.add_argument("transcript", type=Path, help="Path to the exported chat JSON.")
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--book-id", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = get_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot import.")

    messages, wrapper_id = _load_messages(args.transcript)
    session_id = args.session_id or wrapper_id or uuid4().hex
    turns = _pair_into_turns(messages)
    if not turns:
        raise SystemExit("No user/assistant turns found in the transcript.")

    n_steps = sum(len(t.steps) for t in turns)
    print(
        f"Parsed {len(messages)} message(s) -> {len(turns)} turn(s), {n_steps} step(s).\n"
        f"Target session_id: {session_id}"
        + (f"  book_id: {args.book_id}" if args.book_id else "  (no book scope)")
    )

    if args.dry_run:
        for i, t in enumerate(turns, 1):
            kinds = ", ".join(st["type"] for st in t.steps) or "(no steps)"
            print(f"  turn {i}: prompt {len(t.prompt)}c / answer {len(t.answer)}c / steps: {kinds}")
        print("\n[dry-run] nothing written.")
        return

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(s.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chats WHERE session_id = %s LIMIT 1", (session_id,)
            )
            if cur.fetchone() and not args.force:
                raise SystemExit(
                    f"A conversation already exists for session_id {session_id!r}. "
                    "Use a different --session-id, or pass --force to append."
                )

            for t in turns:
                turn_id = str(uuid4())
                cur.execute(
                    "INSERT INTO chats (session_id, turn_id, role, content, book_id, created_at) "
                    "VALUES (%s, %s, 'user', %s, %s, COALESCE(%s, now()))",
                    (session_id, turn_id, t.prompt, args.book_id, t.prompt_at),
                )
                cur.execute(
                    "INSERT INTO chats (session_id, turn_id, role, content, book_id, created_at) "
                    "VALUES (%s, %s, 'assistant', %s, %s, COALESCE(%s, now())) RETURNING id",
                    (session_id, turn_id, t.answer, args.book_id, t.answer_at),
                )
                assistant_id = cur.fetchone()[0]
                if t.steps:
                    psycopg2.extras.execute_values(
                        cur,
                        "INSERT INTO chat_steps "
                        "(chat_id, session_id, turn_id, seq, type, payload) VALUES %s",
                        [
                            (assistant_id, session_id, turn_id, seq, _col_type(st["type"]), json.dumps(st))
                            for seq, st in enumerate(t.steps)
                        ],
                    )
        conn.commit()
    finally:
        conn.close()

    print(
        f"done — imported {len(turns)} turn(s) / {n_steps} step(s) under session_id "
        f"{session_id}. It will appear in the DB-mode history sidebar."
    )


if __name__ == "__main__":
    main()
