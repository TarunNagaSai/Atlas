# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Atlas is a FastAPI backend for a **financial RAG system over Google Gemini**: upload financial
documents (PDF/DOCX/text), turn them into embeddings in a pgvector store, and answer questions
about them through a ReAct agent. It has two halves:

- **Ingestion** (`app/rag/`): load → chunk → embed → store. Newer; built as a port of the
  sibling repo `~/Projects/ai/rag/advanced_rag` (the fuller reference implementation — consult it
  when extending retrieval/graph/agent features).
- **Query** (`app/agent/`, `app/routes/chat.py`): a streaming ReAct agent over Gemini.

## Commands

Package/venv is managed by **uv** (Python >=3.12). There is no test suite or configured linter in
`pyproject.toml` yet.

```bash
uv sync                                   # install/lock deps into .venv
uv run python -m uvicorn main:app --reload --port 8000   # run the API (see gotcha below)
uvx ruff check app                        # lint (ruff isn't a declared dep; run via uvx)
```

- **Gotcha:** `uv run uvicorn ...` fails ("Failed to spawn: uvicorn"). Always invoke via
  `uv run python -m uvicorn`.
- Interactive API docs at `/docs` once running. Health at `/health`.
- Quick import/wiring sanity check: `uv run python -c "import main; print(sorted(main.app.openapi()['paths']))"`.

## Configuration

All config flows through `app/schema/llm_settings.py` → `Settings` (an env-driven object behind an
`lru_cache`d `get_settings()`). Env is loaded from `.env` via `python-dotenv`.

- The Gemini API key is read as **`GOOGLE_API_KEY` OR `GEMINI_API_KEY`** (`require_key()` raises if
  neither is set). `GEMINI_MODEL` selects the generation model.
- Embedding/chunking knobs (`EMBED_MODEL`, `EMBED_DIM` default 1536, `CHUNK_TOKENS`, etc.) and
  `DATABASE_URL` are all env-overridable.
- `get_settings()` is cached — when changing env at runtime in a script, call
  `get_settings.cache_clear()` to pick up new values.

## Architecture

**LLM layer (`app/llm/`)** — two thin wrappers, each exposed as a process-wide singleton
(`get_gemini()`, `get_embedder()`), both using `tenacity` retry:
- `gemini.py`: `generate_content_stream_async` (SSE generation) and `generate_structured`
  (constrained JSON decoding into a Pydantic schema — this is how the agent produces each step).
- `embedding.py`: task-typed embeddings (`RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY` — asymmetric on
  purpose), batched with a one-at-a-time fallback, **always L2-normalized** so cosine == dot product
  (required after Matryoshka truncation to `EMBED_DIM`).

**Ingestion (`app/rag/`)** — pipeline stages, wired together by `IngestionPipeline` in
`pipeline.py`:
- `loaders.py`: `_load_pdf` does **column-aware extraction** (detects two-column layouts by the gap
  between halves and crops each column so text isn't interleaved). Also DOCX and plain text.
- `chunking.py`: **page-as-parent** strategy — each Document (one PDF page) becomes one parent;
  children are overlapping sentence windows. Retrieval matches children; generation swaps in the full
  `parent_text`. `SemanticChunker` is an optional topic-shift splitter (uses the embedder).
- `store.py`: `HybridStore` over **pgvector** — DDL/HNSW index on first use, plus dense (cosine
  `<=>`), lexical (Postgres FTS), and RRF-fused `hybrid_search`. References `vector`/`vector_cosine_ops`
  **unqualified**, relying on `extensions` being on the DB `search_path`.
- `IngestionPipeline.ingest(...)` has two modes: **dry-run** (default — load→chunk→embed a small
  sample to validate wiring, no DB writes) and **persist=True** (embed all, write to store; raises a
  clear error surfaced as 503 if the DB is unreachable).

**Data model (`app/schema/documents.py`)** — `Document` → `Chunk` (with `parent_text` for
parent-document retrieval) → `Scored`. `Chunk.make_id` is a content hash, so re-ingesting the same
text is idempotent (`ON CONFLICT DO NOTHING`).

**Query side (`app/agent/agent.py`)** — a ReAct loop: each turn calls `generate_structured` into the
`AgentStep` schema (`thought`/`action`/`action_input`/`final_answer`), driven by the system prompt in
`app/prompts/react_prompt.txt` (Atlas is scoped to refuse non-financial questions). `chat.py` streams
the agent's output as SSE.

**Composition** — `app/api.py` builds the root `APIRouter` (root/health) and includes feature routers
(`chat`, `documents`); `main.py` mounts it on the `FastAPI` app with CORS (localhost:3000) and a
lifespan that wires Langfuse.

**Observability** — `app/observability/langfuse.py` is wiring only (singleton client + lifespan that
auth-checks on boot and flushes on shutdown). The actual spans/generations live in the route/agent
code, not in that module. Tracing is always-on, self-configured from `LANGFUSE_*` env.

## Important current state / gotchas

- **The agent has no tools wired.** `app/tools/tools.py` is empty and `run_tool` doesn't exist, so
  `agent.py` falls back to `_run_tool = None` — the agent answers only from conversation context. The
  ingestion store/retriever is **not yet connected to the agent**; wiring a `retrieve` tool is the
  natural next step.
- **Database is Supabase pgvector** (session pooler, `ap-south-1`, see `.env`). The `public.chunks`
  table + HNSW index + `vector` extension are already created (RLS enabled, no policies — locked to
  the API, bypassed by the postgres connection). The app's `CREATE ... IF NOT EXISTS` DDL no-ops
  against it. Make schema changes via the **Supabase MCP `apply_migration`** (tracked), not ad-hoc SQL.
  Direct-connection host is IPv6-only; the pooler URL in `.env` is the IPv4 path.
- **GraphRAG is intentionally deferred** (the reference `graph.py` was only a stub; the knowledge-gate
  for it is not cleared). Do not implement it without the `/learn` step first — see the project memory
  `graphrag-deferred-learn-then-build.md`.

## Conventions

- Every module starts with `from __future__ import annotations`.
- New external dependencies (clients, DB) are accessed through cached module-level `get_X()` singletons.
- New tunables go into `Settings` as env-overridable fields, not hardcoded at call sites.
- New routers live in `app/routes/<name>.py` as an `APIRouter(prefix=..., tags=...)` and are included
  in `app/api.py`.
