"""Core data structures shared across the ingestion/retrieval pipeline.

These are kept plain and serializable so the whole index can be persisted to a
store and inspected by hand — observability beats magic.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BM25_WORD = re.compile(r"[A-Za-z0-9_]+")


def bm25_tokenize(text: str) -> list[str]:
    """Lowercase word tokenization for BM25 lexical retrieval.

    Kept deliberately dependency-free and deterministic so the *exact same*
    tokens are produced at ingest time (cached in ``Chunk.bm25_tokens`` and
    persisted) and at query time (when tokenizing the incoming question).
    ``rank_bm25`` scores a tokenized corpus against a tokenized query, so any
    drift between the two tokenizers silently degrades recall.
    """
    return _BM25_WORD.findall(text.lower())


def _hash(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:16]


def book_title(source: str) -> str:
    """Human-readable book name derived from a source path (filename stem).

    ``/Users/x/Downloads/annualreport-2025.pdf`` -> ``annualreport-2025``.
    Used as the display label in the frontend book picker.
    """
    return Path(source).stem or source


def make_book_id(name: str) -> str:
    """Deterministic id shared by every chunk of one book.

    Hash of the normalized (trimmed, lowercased) book name, so re-uploading the
    same book yields the same id — book-level idempotency, mirroring how
    ``Chunk.make_id`` makes chunk-level re-ingestion idempotent.
    """
    return _hash(name.strip().lower())


@dataclass
class Document:
    """A raw source document before chunking."""

    text: str
    source: str  # file path / URL / id
    metadata: dict[str, Any] = field(default_factory=dict)
    # Book identity shared by every chunk of this source. Derived from the
    # filename stem when not supplied, so all pages of one PDF carry the same
    # book_id and the agent can scope retrieval to a single book.
    book_id: str = ""
    title: str = ""
    # Transient: raw single-page PDF bytes embedded multimodally (text + images
    # + charts on the page) by gemini-embedding-2. Never persisted — only the
    # resulting vector is stored. None for plain-text/docx sources.
    embed_pdf: bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.title:
            self.title = book_title(self.source)
        if not self.book_id:
            self.book_id = make_book_id(self.title)


@dataclass
class Chunk:
    """A retrievable child chunk. ``parent_text`` is the larger block we swap in
    at generation time (parent-document retrieval)."""

    id: str
    text: str
    source: str
    parent_id: str
    parent_text: str
    book_id: str = ""  # shared by all chunks of one book (see Document)
    title: str = ""  # display name for the book picker
    metadata: dict[str, Any] = field(default_factory=dict)
    # Precomputed lexical tokens for BM25 retrieval. Cached alongside the vector
    # so the in-memory ``rank_bm25`` index can be built straight from the store
    # without re-tokenizing every chunk on each query. Auto-derived from ``text``
    # when not supplied (see __post_init__); persisted as a TEXT[] column.
    bm25_tokens: list[str] = field(default_factory=list)
    # Transient: single-page PDF bytes for multimodal embedding. When set, the
    # store embeds this (capturing images/charts) instead of ``text``. Excluded
    # from to_dict/from_dict and the DB row — only the vector survives.
    embed_pdf: bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Derive tokens from text unless explicitly provided (e.g. loaded from
        # the DB). Guarded so re-hydrated chunks keep their stored tokens.
        if not self.bm25_tokens and self.text:
            self.bm25_tokens = bm25_tokenize(self.text)

    @staticmethod
    def make_id(source: str, text: str, idx: int) -> str:
        return _hash(source, str(idx), text[:64])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "parent_id": self.parent_id,
            "parent_text": self.parent_text,
            "book_id": self.book_id,
            "title": self.title,
            "bm25_tokens": self.bm25_tokens,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        return cls(**d)


@dataclass
class Scored:
    """A chunk paired with a relevance score and provenance about how it was found."""

    chunk: Chunk
    score: float
    how: str = ""  # e.g. "dense", "bm25", "rrf", "rerank"

    @property
    def citation(self) -> str:
        loc = self.chunk.metadata.get("loc")
        return f"{self.chunk.source}" + (f"#{loc}" if loc else "")
