from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class RetrievalProfile:
    """The model-dependent retrieval/eviction/hop knobs for one agent run.

    Resolved once per run by :meth:`Settings.retrieval_profile` from the active
    generation model, then threaded to the tool call and the eviction step so a
    weak model (flash) can run a relaxed profile without affecting other models.
    """

    keep_recent_tool_results: int
    passage_max_chars: int
    final_top_k: int
    fused_top_k: int
    agent_max_hops: int


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
        self.agent_max_hops: int = int(_env("AGENT_MAX_HOPS", "12"))

        # --- Gemini 3.5 Flash runaway guard -------------------------------
        # This lightweight model, run at temperature 0, is prone to a
        # within-turn thinking runaway: it narrates "re-search, re-search, to be
        # thorough" endlessly without ever committing to a function call or a
        # final answer. Neither loop backstop catches this — the repeat-search
        # breaker and max_hops only advance once a turn *completes* a tool call,
        # which a turn stuck thinking never does. So for this model only, cap the
        # thinking budget and nudge the temperature off greedy decoding (which is
        # what self-reinforces the loop). Every other model is left untouched:
        # matched by substring so a versioned id (…-preview) still trips it, and
        # the lighter plan/graph models (gemini-3.1-flash-lite) never match.
        self.flash_guard_model: str = _env("FLASH_GUARD_MODEL", "gemini-3.5-flash")
        self.flash_thinking_level: str = _env("FLASH_THINKING_LEVEL", "LOW")
        self.flash_temperature: float = float(_env("FLASH_TEMPERATURE", "0.3"))
        # Relaxed *retrieval* profile for the flash model only. The token
        # optimizations (eviction, passage cap, narrow top-k) starve this weak
        # model of context: it re-searches to recover what was dropped, and —
        # because each reworded query is a new key — the repeat-breaker can't
        # catch the loop. So for flash we keep every tool result (no eviction),
        # uncap passages, and widen retrieval, at the cost of more tokens on the
        # cheapest model. Stronger models keep the cost-optimized defaults above.
        # ``flash_agent_max_hops`` is a tighter backstop than the global one so a
        # residual loop still bounds fast. All values env-overridable.
        self.flash_keep_recent_tool_results: int = int(
            _env("FLASH_KEEP_RECENT_TOOL_RESULTS", "99")
        )
        self.flash_passage_max_chars: int = int(_env("FLASH_PASSAGE_MAX_CHARS", "0"))
        self.flash_final_top_k: int = int(_env("FLASH_FINAL_TOP_K", "6"))
        self.flash_fused_top_k: int = int(_env("FLASH_FUSED_TOP_K", "8"))
        self.flash_agent_max_hops: int = int(_env("FLASH_AGENT_MAX_HOPS", "6"))

        # --- Planning turn ------------------------------------------------
        # The tool-less planning turn runs before the ReAct loop. Its plan is
        # appended to ``contents`` and re-sent on every subsequent hop, so it is
        # pure overhead on top of the loop. Two knobs keep it cheap:
        #   • run it on a lighter model (a 3-5 sentence plan doesn't need the full
        #     generation model) — a straight cost cut with no change to the loop;
        #   • skip it entirely for trivial short messages (greetings, one-line
        #     lookups the ReAct prompt already handles). ``plan_min_chars`` is the
        #     length below which planning is skipped when there are no attachments;
        #     0 disables the skip (plan always runs, just on the cheaper model).
        self.plan_model: str = _env("PLAN_MODEL", "gemini-3.1-flash-lite")
        self.plan_min_chars: int = int(_env("PLAN_MIN_CHARS", "0"))

        # Context-window control on the ReAct loop: each retrieved passage set is
        # re-sent on every later hop, so a multi-search run pays for early results
        # again and again. Once a result is superseded, compact all but the most
        # recent ``keep_recent_tool_results`` down to a short stub. Kept
        # conservative (>=1) so the model never loses the context it is actively
        # reasoning over — evicting too aggressively makes it re-search and can
        # push it into the force-answer path with incomplete evidence.
        self.keep_recent_tool_results: int = int(_env("KEEP_RECENT_TOOL_RESULTS", "2"))

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
        self.fused_top_k: int = int(_env("FUSED_TOP_K", "8"))
        # Passages the reranker keeps and the agent actually sees.
        self.final_top_k: int = int(_env("FINAL_TOP_K", "4"))
        # Per-passage character cap handed to the agent. Parent-document retrieval
        # returns whole pages (``parent_chunk_tokens`` ~1200 tokens ≈ 4800 chars);
        # that full page is re-sent on every subsequent ReAct hop, so an uncapped
        # passage dominates the token bill. Above this cap we drop back to the
        # matched child span (the actually-relevant text), then hard-truncate as a
        # final guard. 0 = uncapped (old behaviour).
        self.passage_max_chars: int = int(_env("PASSAGE_MAX_CHARS", "1400"))

        # --- Observability ------------------------------------------------
        # Stdlib logging threshold; records below this never reach Logfire.
        self.log_level: str = _env("LOG_LEVEL", "INFO").upper()

        # --- CORS -----------------------------------------------------
        # Comma-separated list of extra allowed origins (e.g. the deployed
        # frontend's URL), added on top of the localhost defaults main.py
        # always allows for local dev.
        self.allowed_origins: list[str] = [
            origin.strip()
            for origin in _env("ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]

    def is_flash_guard_model(self, model: str | None) -> bool:
        """True only for the weak flash model the loop-guards target.

        Matched by substring so a versioned id (…-preview) still trips it, but a
        ``*-lite`` variant is explicitly excluded: ``gemini-3.1-flash-lite`` (the
        cheaper planning/graph/rerank model) — and any future
        ``gemini-3.5-flash-lite`` — is a different model that must keep the
        default behaviour, never the relaxed flash profile or the thinking cap.
        """
        m = model or ""
        return self.flash_guard_model in m and "lite" not in m

    def retrieval_profile(self, model: str | None) -> RetrievalProfile:
        """Resolve the retrieval/eviction/hop knobs for the active generation model.

        gemini-3.5-flash gets the relaxed anti-loop profile (see the ``flash_*``
        fields); every other model gets the cost-optimized defaults.
        """
        if self.is_flash_guard_model(model):
            return RetrievalProfile(
                keep_recent_tool_results=self.flash_keep_recent_tool_results,
                passage_max_chars=self.flash_passage_max_chars,
                final_top_k=self.flash_final_top_k,
                fused_top_k=self.flash_fused_top_k,
                agent_max_hops=self.flash_agent_max_hops,
            )
        return RetrievalProfile(
            keep_recent_tool_results=self.keep_recent_tool_results,
            passage_max_chars=self.passage_max_chars,
            final_top_k=self.final_top_k,
            fused_top_k=self.fused_top_k,
            agent_max_hops=self.agent_max_hops,
        )

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
