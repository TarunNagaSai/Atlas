"""Agent tools package.

One module per tool — ``retrieve`` (hybrid passage search over pgvector) and
``graph_search`` (per-book knowledge-graph traversal) — plus ``dispatch``, which
owns the native-function-call round-trip (validate args, run the tool, feed the
result back to Gemini). This ``__init__`` re-exports the public surface so callers
can ``from app.tools import RETRIEVE_TOOL, execute_tool_call`` without caring which
module a symbol lives in.

Note: the bare ``retrieve``/``graph_search`` *functions* are deliberately not
re-exported here — their names would collide with the same-named submodules and
shadow them. Import those from their modules (``app.tools.retrieve``) instead.
"""

from __future__ import annotations

from app.tools.dispatch import execute_tool_call, run_tool
from app.tools.graph_search import GRAPH_SEARCH_TOOL, GraphSearchArgs
from app.tools.retrieve import RETRIEVE_TOOL, RetrieveArgs

__all__ = [
    "RETRIEVE_TOOL",
    "GRAPH_SEARCH_TOOL",
    "RetrieveArgs",
    "GraphSearchArgs",
    "run_tool",
    "execute_tool_call",
]
