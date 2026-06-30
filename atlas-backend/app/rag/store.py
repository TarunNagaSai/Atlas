"""pgvector-backed vector store.

Schema (created on first use):
  chunks table — one row per child chunk, embedding column is a pgvector
  HNSW index for fast approximate cosine search.

Hybrid retrieval combines:
  - Dense:   pgvector cosine similarity  (<=> operator)
  - Lexical: PostgreSQL full-text search (tsvector / tsquery)
  - Fusion:  Reciprocal Rank Fusion in Python

NOTE: the database is not wired up yet. This module is DB-ready — the moment a
reachable ``DATABASE_URL`` is set, ``add()`` and the search methods work as-is.
Until then, ingestion runs in dry-run mode and never touches this store.
"""

from __future__ import annotations

import json
import re
from typing import Any

import logfire
import numpy as np

from app.llm.embedding import GeminiEmbedding, get_embedder
from app.schema.documents import Chunk, Scored
from app.schema.llm_settings import Settings, get_settings

# Retrieval knobs (local defaults — ingestion doesn't depend on these).
DENSE_TOP_K = 20
LEXICAL_TOP_K = 20
RRF_K = 60
FUSED_TOP_K = 12

_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    text        TEXT        NOT NULL,
    source      TEXT        NOT NULL,
    parent_id   TEXT        NOT NULL,
    parent_text TEXT        NOT NULL,
    book_id     TEXT        NOT NULL DEFAULT '',
    title       TEXT        NOT NULL DEFAULT '',
    metadata    JSONB       NOT NULL DEFAULT '{{}}',
    embedding   vector({dim})
);

CREATE INDEX IF NOT EXISTS chunks_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_book_id_idx ON chunks (book_id);
"""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _rrf(ranked_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, doc_id in enumerate(lst):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


class HybridStore:
    def __init__(
        self, settings: Settings | None = None, embedder: GeminiEmbedding | None = None
    ):
        self.s = settings or get_settings()
        self._embedder = embedder
        self._conn = None

    @property
    def embedder(self) -> GeminiEmbedding:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    # ---------------------------------------------------------------- connect
    def _connect(self):
        import psycopg2
        from pgvector.psycopg2 import register_vector

        if not self.s.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Connect Postgres before persisting "
                "chunks (ingestion can still run in dry-run mode without it)."
            )
        # Liveness check: the Supabase pooler silently drops idle sessions (e.g.
        # while a slow embedding batch runs between inserts), and psycopg2 won't
        # flag it via ``.closed`` until a query fails. Ping; reconnect if dead.
        if self._conn is not None and not self._conn.closed:
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg2.Error:
                try:
                    self._conn.close()
                except psycopg2.Error:
                    pass
                self._conn = None
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.s.database_url)
            register_vector(self._conn)
        return self._conn

    def _setup(self) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(_DDL.format(dim=self.s.embed_dim))
        conn.commit()

    # ------------------------------------------------------------------- add
    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        import psycopg2.extras

        with logfire.span("store.add", n_chunks=len(chunks)):
            # Embed first (the slow part), then touch the DB — so the connection
            # isn't held open and idle long enough for the pooler to drop it.
            embeddings = self._embed_chunks(chunks)
            self._setup()
            conn = self._connect()
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO chunks (id, text, source, parent_id, parent_text, book_id, title, metadata, embedding)
                    VALUES %s
                    ON CONFLICT (id) DO NOTHING
                    """,
                    [
                        (
                            c.id,
                            c.text,
                            c.source,
                            c.parent_id,
                            c.parent_text,
                            c.book_id,
                            c.title,
                            json.dumps(c.metadata),
                            embeddings[i].tolist(),
                        )
                        for i, c in enumerate(chunks)
                    ],
                )
            conn.commit()
            logfire.info("stored {n} chunks in pgvector", n=len(chunks))

    def _embed_chunks(self, chunks: list[Chunk]) -> np.ndarray:
        """Embed chunks into one shared space: PDF-page chunks go through the
        multimodal path (page image + text), plain-text chunks through the text
        path. Both land in the same ``embed_dim`` vector space so a text query
        retrieves either."""
        out = np.zeros((len(chunks), self.s.embed_dim), dtype=np.float32)
        pdf_idx = [i for i, c in enumerate(chunks) if c.embed_pdf is not None]
        txt_idx = [i for i, c in enumerate(chunks) if c.embed_pdf is None]
        if pdf_idx:
            pdf_vecs = self.embedder.embed_pdfs([chunks[i].embed_pdf for i in pdf_idx])
            for slot, i in enumerate(pdf_idx):
                out[i] = pdf_vecs[slot]
        if txt_idx:
            txt_vecs = self.embedder.embed([chunks[i].text for i in txt_idx])
            for slot, i in enumerate(txt_idx):
                out[i] = txt_vecs[slot]
        return out

    # --------------------------------------------------------------- search
    def dense_search(
        self,
        query_vec: np.ndarray,
        top_k: int,
        source_filter: str | None = None,
        book_id: str | None = None,
    ) -> list[tuple[str, float]]:
        conn = self._connect()
        conds: list[str] = []
        filt_params: list[Any] = []
        if book_id:
            conds.append("book_id = %s")
            filt_params.append(book_id)
        if source_filter:
            conds.append("source LIKE %s")
            filt_params.append(f"%{source_filter}%")
        where = ("WHERE " + " AND ".join(conds)) if conds else ""

        sql = """
            SELECT id, 1 - (embedding <=> %s::vector) AS score
            FROM chunks
            {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """.format(where=where)

        params: list[Any] = [query_vec.tolist(), *filt_params, query_vec.tolist(), top_k]

        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [(row[0], row[1]) for row in cur.fetchall()]

    def lexical_search(
        self,
        query: str,
        top_k: int,
        source_filter: str | None = None,
        book_id: str | None = None,
    ) -> list[tuple[str, float]]:
        conn = self._connect()
        ts_query = " & ".join(_tokenize(query)) or "x"
        conds: list[str] = []
        filt_params: list[Any] = []
        if book_id:
            conds.append("book_id = %s")
            filt_params.append(book_id)
        if source_filter:
            conds.append("source LIKE %s")
            filt_params.append(f"%{source_filter}%")
        extra = ("AND " + " AND ".join(conds)) if conds else ""

        sql = """
            SELECT id,
                   ts_rank(to_tsvector('english', text), to_tsquery('english', %s)) AS score
            FROM chunks
            WHERE to_tsvector('english', text) @@ to_tsquery('english', %s)
            {extra}
            ORDER BY score DESC
            LIMIT %s
        """.format(extra=extra)

        params: list[Any] = [ts_query, ts_query, *filt_params, top_k]

        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [(row[0], float(row[1])) for row in cur.fetchall()]

    def hybrid_search(
        self,
        query: str,
        query_vec: np.ndarray,
        *,
        top_k: int = FUSED_TOP_K,
        book_id: str | None = None,
    ) -> list[Scored]:
        with logfire.span(
            "store.hybrid_search", query=query, top_k=top_k, book_id=book_id
        ) as span:
            dense = self.dense_search(query_vec, DENSE_TOP_K, book_id=book_id)
            lexical = self.lexical_search(query, LEXICAL_TOP_K, book_id=book_id)
            span.set_attribute("n_dense", len(dense))
            span.set_attribute("n_lexical", len(lexical))

            fused = _rrf([[d for d, _ in dense], [lx for lx, _ in lexical]])
            ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:top_k]

            ids = [cid for cid, _ in ranked]
            if not ids:
                logfire.info("hybrid search for {query!r} returned no results", query=query)
                return []

            chunks_by_id = self._fetch_by_ids(ids)
            results = [
                Scored(chunk=chunks_by_id[cid], score=score, how="rrf")
                for cid, score in ranked
                if cid in chunks_by_id
            ]
            span.set_attribute("n_results", len(results))
            return results

    def _fetch_by_ids(self, ids: list[str]) -> dict[str, Chunk]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, source, parent_id, parent_text, book_id, title, metadata "
                "FROM chunks WHERE id = ANY(%s)",
                (ids,),
            )
            return {
                row[0]: Chunk(
                    id=row[0],
                    text=row[1],
                    source=row[2],
                    parent_id=row[3],
                    parent_text=row[4],
                    book_id=row[5],
                    title=row[6],
                    metadata=row[7] if isinstance(row[7], dict) else json.loads(row[7]),
                )
                for row in cur.fetchall()
            }

    # ---------------------------------------------------------- chunk access
    @property
    def chunks(self) -> list[Chunk]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, source, parent_id, parent_text, book_id, title, metadata "
                "FROM chunks"
            )
            return [
                Chunk(
                    id=row[0],
                    text=row[1],
                    source=row[2],
                    parent_id=row[3],
                    parent_text=row[4],
                    book_id=row[5],
                    title=row[6],
                    metadata=row[7] if isinstance(row[7], dict) else json.loads(row[7]),
                )
                for row in cur.fetchall()
            ]

    def get(self, chunk_id: str) -> Chunk | None:
        return self._fetch_by_ids([chunk_id]).get(chunk_id)

    def fetch_parents(self, parent_ids: list[str]) -> dict[str, Chunk]:
        """Map parent ids -> a representative Chunk carrying that parent's text.

        The GraphRAG provenance bridge: graph nodes store the ``parent_id``s of
        the blocks a relation was extracted from; to quote real passages we need
        the full ``parent_text`` back. Many child chunks share one parent, so we
        pick one row per ``parent_id`` (``DISTINCT ON``) — the returned Chunk's
        ``id`` is that representative child, but ``parent_text`` is what callers
        actually quote.
        """
        if not parent_ids:
            return {}
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (parent_id) "
                "parent_id, id, text, source, parent_text, book_id, title, metadata "
                "FROM chunks WHERE parent_id = ANY(%s)",
                (parent_ids,),
            )
            return {
                row[0]: Chunk(
                    id=row[1],
                    text=row[2],
                    source=row[3],
                    parent_id=row[0],
                    parent_text=row[4],
                    book_id=row[5],
                    title=row[6],
                    metadata=row[7] if isinstance(row[7], dict) else json.loads(row[7]),
                )
                for row in cur.fetchall()
            }

    def get_overview(self, book_id: str) -> list[Chunk]:
        """Overview chunk(s) for a book (metadata.kind == 'overview').

        These describe the book *itself* — what it is, what it contains, who
        filed/authored it — answering meta-questions that no single content page
        covers. The retrieve tool can always-include these for the active book so
        such questions are answered reliably, independent of ranking.
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM chunks "
                "WHERE book_id = %s AND metadata->>'kind' = 'overview'",
                (book_id,),
            )
            ids = [row[0] for row in cur.fetchall()]
        by_id = self._fetch_by_ids(ids)
        return [by_id[i] for i in ids if i in by_id]

    def list_books(self) -> list[dict[str, Any]]:
        """Distinct books for the frontend picker: ``{book_id, title, n_chunks}``."""
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT book_id, max(title) AS title, count(*) AS n "
                "FROM chunks GROUP BY book_id ORDER BY n DESC"
            )
            return [
                {"book_id": row[0], "title": row[1], "n_chunks": row[2]}
                for row in cur.fetchall()
            ]

    @staticmethod
    def exists(settings: Settings | None = None) -> bool:
        """True if a reachable DB already holds at least one chunk."""
        s = settings or get_settings()
        if not s.database_url:
            return False
        try:
            import psycopg2
            from pgvector.psycopg2 import register_vector

            conn = psycopg2.connect(s.database_url)
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chunks")
                count = cur.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:  # noqa: BLE001 - missing DB/table is just "no index"
            return False
