"""In-memory BM25 lexical index (``rank_bm25``) over cached chunk tokens.

The lexical half of ``HybridStore.hybrid_search``. Dense retrieval finds
*semantically* similar passages; BM25 catches the exact-term matches embeddings
blur over — tickers, defined terms, line-item names, specific figures. A user
asking for "Segment operating income" wants the row that literally says it, not
merely a paragraph that's topically close.

Built from the precomputed ``Chunk.bm25_tokens`` (see
``schema.documents.bm25_tokenize``), so no re-tokenizing happens at query time
and the query is tokenized the identical way the corpus was — any drift between
the two tokenizers silently degrades recall.

BM25 (Okapi) scores a document by, per query term: term frequency in the doc,
dampened (a term appearing 10× isn't 10× as relevant → the ``k1`` saturation),
times the term's inverse document frequency (rare terms discriminate more than
common ones), normalized by document length (``b``, so long docs don't win just
by being long). ``rank_bm25`` implements exactly this over an in-memory corpus.
"""

from __future__ import annotations

import numpy as np
from rank_bm25 import BM25Okapi


class BM25Index:
    """A frozen BM25 index over a fixed corpus of ``(id, tokens)`` documents.

    Cheap to query, rebuilt (not mutated) when the underlying corpus changes —
    the store caches one instance per book scope and drops it on new writes.
    """

    def __init__(self, ids: list[str], corpus: list[list[str]]):
        self.ids = ids
        # rank_bm25 can't initialize on an empty corpus (no docs → no avg length
        # to normalize against); an empty index simply yields no lexical hits.
        self._bm25 = BM25Okapi(corpus) if ids else None

    def __len__(self) -> int:
        return len(self.ids)

    def search(self, query_tokens: list[str], top_k: int) -> list[tuple[str, float]]:
        """Top-``top_k`` ``(chunk_id, score)`` for the tokenized query, best first.

        Scores every document, then keeps the highest ``top_k`` with a *positive*
        score — a non-positive BM25 score means no real term overlap (or a term
        so common its IDF is ≤0), which is noise we don't want polluting the RRF
        fusion. Returns fewer than ``top_k`` when few documents genuinely match.
        """
        if self._bm25 is None or not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        # argpartition to find the top_k cheaply, then sort just those descending.
        k = min(top_k, len(scores))
        top = np.argpartition(scores, -k)[-k:]
        top = top[np.argsort(scores[top])[::-1]]
        return [(self.ids[i], float(scores[i])) for i in top if scores[i] > 0]
