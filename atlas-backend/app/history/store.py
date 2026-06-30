"""Postgres-backed chat history.

Persists the global conversation (not user-scoped) across three tables created
by migration:

  - ``chats``       one row per message (``role`` ∈ {user, assistant}), grouped
                    into conversations by ``session_id`` and into single turns by
                    ``turn_id``.
  - ``chat_steps``  the agent's reason→act trace behind one assistant message:
                    the ordered ``thought`` / ``text`` / ``tool_call`` /
                    ``tool_result`` / ``usage`` events, one row each.

A "turn" spans the user prompt → agent steps → AI final answer; the user row,
the assistant row, and every step row of a turn share one ``turn_id``.

This mirrors :class:`app.rag.store.HybridStore`'s connection handling (lazy
connect with a Supabase-pooler liveness ping). Writes are synchronous psycopg2;
the async route calls :meth:`record_turn` via ``asyncio.to_thread`` and treats
failures as best-effort (a logging miss must never break the user's stream).
"""

from __future__ import annotations

import json
from typing import Any

import logfire

from app.schema.agent import AgentEvent
from app.schema.llm_settings import Settings, get_settings

# Streamed events that arrive as many small chunks; consecutive runs of the same
# kind are coalesced into a single step so the trace is one row per logical step,
# not one per token.
_STREAMED = {"plan", "thought", "text"}


def coalesce_steps(events: list[AgentEvent]) -> list[dict[str, Any]]:
    """Turn the raw agent event stream into ordered step records.

    Consecutive ``thought`` (or ``text``) chunks are merged into one step with
    the concatenated text; discrete events (``tool_call`` / ``tool_result`` /
    ``usage``) each become their own step. ``ToolCallEvent.part`` is already
    ``exclude=True`` so the raw SDK object never lands in the payload.
    """
    steps: list[dict[str, Any]] = []
    buf_type: str | None = None
    buf_text: list[str] = []

    def flush() -> None:
        nonlocal buf_type, buf_text
        if buf_type is not None and buf_text:
            text = "".join(buf_text)
            if text:
                steps.append(
                    {"type": buf_type, "payload": {"type": buf_type, "text": text}}
                )
        buf_type, buf_text = None, []

    for ev in events:
        if ev.type in _STREAMED:
            if buf_type == ev.type:
                buf_text.append(ev.text)  # type: ignore[union-attr]
            else:
                flush()
                buf_type, buf_text = ev.type, [ev.text]  # type: ignore[union-attr]
        else:
            flush()
            steps.append({"type": ev.type, "payload": ev.model_dump()})
    flush()
    return steps


class ChatHistoryStore:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self._conn = None

    @property
    def enabled(self) -> bool:
        return bool(self.s.database_url)

    # ---------------------------------------------------------------- connect
    def _connect(self):
        import psycopg2

        if not self.s.database_url:
            raise RuntimeError("DATABASE_URL is not set; chat history is disabled.")
        # The Supabase pooler silently drops idle sessions; psycopg2 won't flag it
        # via ``.closed`` until a query fails. Ping, and reconnect if dead.
        if self._conn is not None and not self._conn.closed:
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg2.Error:
                try:
                    self._conn.close()
                except psycopg2.Error:
                    pass
                self._conn = None
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.s.database_url)
        return self._conn

    # ------------------------------------------------------------- record
    def record_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        prompt: str,
        answer: str,
        events: list[AgentEvent],
        book_id: str | None = None,
    ) -> None:
        """Persist one full turn: the user prompt, the assistant answer, and the
        coalesced agent step trace — atomically, under a shared ``turn_id``.

        ``book_id`` scopes the conversation to a single ingested book (``None``
        when the chat isn't pinned to one — i.e. retrieval spans all books)."""
        import psycopg2.extras

        steps = coalesce_steps(events)
        with logfire.span(
            "history.record_turn",
            session_id=session_id,
            turn_id=turn_id,
            n_steps=len(steps),
        ):
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chats (session_id, turn_id, role, content, book_id) "
                    "VALUES (%s, %s, 'user', %s, %s)",
                    (session_id, turn_id, prompt, book_id),
                )
                cur.execute(
                    "INSERT INTO chats (session_id, turn_id, role, content, book_id) "
                    "VALUES (%s, %s, 'assistant', %s, %s) RETURNING id",
                    (session_id, turn_id, answer, book_id),
                )
                assistant_id = cur.fetchone()[0]
                if steps:
                    psycopg2.extras.execute_values(
                        cur,
                        "INSERT INTO chat_steps "
                        "(chat_id, session_id, turn_id, seq, type, payload) VALUES %s",
                        [
                            (
                                assistant_id,
                                session_id,
                                turn_id,
                                seq,
                                step["type"],
                                json.dumps(step["payload"]),
                            )
                            for seq, step in enumerate(steps)
                        ],
                    )
            conn.commit()
            logfire.info(
                "recorded turn {turn_id} ({n} steps)", turn_id=turn_id, n=len(steps)
            )


    # -------------------------------------------------------------- read
    def load_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Prior turns of a conversation as plain ``{role, content}`` messages,
        oldest first — the cheap read used to seed the agent's context in DB
        mode. Unlike :meth:`get_conversation` (which also pulls the step trace
        for the replay UI), this touches only ``chats``."""
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM chats WHERE session_id = %s ORDER BY id",
                (session_id,),
            )
            return [{"role": role, "content": content} for role, content in cur.fetchall()]

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        book_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Conversations for the history list, most-recently-active first.

        One row per ``session_id`` with the first user prompt as the title and
        the turn count / time bounds for the preview. When ``book_id`` is given,
        only conversations scoped to that book are returned (the frontend's
        per-book history list)."""
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id,
                       (array_agg(content ORDER BY id)
                          FILTER (WHERE role = 'user'))[1] AS title,
                       max(book_id) AS book_id,
                       count(*) FILTER (WHERE role = 'user') AS n_turns,
                       min(created_at) AS started_at,
                       max(created_at) AS last_at
                FROM chats
                WHERE (%(book_id)s IS NULL OR book_id = %(book_id)s)
                GROUP BY session_id
                ORDER BY last_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {"book_id": book_id, "limit": limit, "offset": offset},
            )
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "book_id": row[2],
                    "n_turns": row[3],
                    "started_at": row[4],
                    "last_at": row[5],
                }
                for row in cur.fetchall()
            ]

    def get_conversation(self, session_id: str) -> list[dict[str, Any]] | None:
        """Every turn of a conversation in order, each with its prompt, answer,
        and full agent step trace. ``None`` if the session has no messages."""
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT turn_id, role, content, id FROM chats "
                "WHERE session_id = %s ORDER BY id",
                (session_id,),
            )
            msg_rows = cur.fetchall()
            if not msg_rows:
                return None
            cur.execute(
                "SELECT turn_id, payload FROM chat_steps "
                "WHERE session_id = %s ORDER BY turn_id, seq",
                (session_id,),
            )
            step_rows = cur.fetchall()

        steps_by_turn: dict[str, list[Any]] = {}
        for turn_id, payload in step_rows:
            steps_by_turn.setdefault(str(turn_id), []).append(
                payload if isinstance(payload, dict) else json.loads(payload)
            )

        # Assemble in first-seen (chronological) order; user row precedes its
        # assistant row since record_turn inserts them in that order.
        turns: dict[str, dict[str, Any]] = {}
        for turn_id, role, content, _id in msg_rows:
            tid = str(turn_id)
            turn = turns.setdefault(
                tid,
                {"turn_id": tid, "prompt": "", "answer": "", "steps": steps_by_turn.get(tid, [])},
            )
            if role == "user":
                turn["prompt"] = content
            else:
                turn["answer"] = content
        return list(turns.values())


_store: ChatHistoryStore | None = None


def get_chat_history() -> ChatHistoryStore:
    global _store
    if _store is None:
        _store = ChatHistoryStore()
    return _store
