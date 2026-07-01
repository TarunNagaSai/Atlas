from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Settings:
    def __init__(self) -> None:
        # Accept either name; GOOGLE_API_KEY wins (matches the SDK's own precedence).
        self.api_key: str = (
            os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        )
        self.gen_model: str = _env("GEMINI_MODEL", "gemini-3.5-flash")
        # Stream the model's summarized reasoning as ``thought`` events. Costs
        # thinking tokens; turn off to save them when reasoning isn't surfaced.
        self.include_thoughts: bool = _env("INCLUDE_THOUGHTS", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        # Safety valve on the ReAct loop, not a functional limit: the agent
        # normally runs until it stops calling tools and answers. This is a high
        # backstop so a model stuck in a retrieve-loop can't spin forever — on the
        # final allowed turn the agent drops its tools and forces an answer from
        # whatever it has already gathered (see run_agent).
        self.agent_max_hops: int = int(_env("AGENT_MAX_HOPS", "40"))

        # --- Embeddings ---------------------------------------------------
        # gemini-embedding-2 is natively multimodal (text + image + PDF map into
        # one shared space) and supports Matryoshka truncation (128..3072). 1536
        # is a strong quality/footprint trade-off; embeddings are always
        # L2-normalized so cosine similarity == dot product.
        # Embeddings can use a dedicated key (separate quota/billing); falls back
        # to the main key if GOOGLE_API_EMBEDDING_KEY is unset.
        self.embed_api_key: str = (
            os.getenv("GOOGLE_API_EMBEDDING_KEY") or self.api_key
        )
        self.embed_model: str = _env("EMBED_MODEL", "gemini-embedding-2")
        self.embed_dim: int = int(_env("EMBED_DIM", "1536"))
        # This model returns one embedding per request (no batching), so large
        # ingests are paced to stay under the per-minute request quota. 0 = off.
        self.embed_rpm: int = int(_env("EMBED_RPM", "0"))

        # --- Chunking -----------------------------------------------------
        self.chunk_tokens: int = int(_env("CHUNK_TOKENS", "320"))
        self.chunk_overlap_tokens: int = int(_env("CHUNK_OVERLAP_TOKENS", "60"))
        self.parent_chunk_tokens: int = int(_env("PARENT_CHUNK_TOKENS", "1200"))

        # --- Attachments --------------------------------------------------
        # Per-file size cap for chat attachments (images/PDF/Word/Excel),
        # enforced after base64 decode. The frontend enforces the same cap
        # before upload; this is the server-side backstop.
        self.max_attachment_mb: int = int(_env("MAX_ATTACHMENT_MB", "4"))

        # --- Persistence --------------------------------------------------
        self.database_url: str = os.getenv("DATABASE_URL", "")

        # --- GraphRAG -----------------------------------------------------
        # A per-book knowledge graph (entities as nodes, relations as edges) is
        # built at ingestion and persisted to the ``graphs`` table; the agent's
        # ``graph_search`` tool loads and traverses it at query time.
        self.graph_table: str = _env("GRAPH_TABLE", "graphs")
        # Model for the graph's LLM reads (triple extraction, entity extraction,
        # community summaries). A cheaper/faster model than the chat generation
        # model is fine here — these are high-volume, structured-output calls.
        self.graph_model: str = _env("GRAPH_MODEL", "gemini-3.1-flash-lite")
        # Build cost knob: triples are extracted once per parent block. Skip
        # blocks shorter than this (too little text to yield useful relations).
        self.graph_min_block_chars: int = int(_env("GRAPH_MIN_BLOCK_CHARS", "200"))
        # Local search: how many hops out from a matched entity to gather backing
        # passages (1 = direct relations only, 2 = neighbours-of-neighbours).
        self.graph_local_hops: int = int(_env("GRAPH_LOCAL_HOPS", "2"))
        # Cap on distinct parent passages returned by either search mode, to keep
        # the context handed back to the agent bounded.
        self.graph_max_parents: int = int(_env("GRAPH_MAX_PARENTS", "6"))
        # Global search: how many top community summaries to return.
        self.graph_global_top: int = int(_env("GRAPH_GLOBAL_TOP", "3"))
        # Communities smaller than this are skipped when summarizing (too small
        # to represent a meaningful theme).
        self.graph_min_community: int = int(_env("GRAPH_MIN_COMMUNITY", "3"))

        # --- Reranking ----------------------------------------------------
        # A cross-encoder-style second pass: hybrid_search ranks by proximity
        # (how close a passage sits to the query), which isn't the same as
        # usefulness — the passage that actually answers the question often sits
        # a few ranks down. The reranker reads query + candidate *together* and
        # scores each for answer-usefulness, restoring precision after wide
        # recall. Retrieve ``fused_top_k`` (wide net), rerank to ``final_top_k``.
        self.rerank_enabled: bool = _env("RERANK_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        # A cheaper/faster model is fine — this is one structured scoring call
        # over a short candidate list, not open-ended generation.
        self.rerank_model: str = _env("RERANK_MODEL", "gemini-3.1-flash-lite")
        # Candidates kept after RRF fusion and handed to the reranker.
        self.fused_top_k: int = int(_env("FUSED_TOP_K", "12"))
        # Passages the reranker keeps and the agent actually sees.
        self.final_top_k: int = int(_env("FINAL_TOP_K", "6"))

        # --- Observability ------------------------------------------------
        # Stdlib logging threshold; records below this never reach Logfire.
        self.log_level: str = _env("LOG_LEVEL", "INFO").upper()

    def require_key(self) -> str:
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set. Copy .env.example "
                "to .env and add your key, or export it in your shell."
            )
        return self.api_key

    def require_embed_key(self) -> str:
        if not self.embed_api_key:
            raise ValueError(
                "No embedding API key. Set GOOGLE_API_EMBEDDING_KEY (or "
                "GOOGLE_API_KEY/GEMINI_API_KEY as a fallback)."
            )
        return self.embed_api_key


@dataclass
class ModelSettings:
    """Shared generation parameters for every Gemini call."""

    system: str | None = None
    temperature: float = 0.2
    model: str | None = None
    max_output_tokens: int | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
