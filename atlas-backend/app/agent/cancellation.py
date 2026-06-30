from __future__ import annotations


class GenerationCancelled(Exception):
    """Raised inside ``run_agent`` when a stream is cooperatively cancelled.

    Carries no message — the route layer catches it to emit a ``cancelled`` SSE
    event rather than treating the stop as a server error.
    """


class CancellationRegistry:
    """In-process shared state bridging ``/chat/stream`` and ``/chat/cancel``.

    The two requests have no direct channel to each other (one streams out, the
    other comes in separately), so they communicate through this registry: a
    stream registers its ``session_id`` on start, ``/chat/cancel`` flips that id
    to cancelled, and the agent loop polls :meth:`is_cancelled` at its gates and
    tears itself (plus the Gemini socket) down.

    **Single-process only.** The state lives in this worker's memory, so a cancel
    must land on the same worker serving the stream. To span multiple workers or
    hosts, swap in a Redis-backed implementation with the same interface — the
    callers don't change.

    All methods are synchronous (no ``await`` inside), so on the asyncio event
    loop they run atomically with respect to other coroutines; no lock needed.
    """

    def __init__(self) -> None:
        self._active: set[str] = set()
        self._cancelled: set[str] = set()

    def register(self, session_id: str) -> None:
        """Mark a stream as running (clearing any stale cancel flag for the id)."""
        self._active.add(session_id)
        self._cancelled.discard(session_id)

    def request_cancel(self, session_id: str) -> bool:
        """Flag a running stream to stop. Returns ``False`` if no such stream is active."""
        if session_id not in self._active:
            return False
        self._cancelled.add(session_id)
        return True

    def is_cancelled(self, session_id: str) -> bool:
        return session_id in self._cancelled

    def release(self, session_id: str) -> None:
        """Drop all state for a finished stream (success, error, or cancel)."""
        self._active.discard(session_id)
        self._cancelled.discard(session_id)


_registry: CancellationRegistry | None = None


def get_cancellation_registry() -> CancellationRegistry:
    global _registry
    if _registry is None:
        _registry = CancellationRegistry()
    return _registry
