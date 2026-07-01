"""Agent tools.

The streaming agent in ``app/agent/agent.py`` advertises ``RETRIEVE_TOOL`` to
Gemini (native function calling). When the model emits a function call, the agent
hands the ``ToolCallEvent`` to ``execute_tool_call`` — this module owns the whole
tool round-trip: validate args against a Pydantic schema (``RetrieveArgs``),
dispatch via ``run_tool``, catch failures and turn them into a recovery message
for the model, and build the conversation turns to feed back. The one tool is
``retrieve`` — hybrid (dense + lexical, RRF-fused) search over the ingested
financial documents in pgvector, returning parent-page passages with citations
so the agent can ground its answer in real figures instead of guessing.
"""

from __future__ import annotations

import asyncio

import logfire
from google.genai import types
from langfuse import observe
from pydantic import BaseModel, Field, ValidationError

from app.llm.embedding import get_embedder
from app.llm.gemini import get_gemini
from app.rag.rerank import Reranker
from app.rag.store import HybridStore
from app.schema.agent import ToolCallEvent
from app.schema.llm_settings import get_settings

_RETRIEVE_QUERY_DESC = "A focused natural-language search query."

_GRAPH_QUERY_DESC = "A focused natural-language question for the knowledge graph."
_GRAPH_MODE_DESC = (
    "Search mode. 'local' walks the graph from the entities named in the query "
    "to find specific facts and how things connect; 'global' returns book-wide "
    "thematic summaries for high-level / 'across the whole document' questions."
)


class RetrieveArgs(BaseModel):
    """Validated arguments for the ``retrieve`` tool.

    The model returns free-form ``args`` with native function calling; we parse
    them through this schema before dispatching so a malformed call becomes a
    recoverable message to the model rather than a crash.
    """

    query: str = Field(description=_RETRIEVE_QUERY_DESC, min_length=1)


# Native function-calling declaration handed to Gemini. The agent advertises
# exactly this tool; the parameter contract mirrors ``RetrieveArgs``.
RETRIEVE_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="retrieve",
            description=(
                "Search the indexed financial documents and return the most "
                "relevant passages, each numbered and prefixed with its source "
                "citation for grounding."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING, description=_RETRIEVE_QUERY_DESC
                    )
                },
                required=["query"],
            ),
        )
    ]
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

_store: HybridStore | None = None


def _get_store() -> HybridStore:
    global _store
    if _store is None:
        _store = HybridStore(get_settings())
    return _store


@observe(name="retrieve", as_type="retriever")
def retrieve(
    query: str,
    top_k: int | None = None,
    api_key: str | None = None,
    book_id: str | None = None,
) -> str:
    """Search indexed documents and return relevant passages with citations.

    The query is embedded with the RETRIEVAL_QUERY task type into the same shared
    space as the stored document/page embeddings, so a text question retrieves
    both text chunks and multimodally-embedded PDF pages. ``api_key`` (the
    caller's own key) embeds the query on that key; the pgvector search itself
    needs no key. ``book_id`` (the book the user selected) scopes the search to
    that book's embeddings only; ``None`` searches across every book.

    Retrieval is **wide then narrow**: hybrid search returns ``fused_top_k``
    candidates by proximity, then the reranker rescores them by answer-usefulness
    and keeps the ``final_top_k`` (``top_k``) most useful — high recall first,
    sharp precision last.
    """
    query = query.strip()
    if not query:
        return "retrieve requires a non-empty search query."

    s = get_settings()
    top_k = top_k or s.final_top_k
    with logfire.span("tool.retrieve", query=query, top_k=top_k, book_id=book_id):
        store = _get_store()
        gemini = get_gemini(api_key)
        query_vec = get_embedder(api_key).embed_query(query)
        # Cast a wide net (fused_top_k), then let the reranker restore precision.
        candidates = store.hybrid_search(
            query, query_vec, top_k=s.fused_top_k, book_id=book_id
        )
        results = Reranker(s, gemini=gemini).rerank(query, candidates, top_k=top_k)
        logfire.info("retrieve found {n} passage(s)", n=len(results))

    if not results:
        return (
            "No relevant passages were found in the indexed documents for that "
            "query."
        )

    blocks: list[str] = []
    seen: set[str] = set()
    for scored in results:
        # Parent-document retrieval: hand the agent the full page, de-duplicated
        # so the same page isn't repeated when several of its children match.
        if scored.chunk.parent_id in seen:
            continue
        seen.add(scored.chunk.parent_id)
        passage = (scored.chunk.parent_text or scored.chunk.text).strip()
        if not passage:
            continue
        # Number each source so the agent can cite it with a compact [n] marker
        # after each claim (grounding). The source path stays on the same line, so
        # the [n] -> document mapping is auditable straight from the trace.
        n = len(blocks) + 1
        blocks.append(f"[{n}] Source: {scored.citation}\n{passage}")

    if not blocks:
        return "Matching passages had no extractable text to quote."

    return "\n\n---\n\n".join(blocks)


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


@observe(name="tool-dispatch", as_type="span")
def run_tool(
    name: str, args: dict, api_key: str | None = None, book_id: str | None = None
) -> str:
    """Dispatch a native function call from the agent.

    ``args`` is validated against the tool's Pydantic schema; an invalid call is
    returned to the model as a recoverable error string instead of raising.
    ``api_key`` is the caller's own key, forwarded to tools that hit Gemini;
    ``book_id`` scopes ``retrieve``/``graph_search`` to the user's selected book.
    """
    if name == "retrieve":
        try:
            parsed = RetrieveArgs.model_validate(args)
        except ValidationError as e:
            return f"Invalid arguments for 'retrieve' ({e}). Provide a non-empty 'query' string."
        return retrieve(parsed.query, api_key=api_key, book_id=book_id)

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
    event: ToolCallEvent, *, api_key: str | None = None, book_id: str | None = None
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
    """
    name, args = event.name, event.args
    logfire.info("tool call: {tool} {args}", tool=name, args=args)
    try:
        with logfire.span("tool.execute", tool=name, tool_args=args):
            result = await asyncio.to_thread(run_tool, name, args, api_key, book_id)
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
