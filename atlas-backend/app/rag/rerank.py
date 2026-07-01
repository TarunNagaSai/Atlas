"""LLM reranker — the precision half of retrieve-wide, rerank-narrow.

First-pass retrieval (dense, BM25, RRF-fused) ranks by **proximity**: how close a
passage sits to the query in embedding/term space. Proximity is not the same as
**usefulness** — the top cosine hit is often merely topical, while the passage
that actually contains the answer sits at rank 7 and gets cut by ``final_top_k``.

A **bi-encoder** (the vector index) embeds query and document *separately* then
compares — fast and scalable, so it's the right tool for a wide first pass over
the whole corpus. A **cross-encoder** (a reranker) feeds the query **and** a
candidate into one model *together* so it can read them jointly and judge
relevance directly — far more accurate, but too expensive to run over the corpus.
So we run it only on the handful of candidates the first pass already narrowed to.

There's no hosted Google rerank endpoint, so we use **Gemini as the reranker**:
one structured call shows the query and every candidate and asks for a relevance
score in ``[0, 1]`` per candidate — judged on usefulness for *answering*, not
topical overlap. A single batched call (not one per passage) keeps latency/cost
down. We sort by that score, keep the top ``final_top_k``, and tag provenance
``how="rerank"``. For very high QPS you'd swap in a dedicated cross-encoder; this
function's signature stays the same.
"""

from __future__ import annotations

import logfire
from pydantic import BaseModel, Field

from app.llm.gemini import Gemini, get_gemini
from app.schema.documents import Scored
from app.schema.llm_settings import ModelSettings, Settings, get_settings

# Cap on how much of each candidate the judge reads. Rerank runs on the child
# window that matched (focused and cheap), not the full parent page; this trims
# pathologically long chunks so one outlier can't blow up the prompt.
_MAX_CANDIDATE_CHARS = 1200


# --------------------------------------------------------------- LLM schemas
class _CandidateScore(BaseModel):
    """A relevance judgement for one candidate, keyed by its list index."""

    index: int = Field(description="The candidate's number as shown in the list.")
    score: float = Field(
        description="Relevance in [0,1]: how useful this passage is for answering "
        "the query. 1 = directly answers it; 0 = irrelevant."
    )


class _RerankScores(BaseModel):
    """The judge's scores for every candidate shown."""

    scores: list[_CandidateScore] = Field(default_factory=list)


_RERANK_PROMPT = (
    "You are ranking candidate passages from financial documents by how useful "
    "each is for answering the user's question. Judge **usefulness for answering "
    "the specific question**, not mere topical overlap: a passage that is on-topic "
    "but does not contain the answer scores low; a passage that contains the "
    "figure, fact, or statement the question asks for scores high. Assign every "
    "candidate a relevance score in [0, 1]. Return one score per candidate index.\n\n"
    "QUESTION:\n{query}\n\nCANDIDATES:\n{candidates}"
)


class Reranker:
    """Rerank fused candidates by answer-usefulness via a single Gemini call."""

    def __init__(
        self, settings: Settings | None = None, *, gemini: Gemini | None = None
    ) -> None:
        self.s = settings or get_settings()
        self._gemini = gemini

    @property
    def gemini(self) -> Gemini:
        if self._gemini is None:
            self._gemini = get_gemini()
        return self._gemini

    def rerank(
        self, query: str, candidates: list[Scored], top_k: int | None = None
    ) -> list[Scored]:
        """Reorder ``candidates`` by relevance and keep the top ``top_k``.

        Falls back to the fused order (truncated) whenever reranking can't run or
        the model misbehaves — so a reranker hiccup degrades to first-pass
        retrieval instead of dropping results. Candidates the model omits keep
        their original relative order behind the ones it scored.
        """
        top_k = top_k or self.s.final_top_k
        if not candidates:
            return []
        # Nothing to reorder, or the feature is off: return the fused order as-is.
        if not self.s.rerank_enabled or len(candidates) <= 1:
            return candidates[:top_k]

        with logfire.span(
            "rerank", query=query, n_candidates=len(candidates), top_k=top_k
        ) as span:
            try:
                scores = self._score(query, candidates)
            except Exception:  # noqa: BLE001 - degrade to fused order, never crash retrieval
                logfire.exception("rerank failed; falling back to fused order")
                span.set_attribute("fallback", True)
                return candidates[:top_k]

            # Stable sort by rerank score, descending. Candidates the model
            # didn't score sink below scored ones (-1.0) but keep fused order
            # among themselves — Python's sort is stable, and enumerate order is
            # the fused order.
            order = sorted(
                range(len(candidates)),
                key=lambda i: -scores.get(i, -1.0),
            )
            ranked = [
                Scored(
                    chunk=candidates[i].chunk,
                    score=scores.get(i, candidates[i].score),
                    how="rerank",
                )
                for i in order[:top_k]
            ]
            span.set_attribute("n_scored", len(scores))
            span.set_attribute("n_results", len(ranked))
            return ranked

    def _score(self, query: str, candidates: list[Scored]) -> dict[int, float]:
        """One batched structured call → ``{candidate_index: score}``."""
        listing = "\n\n".join(
            f"[{i}] {(c.chunk.text or c.chunk.parent_text).strip()[:_MAX_CANDIDATE_CHARS]}"
            for i, c in enumerate(candidates)
        )
        result = self.gemini.generate_structured(
            _RERANK_PROMPT.format(query=query, candidates=listing),
            _RerankScores,
            settings=ModelSettings(model=self.s.rerank_model, temperature=0.0),
        )
        # Keep only in-range indices; clamp scores to [0,1] so a stray value
        # can't dominate the ordering.
        return {
            s.index: max(0.0, min(1.0, s.score))
            for s in result.scores
            if 0 <= s.index < len(candidates)
        }
