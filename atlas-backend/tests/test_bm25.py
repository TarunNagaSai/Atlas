"""Unit tests for the BM25 lexical-retrieval path.

Covers the four pieces the BM25 feature added, all exercised without a database:

  - ``BM25Index`` (app/rag/bm25.py): ranking, top-k, positive-score filtering,
    and the empty-corpus / empty-query degenerate cases;
  - ``bm25_tokenize`` (schema/documents.py): the shared tokenizer used on both
    the stored corpus and the incoming query;
  - ``Chunk.bm25_tokens`` auto-derivation and serialization;
  - ``HybridStore``'s lexical wiring: query tokenization, per-book index caching,
    and the RRF fusion of dense + BM25 result lists.

Corpora are hand-built so the query term is *rare* (present in a minority of
docs) — that keeps its IDF firmly positive, so the assertions don't depend on
``rank_bm25``'s epsilon handling of common (negative-IDF) terms.
"""

from __future__ import annotations

import pytest

from app.rag.bm25 import BM25Index
from app.rag.store import HybridStore, _rrf
from app.schema.documents import Chunk, bm25_tokenize


# --------------------------------------------------------------------------- #
# BM25Index — ranking & edges
# --------------------------------------------------------------------------- #
def _index(*docs: tuple[str, list[str]]) -> BM25Index:
    return BM25Index([d[0] for d in docs], [d[1] for d in docs])


def test_bm25_returns_only_docs_containing_the_query_term():
    idx = _index(
        ("a", ["alpha", "beta"]),
        ("b", ["gamma", "delta"]),
        ("c", ["epsilon", "zeta"]),
        ("d", ["eta", "theta"]),
        ("hit", ["revenue", "iota"]),  # the only doc with 'revenue'
    )

    results = idx.search(["revenue"], top_k=5)

    # Only the matching doc scores positive; the rest are filtered out.
    assert [cid for cid, _ in results] == ["hit"]
    assert results[0][1] > 0


def test_bm25_ranks_higher_term_frequency_first():
    # 'revenue' in 2 of 5 docs → positive IDF. Both matching docs are the same
    # length, so term frequency alone decides order (no length-norm confound).
    idx = _index(
        ("more", ["revenue", "revenue"]),  # tf=2
        ("less", ["revenue", "other"]),    # tf=1
        ("p", ["x", "y"]),
        ("q", ["p", "q"]),
        ("r", ["m", "n"]),
    )

    results = idx.search(["revenue"], top_k=5)

    assert [cid for cid, _ in results] == ["more", "less"]
    assert results[0][1] > results[1][1]


def test_bm25_respects_top_k():
    idx = _index(
        ("more", ["revenue", "revenue"]),
        ("less", ["revenue", "other"]),
        ("p", ["x", "y"]),
        ("q", ["p", "q"]),
        ("r", ["m", "n"]),
    )

    results = idx.search(["revenue"], top_k=1)

    assert [cid for cid, _ in results] == ["more"]


def test_bm25_scores_are_python_floats():
    idx = _index(("hit", ["revenue"]), ("a", ["x"]), ("b", ["y"]))

    (_cid, score), = idx.search(["revenue"], top_k=1)

    assert isinstance(score, float)


def test_bm25_empty_query_returns_nothing():
    idx = _index(("hit", ["revenue"]), ("a", ["x"]))

    assert idx.search([], top_k=5) == []


def test_bm25_empty_corpus_returns_nothing():
    idx = BM25Index([], [])

    assert len(idx) == 0
    assert idx.search(["revenue"], top_k=5) == []


def test_bm25_no_match_returns_nothing():
    idx = _index(("a", ["x", "y"]), ("b", ["p", "q"]))

    assert idx.search(["revenue"], top_k=5) == []


def test_bm25_len_reports_corpus_size():
    idx = _index(("a", ["x"]), ("b", ["y"]), ("c", ["z"]))

    assert len(idx) == 3


# --------------------------------------------------------------------------- #
# bm25_tokenize — the shared tokenizer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Revenue grew 12% in FY2025.", ["revenue", "grew", "12", "in", "fy2025"]),
        ("world_1", ["world_1"]),  # underscore is a word char, kept intact
        ("a,b\nc", ["a", "b", "c"]),  # punctuation and newlines split
        ("   ", []),  # whitespace only → no tokens
        ("", []),
        ("MixedCASE", ["mixedcase"]),  # lowercased
    ],
)
def test_bm25_tokenize(text, expected):
    assert bm25_tokenize(text) == expected


# --------------------------------------------------------------------------- #
# Chunk.bm25_tokens — auto-derivation & serialization
# --------------------------------------------------------------------------- #
def _chunk(text: str, **kw) -> Chunk:
    return Chunk(id="1", text=text, source="s", parent_id="p", parent_text="pt", **kw)


def test_chunk_auto_derives_tokens_from_text():
    c = _chunk("Revenue grew.")

    assert c.bm25_tokens == ["revenue", "grew"]


def test_chunk_preserves_explicitly_provided_tokens():
    # Re-hydration from the DB passes stored tokens; they must not be recomputed.
    c = _chunk("Revenue grew.", bm25_tokens=["stored", "toks"])

    assert c.bm25_tokens == ["stored", "toks"]


def test_chunk_empty_text_yields_no_tokens():
    c = _chunk("")

    assert c.bm25_tokens == []


def test_chunk_to_dict_and_from_dict_round_trip_tokens():
    c = _chunk("Revenue grew.")

    d = c.to_dict()
    assert d["bm25_tokens"] == ["revenue", "grew"]
    assert Chunk.from_dict(d).bm25_tokens == ["revenue", "grew"]


# --------------------------------------------------------------------------- #
# _rrf — reciprocal rank fusion
# --------------------------------------------------------------------------- #
def test_rrf_rewards_documents_in_multiple_lists():
    # 'b' is ranked in both lists → it should fuse to the top.
    fused = _rrf([["a", "b", "c"], ["b", "d"]])
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])

    assert [cid for cid, _ in ranked] == ["b", "a", "d", "c"]


# --------------------------------------------------------------------------- #
# HybridStore — lexical wiring (no DB)
# --------------------------------------------------------------------------- #
class _RecordingIndex:
    """A stand-in BM25 index that records the tokens/top_k it was searched with."""

    def __init__(self):
        self.calls: list[tuple[list[str], int]] = []

    def search(self, tokens, top_k):
        self.calls.append((tokens, top_k))
        return [("chunk-1", 4.2)]


def test_bm25_search_tokenizes_query_and_delegates_to_index():
    store = HybridStore()
    fake = _RecordingIndex()
    store._bm25[""] = fake  # pre-seed the all-books cache so no DB build happens

    out = store.bm25_search("Revenue GREW 12%", top_k=7)

    # The query is tokenized with the same tokenizer the corpus used.
    assert fake.calls == [(["revenue", "grew", "12"], 7)]
    assert out == [("chunk-1", 4.2)]


def test_get_bm25_caches_per_book_scope(monkeypatch):
    store = HybridStore()
    builds: list[str | None] = []

    def fake_build(book_id):
        builds.append(book_id)
        return _RecordingIndex()

    monkeypatch.setattr(store, "_build_bm25", fake_build)

    store._get_bm25("book-a")
    store._get_bm25("book-a")  # cached → no rebuild
    store._get_bm25("book-b")  # different scope → one more build
    store._get_bm25(None)      # all-books scope ("") → one more build
    store._get_bm25(None)      # cached

    assert builds == ["book-a", "book-b", None]


def test_hybrid_search_fuses_dense_and_bm25(monkeypatch):
    """RRF fusion: a doc found by *both* retrievers outranks single-list hits,
    and each result is wrapped as a Scored(how='rrf')."""
    store = HybridStore()

    # 'shared' appears in both lists; the others in one each.
    monkeypatch.setattr(
        store, "dense_search", lambda vec, k, book_id=None: [("shared", 0.9), ("dense-only", 0.8)]
    )
    monkeypatch.setattr(
        store, "bm25_search", lambda q, k, book_id=None: [("shared", 5.0), ("bm25-only", 4.0)]
    )
    monkeypatch.setattr(
        store,
        "_fetch_by_ids",
        lambda ids: {
            cid: Chunk(id=cid, text=cid, source="s", parent_id=cid, parent_text=cid)
            for cid in ids
        },
    )

    results = store.hybrid_search("q", query_vec=None, top_k=3)

    assert [r.chunk.id for r in results] == ["shared", "dense-only", "bm25-only"]
    assert all(r.how == "rrf" for r in results)


def test_hybrid_search_respects_top_k(monkeypatch):
    store = HybridStore()
    monkeypatch.setattr(store, "dense_search", lambda vec, k, book_id=None: [("a", 1.0), ("b", 0.9)])
    monkeypatch.setattr(store, "bm25_search", lambda q, k, book_id=None: [("c", 1.0), ("d", 0.9)])
    monkeypatch.setattr(
        store,
        "_fetch_by_ids",
        lambda ids: {cid: Chunk(id=cid, text=cid, source="s", parent_id=cid, parent_text=cid) for cid in ids},
    )

    results = store.hybrid_search("q", query_vec=None, top_k=2)

    assert len(results) == 2


def test_hybrid_search_empty_when_no_hits(monkeypatch):
    store = HybridStore()
    monkeypatch.setattr(store, "dense_search", lambda vec, k, book_id=None: [])
    monkeypatch.setattr(store, "bm25_search", lambda q, k, book_id=None: [])

    assert store.hybrid_search("q", query_vec=None) == []
