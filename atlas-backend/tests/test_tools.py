"""Unit tests for the ``retrieve`` tool's output formatting (app/tools/tools.py).

The retrieval/rerank/embedding machinery is stubbed so these tests pin only the
part that matters for grounding: passages are handed to the agent **numbered**
(``[1]``, ``[2]`` …) with their source citation, de-duplicated by parent page,
so the model can cite each claim with a compact ``[n]`` marker that maps back to
a real document in the trace.
"""

from __future__ import annotations

import app.tools.tools as tools
from app.schema.documents import Chunk, Scored


def _scored(pid: str, source: str, loc: str, text: str) -> Scored:
    return Scored(
        chunk=Chunk(
            id=f"c-{pid}", text=text, source=source, parent_id=pid,
            parent_text=text, metadata={"loc": loc},
        ),
        score=1.0,
        how="rerank",
    )


class _FakeStore:
    def __init__(self, results: list[Scored]):
        self._results = results

    def hybrid_search(self, query, query_vec, *, top_k, book_id=None):
        return self._results


class _FakeReranker:
    """Identity reranker: keeps the fed order, truncated to ``top_k``."""

    def __init__(self, *a, **k):
        pass

    def rerank(self, query, candidates, top_k=None):
        return candidates[: (top_k or len(candidates))]


class _FakeEmbedder:
    def embed_query(self, q):
        return [0.0]


def _patch(monkeypatch, results: list[Scored]) -> None:
    monkeypatch.setattr(tools, "_get_store", lambda: _FakeStore(results))
    monkeypatch.setattr(tools, "get_embedder", lambda api_key=None: _FakeEmbedder())
    monkeypatch.setattr(tools, "get_gemini", lambda api_key=None: object())
    monkeypatch.setattr(tools, "Reranker", _FakeReranker)


def test_passages_are_numbered_with_source_citations(monkeypatch):
    _patch(monkeypatch, [
        _scored("p1", "annualreport-2025.pdf", "p12", "Net revenue was 1,240 crore."),
        _scored("p2", "annualreport-2025.pdf", "p13", "Opex was 800 crore."),
    ])

    out = tools.retrieve("revenue")

    assert "[1] Source: annualreport-2025.pdf#p12" in out
    assert "[2] Source: annualreport-2025.pdf#p13" in out
    # The passage text follows its numbered header.
    assert "[1] Source: annualreport-2025.pdf#p12\nNet revenue was 1,240 crore." in out


def test_numbering_dedupes_by_parent_page(monkeypatch):
    # Two children of the same parent page must collapse to a single [n] block.
    _patch(monkeypatch, [
        _scored("p1", "f.pdf", "p1", "First child of page 1."),
        _scored("p1", "f.pdf", "p1", "Second child of page 1."),
        _scored("p2", "f.pdf", "p2", "Page 2 content."),
    ])

    out = tools.retrieve("q")

    assert out.count("Source:") == 2  # one per distinct parent, not per child
    assert "[1] Source: f.pdf#p1" in out
    assert "[2] Source: f.pdf#p2" in out
    assert "Second child of page 1." not in out  # the duplicate parent is dropped


def test_no_results_returns_honest_message(monkeypatch):
    _patch(monkeypatch, [])

    out = tools.retrieve("q")

    assert "No relevant passages" in out
    assert "Source:" not in out


def test_empty_query_short_circuits(monkeypatch):
    _patch(monkeypatch, [_scored("p1", "f.pdf", "p1", "x")])

    assert "non-empty" in tools.retrieve("   ")
