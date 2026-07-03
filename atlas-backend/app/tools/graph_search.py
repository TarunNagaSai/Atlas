"""The ``graph_search`` tool.

Search over a per-book knowledge graph of entities and relationships, built at
ingestion and persisted per book. ``mode='local'`` walks the graph from the
entities named in the query; ``mode='global'`` ranks pre-computed community
summaries for whole-book / thematic questions. Complements ``retrieve`` (passage
search). The agent advertises ``GRAPH_SEARCH_TOOL`` to Gemini via native function
calling; ``GraphSearchArgs`` validates the model's arguments before dispatch (see
``app/tools/dispatch.py``).
"""

from __future__ import annotations

import logfire
from google.genai import types
from langfuse import observe
from pydantic import BaseModel, Field

from app.llm.embedding import get_embedder
from app.llm.gemini import get_gemini

_GRAPH_QUERY_DESC = "A focused natural-language question for the knowledge graph."
_GRAPH_MODE_DESC = (
    "Search mode. 'local' walks the graph from the entities named in the query "
    "to find specific facts and how things connect; 'global' returns book-wide "
    "thematic summaries for high-level / 'across the whole document' questions."
)


class GraphSearchArgs(BaseModel):
    """Validated arguments for the ``graph_search`` tool."""

    query: str = Field(description=_GRAPH_QUERY_DESC, min_length=1)
    mode: str = Field(default="local", description=_GRAPH_MODE_DESC)


# Native function-calling declaration for the knowledge-graph search. The agent
# picks ``mode`` per question: 'local' (entity traversal) vs 'global' (themes).
GRAPH_SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="graph_search",
            description=(
                "Search the book's knowledge graph of entities and relationships. "
                "Use mode='local' to trace how specific named entities connect "
                "(e.g. 'which subsidiaries does X own?'); use mode='global' for "
                "high-level themes across the whole book (e.g. 'what are the main "
                "risk factors?'). Complements `retrieve`, which does passage search."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING, description=_GRAPH_QUERY_DESC
                    ),
                    "mode": types.Schema(
                        type=types.Type.STRING,
                        enum=["local", "global"],
                        description=_GRAPH_MODE_DESC,
                    ),
                },
                required=["query"],
            ),
        )
    ]
)


@observe(name="graph_search", as_type="retriever")
def graph_search(
    query: str,
    mode: str = "local",
    api_key: str | None = None,
    book_id: str | None = None,
) -> str:
    """Search the active book's knowledge graph (local traversal or global themes).

    The graph is built at ingestion and persisted per book, so this loads and
    traverses it — it never rebuilds. ``mode='local'`` matches the query's
    entities to nodes and walks a few hops to gather connected facts and backing
    passages; ``mode='global'`` ranks pre-computed community summaries by
    similarity to the query for whole-book / thematic questions. ``api_key`` (the
    caller's key) powers the graph's own Gemini/embedding calls; ``book_id`` picks
    which book's graph to load.
    """
    from app.rag.graph import GraphIndex

    query = query.strip()
    if not query:
        return "graph_search requires a non-empty query."
    if not book_id:
        return (
            "graph_search needs a selected book. Ask the user to pick a book, or "
            "use the `retrieve` tool to search across all books."
        )

    mode = (mode or "local").strip().lower()
    if mode not in {"local", "global"}:
        mode = "local"

    with logfire.span("tool.graph_search", query=query, mode=mode, book_id=book_id):
        idx = GraphIndex.load(
            book_id,
            gemini=get_gemini(api_key),
            embedder=get_embedder(api_key),
        )
        if idx is None:
            return (
                "No knowledge graph exists for the selected book yet. Use the "
                "`retrieve` tool to search its passages instead."
            )
        return idx.global_search(query) if mode == "global" else idx.local_search(query)
