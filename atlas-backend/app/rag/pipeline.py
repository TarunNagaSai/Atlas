"""IngestionPipeline — load -> chunk -> embed -> (store).

The ingestion slice of a RAG system. Two modes:

  * dry-run (default): load -> chunk -> embed a small sample (to validate the
    embedding path and capture the vector dimension) -> return a preview. No
    database is touched. This is the mode used until ``DATABASE_URL`` is wired.
  * persist=True: embed every chunk and write it to the pgvector store. Requires
    a reachable database.

Everything is reported back in an ``IngestReport`` so the upload endpoint can
return exactly what happened — observability beats magic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import logfire

from app.llm.embedding import GeminiEmbedding, get_embedder
from app.rag.chunking import (
    SemanticChunker,
    approx_tokens,
    chunk_documents,
    chunk_pages_as_pdf,
)
from app.rag.loaders import load_path, load_text
from app.rag.store import HybridStore
from app.schema.documents import Chunk, Document, make_book_id
from app.schema.llm_settings import Settings, get_settings


@dataclass
class SampleChunk:
    loc: str
    approx_tokens: int
    preview: str  # first slice of the child text


@dataclass
class IngestReport:
    source: str
    n_documents: int  # pages for a PDF, sections for semantic, 1 for plain text
    n_chunks: int
    sample_chunks: list[SampleChunk] = field(default_factory=list)
    embedded_sample: int = 0
    embed_dim: int | None = None
    persisted: bool = False
    note: str = ""


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: GeminiEmbedding | None = None,
        store: HybridStore | None = None,
    ):
        self.s = settings or get_settings()
        self._embedder = embedder
        self._store = store

    @property
    def embedder(self) -> GeminiEmbedding:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    @property
    def store(self) -> HybridStore:
        if self._store is None:
            self._store = HybridStore(self.s, self._embedder)
        return self._store

    def ingest(
        self,
        source: str | Path | None = None,
        *,
        text: str | None = None,
        title: str | None = None,
        kind: str | None = None,
        persist: bool = False,
        semantic: bool = False,
        embed_sample: int = 5,
        sample_preview_chars: int = 240,
    ) -> IngestReport:
        src_label = str(source) if source is not None else "inline"

        with logfire.span(
            "ingest", source=src_label, persist=persist, semantic=semantic
        ):
            # 1. load
            with logfire.span("ingest.load"):
                if text is not None:
                    docs: list[Document] = load_text(text)
                elif source is not None:
                    docs = load_path(source)
                else:
                    raise ValueError("Provide either a source path or text=")
                # A friendly title overrides the filename-derived one — essential
                # for uploads, where ``source`` is a random temp path. The book_id
                # is recomputed from it so all pages share one id.
                if title:
                    book_id = make_book_id(title)
                    for d in docs:
                        d.title = title
                        d.book_id = book_id
                # ``kind`` (e.g. "overview") is stamped onto every chunk's
                # metadata so meta-docs about a book are distinguishable from its
                # page content — the retrieve tool can always-include the overview
                # for the active book, and content chunks default to no kind.
                if kind:
                    for d in docs:
                        d.metadata["kind"] = kind
                logfire.info("loaded {n} document(s)", n=len(docs))

            # 2. chunk
            #   PDF sources → page-as-PDF (each page is one multimodally-embedded
            #   chunk: text + charts/images). Text/DOCX → sentence-window
            #   children, optionally split on topic shifts.
            is_pdf = any(d.embed_pdf is not None for d in docs)
            with logfire.span("ingest.chunk", semantic=semantic, pdf=is_pdf):
                if is_pdf:
                    chunks = chunk_pages_as_pdf(docs, self.s)
                elif semantic:
                    chunks = SemanticChunker(self._embedder, self.s).chunk(docs)
                else:
                    chunks = chunk_documents(docs, self.s)
                logfire.info("chunked into {n} chunk(s)", n=len(chunks))

            return self._finish_ingest(
                docs, chunks, src_label, persist, embed_sample, sample_preview_chars
            )

    def _finish_ingest(
        self,
        docs: list[Document],
        chunks: list[Chunk],
        src_label: str,
        persist: bool,
        embed_sample: int,
        sample_preview_chars: int,
    ) -> IngestReport:
        report = IngestReport(
            source=src_label,
            n_documents=len(docs),
            n_chunks=len(chunks),
            sample_chunks=[
                SampleChunk(
                    loc=c.metadata.get("loc", ""),
                    approx_tokens=approx_tokens(c.text),
                    preview=c.text[:sample_preview_chars],
                )
                for c in chunks[:embed_sample]
            ],
        )

        if not chunks:
            report.note = "No extractable text found in the document."
            return report

        # 3. embed (+ optionally store)
        if persist:
            return self._persist(chunks, report)
        return self._dry_run(chunks, report, embed_sample)

    # ------------------------------------------------------------ persist path
    def _persist(self, chunks: list[Chunk], report: IngestReport) -> IngestReport:
        if not self.s.database_url:
            raise RuntimeError(
                "persist=true requires a DATABASE_URL. Connect Postgres, or call "
                "without persist to run a dry-run preview."
            )
        try:
            self.store.add(chunks)  # embeds all chunks + writes to pgvector
        except Exception as e:  # noqa: BLE001 - surface DB connectivity as a clean 503
            import psycopg2

            if isinstance(e, (psycopg2.OperationalError, psycopg2.errors.Error)):
                logfire.error("vector store unreachable during persist: {err}", err=str(e))
                raise RuntimeError(
                    f"Could not reach the vector store at DATABASE_URL ({e}). "
                    "Connect Postgres (with the pgvector extension), or drop "
                    "persist to run a dry-run preview."
                ) from e
            raise
        report.embedded_sample = len(chunks)
        report.embed_dim = self.s.embed_dim
        report.persisted = True
        report.note = f"Persisted {len(chunks)} chunks to the vector store."
        # Build the book's knowledge graph from the same chunks and persist it
        # alongside. Supplementary to retrieval — a graph failure (e.g. an LLM
        # hiccup mid-extraction) must not fail an otherwise-successful ingest.
        self._build_graph(chunks)
        logfire.info(
            "persisted {n} chunks (dim={dim})", n=len(chunks), dim=self.s.embed_dim
        )
        return report

    def _build_graph(self, chunks: list[Chunk]) -> None:
        """Build + persist the per-book knowledge graph (best-effort)."""
        from app.rag.graph import GraphIndex

        try:
            with logfire.span("ingest.graph", n_chunks=len(chunks)):
                idx = GraphIndex(self.s, store=self.store, embedder=self._embedder)
                idx.build(chunks)
                idx.save()
        except Exception as e:  # noqa: BLE001 - graph is supplementary to retrieval
            logfire.warn("graph build skipped (ingest still succeeded): {err}", err=str(e))

    # ------------------------------------------------------------ dry-run path
    def _dry_run(
        self, chunks: list[Chunk], report: IngestReport, embed_sample: int
    ) -> IngestReport:
        report.persisted = False
        # Validate the embedding path on a small sample (cheap, proves the wiring).
        # Mirror the persist path: PDF-page chunks embed multimodally, text chunks
        # embed as text.
        sample = chunks[:embed_sample]
        try:
            self.s.require_embed_key()
            if sample and sample[0].embed_pdf is not None:
                vecs = self.embedder.embed_pdfs([c.embed_pdf for c in sample])
            else:
                vecs = self.embedder.embed([c.text for c in sample])
            report.embedded_sample = int(vecs.shape[0])
            report.embed_dim = int(vecs.shape[1]) if vecs.size else self.s.embed_dim
            report.note = (
                f"Dry-run: chunked {report.n_chunks} chunks and embedded a "
                f"{report.embedded_sample}-chunk sample (dim={report.embed_dim}). "
                "Not persisted — connect DATABASE_URL and pass persist=true to store."
            )
            logfire.info(
                "dry-run embedded {n}-chunk sample (dim={dim})",
                n=report.embedded_sample,
                dim=report.embed_dim,
            )
        except Exception as e:  # noqa: BLE001 - no key / embed failure must not 500
            report.embedded_sample = 0
            report.embed_dim = self.s.embed_dim
            logfire.warn("dry-run embedding sample skipped: {err}", err=str(e))
            report.note = (
                f"Dry-run: chunked {report.n_chunks} chunks. Embedding sample "
                f"skipped ({e}). Set GOOGLE_API_KEY/GEMINI_API_KEY to validate "
                "the embedding step."
            )
        return report
