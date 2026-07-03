"""The ``retrieve`` tool.

Hybrid (dense + lexical, RRF-fused) search over the ingested financial documents
in pgvector, reranked, returning parent-page passages with citations so the agent
can ground its answer in real figures instead of guessing. The streaming agent in
``app/agent/agent.py`` advertises ``RETRIEVE_TOOL`` to Gemini via native function
calling; ``RetrieveArgs`` validates the model's free-form arguments before dispatch
(see ``app/tools/dispatch.py``).
"""

from __future__ import annotations

import logfire
from google.genai import types
from langfuse import observe
from pydantic import BaseModel, Field

from app.llm.embedding import get_embedder
from app.llm.gemini import get_gemini
from app.rag.rerank import Reranker
from app.rag.store import HybridStore
from app.schema.llm_settings import get_settings

_RETRIEVE_QUERY_DESC = "A focused natural-language search query."


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
    *,
    fused_top_k: int | None = None,
    passage_max_chars: int | None = None,
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
    # Per-run overrides (from the model's retrieval profile) win over the global
    # defaults; ``passage_max_chars`` uses ``is not None`` because 0 (uncapped)
    # is a valid, meaningful override that must not fall through to the default.
    top_k = top_k or s.final_top_k
    fused = fused_top_k or s.fused_top_k
    with logfire.span("tool.retrieve", query=query, top_k=top_k, book_id=book_id):
        store = _get_store()
        gemini = get_gemini(api_key)
        query_vec = get_embedder(api_key).embed_query(query)
        # Cast a wide net (fused_top_k), then let the reranker restore precision.
        candidates = store.hybrid_search(
            query, query_vec, top_k=fused, book_id=book_id
        )
        results = Reranker(s, gemini=gemini).rerank(query, candidates, top_k=top_k)
        logfire.info("retrieve found {n} passage(s)", n=len(results))

    if not results:
        return (
            "No relevant passages were found in the indexed documents for that "
            "query."
        )

    cap = passage_max_chars if passage_max_chars is not None else s.passage_max_chars
    blocks: list[str] = []
    seen: set[str] = set()
    for scored in results:
        # Parent-document retrieval: hand the agent the full page, de-duplicated
        # so the same page isn't repeated when several of its children match.
        if scored.chunk.parent_id in seen:
            continue
        seen.add(scored.chunk.parent_id)
        parent = (scored.chunk.parent_text or "").strip()
        child = scored.chunk.text.strip()
        # Bound the passage: the whole page is great for grounding but gets
        # re-sent on every later hop. Keep the full page only while it fits the
        # cap; past it, fall back to the matched child span (the actually-relevant
        # text) rather than the page's arbitrary head, then hard-truncate as a
        # last-resort guard.
        if parent and (not cap or len(parent) <= cap):
            passage = parent
        else:
            passage = child or parent
            if cap and len(passage) > cap:
                passage = passage[:cap].rstrip()
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
