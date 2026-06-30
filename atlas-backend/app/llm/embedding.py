"""Gemini embedding wrapper.

Why a wrapper at all? Three reasons:
  1. One place to apply retries/backoff (the network is flaky; quotas exist).
  2. Embeddings need *different task types* for documents vs queries — getting this
     right is one of the highest-leverage, least-known RAG tricks.
  3. We always L2-normalize embeddings so cosine similarity == dot product, which
     keeps the vector store fast and correct after Matryoshka truncation.
"""

from __future__ import annotations

import time
from typing import Sequence

import logfire
import numpy as np
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schema.llm_settings import Settings, get_settings

# Task types tell the embedding model how the text will be used. Documents and
# queries are embedded into a shared space but with asymmetric optimization.
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"


class GeminiEmbedding:
    def __init__(self, settings: Settings | None = None, api_key: str | None = None):
        self.s = settings or get_settings()
        # A per-request key (a visitor's own key, BYO-key flow) takes precedence;
        # otherwise embeddings use their own key (separate quota/billing), which
        # falls back to the main key inside require_embed_key().
        self.client = genai.Client(api_key=api_key or self.s.require_embed_key())

    # Patient retry: a 429 per-minute quota window needs a wait long enough to
    # outlast it (up to ~60s), so transient rate limits self-pace instead of
    # failing the run.
    @retry(stop=stop_after_attempt(8), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _embed_raw(self, text: str, task_type: str) -> list[float]:
        """Embed ONE text. ``embed_content`` returns a single embedding per call
        for this model — passing a list of contents is interpreted as one
        interleaved input (yielding one vector), not a batch — so callers must
        loop, they can't rely on batching here."""
        resp = self.client.models.embed_content(
            model=self.s.embed_model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.s.embed_dim,
            ),
        )
        return resp.embeddings[0].values

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
    def _embed_pdf_raw(self, pdf: bytes, task_type: str) -> list[float]:
        """Embed one single-page PDF as a multimodal unit (text + images +
        charts on the page) into the shared embedding space."""
        part = types.Part.from_bytes(data=pdf, mime_type="application/pdf")
        resp = self.client.models.embed_content(
            model=self.s.embed_model,
            contents=[part],
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.s.embed_dim,
            ),
        )
        return resp.embeddings[0].values

    def embed(
        self, texts: Sequence[str], *, task_type: str = TASK_DOCUMENT
    ) -> np.ndarray:
        """Embed texts -> (n, dim) float32 array, L2-normalized.

        One request per text: this model's ``embed_content`` returns a single
        embedding per call (a list of contents is treated as one interleaved
        input, not a batch), so we loop. Each call is retried independently, so a
        single bad item can't sink the whole run.
        """
        if not texts:
            return np.zeros((0, self.s.embed_dim), dtype=np.float32)

        # Optional pacing to stay under the per-minute request quota on big runs.
        interval = 60.0 / self.s.embed_rpm if self.s.embed_rpm > 0 else 0.0
        with logfire.span(
            "embed",
            n_texts=len(texts),
            task_type=task_type,
            model=self.s.embed_model,
            rpm=self.s.embed_rpm,
        ):
            vectors: list[list[float]] = []
            for i, text in enumerate(texts):
                if interval and i:
                    time.sleep(interval)
                vectors.append(self._embed_raw(text, task_type))

        return self._normalize(vectors)

    def embed_pdfs(
        self, pdfs: Sequence[bytes], *, task_type: str = TASK_DOCUMENT
    ) -> np.ndarray:
        """Embed single-page PDFs -> (n, dim) float32 array, L2-normalized.

        Multimodal embed_content takes one document per call (multiple parts are
        interpreted as a single interleaved input), so PDFs are embedded
        one-at-a-time rather than batched like text.
        """
        if not pdfs:
            return np.zeros((0, self.s.embed_dim), dtype=np.float32)

        vectors: list[list[float]] = []
        with logfire.span(
            "embed_pdfs",
            n_pdfs=len(pdfs),
            task_type=task_type,
            model=self.s.embed_model,
        ):
            for pdf in pdfs:
                vectors.append(self._embed_pdf_raw(pdf, task_type))

        return self._normalize(vectors)

    def _normalize(self, vectors: list[list[float]]) -> np.ndarray:
        arr = np.asarray(vectors, dtype=np.float32)
        # Matryoshka truncation (<3072) requires renormalization for cosine to hold.
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text], task_type=TASK_QUERY)[0]


_embedder: GeminiEmbedding | None = None


def get_embedder(api_key: str | None = None) -> GeminiEmbedding:
    """Embedding client. With ``api_key`` (a visitor's own key) a fresh, uncached
    client is built per call so the key is never retained process-wide; without
    it, the shared server-key singleton is returned."""
    if api_key:
        return GeminiEmbedding(api_key=api_key)
    global _embedder
    if _embedder is None:
        _embedder = GeminiEmbedding()
    return _embedder
