"""Unit tests for the LLM reranker (app/rag/rerank.py).

The reranker is the precision half of retrieve-wide, rerank-narrow: it rescores
fused candidates by answer-usefulness and keeps the top ``final_top_k``. These
tests stub the single Gemini scoring call so the ordering, truncation, provenance
and — crucially — the graceful-degradation behaviour are exercised without a
model or a database.
"""

from __future__ import annotations

from app.rag.rerank import Reranker, _CandidateScore, _RerankScores
from app.schema.documents import Chunk, Scored
from app.schema.llm_settings import Settings


def _settings(**over) -> Settings:
    s = Settings()
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _cands(n: int) -> list[Scored]:
    """``n`` fused candidates, best-first (fused score descending)."""
    return [
        Scored(
            chunk=Chunk(
                id=str(i), text=f"passage {i}", source="s",
                parent_id=f"p{i}", parent_text=f"passage {i}",
            ),
            score=1.0 / (i + 1),
            how="rrf",
        )
        for i in range(n)
    ]


class _StubGemini:
    """Returns a fixed set of scores; records the schema it was asked for."""

    def __init__(self, scores: list[tuple[int, float]]):
        self._scores = scores

    def generate_structured(self, prompt, schema, settings=None):
        assert schema is _RerankScores
        return _RerankScores(
            scores=[_CandidateScore(index=i, score=v) for i, v in self._scores]
        )


class _BoomGemini:
    def generate_structured(self, *a, **k):
        raise RuntimeError("model unreachable")


# --------------------------------------------------------------------------- #
# Ordering, truncation, provenance
# --------------------------------------------------------------------------- #
def test_rerank_reorders_by_relevance_and_truncates():
    cands = _cands(5)
    # Invert the fused order: the last candidate is judged most useful.
    stub = _StubGemini([(4, 0.9), (3, 0.8), (2, 0.7), (1, 0.6), (0, 0.5)])
    out = Reranker(_settings(), gemini=stub).rerank("q", cands, top_k=3)
    assert [c.chunk.id for c in out] == ["4", "3", "2"]
    assert all(c.how == "rerank" for c in out)
    assert [round(c.score, 2) for c in out] == [0.9, 0.8, 0.7]


def test_rerank_falls_back_to_final_top_k_from_settings():
    out = Reranker(_settings(final_top_k=2), gemini=_StubGemini([(0, 0.1), (1, 0.9)])).rerank(
        "q", _cands(4)
    )
    assert len(out) == 2
    assert out[0].chunk.id == "1"  # highest score first


def test_rerank_scores_are_clamped_to_unit_interval():
    out = Reranker(_settings(), gemini=_StubGemini([(0, 5.0), (1, -3.0)])).rerank(
        "q", _cands(2), top_k=2
    )
    assert out[0].chunk.id == "0" and out[0].score == 1.0
    assert out[1].chunk.id == "1" and out[1].score == 0.0


# --------------------------------------------------------------------------- #
# Robustness: unscored / out-of-range indices, and outright failure
# --------------------------------------------------------------------------- #
def test_unscored_candidates_sink_but_keep_fused_order():
    # Model scores only index 3; the rest are omitted and must fall back behind
    # it in their original fused order.
    out = Reranker(_settings(), gemini=_StubGemini([(3, 0.9)])).rerank(
        "q", _cands(4), top_k=4
    )
    assert [c.chunk.id for c in out] == ["3", "0", "1", "2"]


def test_out_of_range_indices_are_ignored():
    out = Reranker(_settings(), gemini=_StubGemini([(99, 1.0), (0, 0.5)])).rerank(
        "q", _cands(2), top_k=2
    )
    assert [c.chunk.id for c in out] == ["0", "1"]


def test_rerank_failure_degrades_to_fused_order():
    cands = _cands(5)
    out = Reranker(_settings(), gemini=_BoomGemini()).rerank("q", cands, top_k=3)
    assert [c.chunk.id for c in out] == ["0", "1", "2"]
    assert all(c.how == "rrf" for c in out)  # provenance untouched on fallback


def test_disabled_reranker_returns_fused_order_untouched():
    cands = _cands(4)
    # A stub that would reorder if called — it must not be called when disabled.
    out = Reranker(_settings(rerank_enabled=False), gemini=_BoomGemini()).rerank(
        "q", cands, top_k=2
    )
    assert [c.chunk.id for c in out] == ["0", "1"]


def test_empty_candidates_returns_empty():
    assert Reranker(_settings(), gemini=_BoomGemini()).rerank("q", [], top_k=3) == []
