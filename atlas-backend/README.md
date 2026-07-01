# Atlas Backend

A FastAPI backend for a **financial RAG system over Google Gemini**. Upload financial
documents (PDF/DOCX/text), turn them into embeddings in a pgvector store, and answer
questions about them through a streaming ReAct agent.

It has two halves:

- **Ingestion** (`app/rag/`) — load → chunk → embed → store.
- **Query** (`app/agent/`, `app/routes/chat.py`) — a streaming ReAct agent over Gemini.

## Requirements

- Python **>=3.12**
- [uv](https://docs.astral.sh/uv/) for dependency/venv management
- A Google Gemini API key
- (Optional, for persistence) a Postgres database with the **pgvector** extension

## Setup

```bash
uv sync                 # install/lock deps into .venv
cp .env.example .env    # then fill in the values below
```

### Environment

Config flows through `app/schema/llm_settings.py` (`Settings`, env-driven, cached via
`get_settings()`). Loaded from `.env`.

| Variable | Purpose |
| --- | --- |
| `GOOGLE_API_KEY` **or** `GEMINI_API_KEY` | Gemini API key (one is required) |
| `GEMINI_MODEL` | Generation model |
| `EMBED_MODEL`, `EMBED_DIM` (1536), `CHUNK_TOKENS`, … | Embedding/chunking knobs |
| `DATABASE_URL` | Postgres + pgvector connection (only needed to persist) |
| `LANGFUSE_*` | Observability (always-on, self-configured) |

## Running

```bash
# NOTE: invoke uvicorn via `python -m` — `uv run uvicorn ...` fails to spawn.
uv run python -m uvicorn main:app --reload --port 8000
```

- Interactive API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Quick wiring sanity check:

```bash
uv run python -c "import main; print(sorted(main.app.openapi()['paths']))"
```

## API

| Method & path | Description |
| --- | --- |
| `GET /health` | Liveness probe |
| `POST /documents/upload` | Ingest a document (multipart `file`). Query params: `persist` (default `false` — dry-run preview, no DB writes), `semantic` (topic-shift chunker). Returns an ingest report (chunk count, sample chunks, embed dim). |
| `POST /chat/stream` | Stream the ReAct agent's answer as Server-Sent Events |

Example upload (dry-run preview — no DB needed):

```bash
curl -F "file=@report.pdf" "http://localhost:8000/documents/upload"
```

Persist into pgvector (requires a reachable `DATABASE_URL`):

```bash
curl -F "file=@report.pdf" "http://localhost:8000/documents/upload?persist=true"
```

## Architecture

**LLM layer (`app/llm/`)** — thin wrappers exposed as process-wide singletons
(`get_gemini()`, `get_embedder()`), both with `tenacity` retry. `gemini.py` does SSE
generation and constrained JSON decoding; `embedding.py` does task-typed
(`RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY`), L2-normalized embeddings.

**Ingestion (`app/rag/`)** — wired by `IngestionPipeline` (`pipeline.py`):
- `loaders.py` — column-aware PDF extraction (detects two-column layouts and crops each
  column), plus DOCX and plain text.
- `chunking.py` — **page-as-parent** strategy: each page becomes one parent; children are
  overlapping sentence windows. Retrieval matches children, generation swaps in the full
  parent text. Optional `SemanticChunker` splits on topic shifts.
- `store.py` — `HybridStore` over pgvector: dense (cosine), lexical (Postgres FTS), and
  RRF-fused `hybrid_search`, with an HNSW index.

**Query side (`app/agent/agent.py`)** — a ReAct loop; each turn produces an `AgentStep`
via constrained decoding, driven by `app/prompts/react_prompt.txt` (Atlas is scoped to
refuse non-financial questions). `chat.py` streams the output as SSE.

**Composition** — `app/api.py` builds the root router; `main.py` mounts it with CORS and a
Langfuse lifespan.

See [`CLAUDE.md`](./CLAUDE.md) for the deeper architecture notes and current gotchas.

## Linting

```bash
uvx ruff check app      # ruff is not a declared dep — run via uvx
```

## Deploying to Vercel

The app is exposed to Vercel's Python runtime via `api/index.py` (imports the `app` from
`main.py`), routed by `vercel.json` (catch-all rewrite to that function, `maxDuration: 300`).

1. `requirements.txt` is generated from `uv.lock` — regenerate it after changing dependencies:
   ```bash
   uv export --no-hashes --no-dev -o requirements.txt
   ```
2. Set these as environment variables in the Vercel project (not via `.env` — that file is
   gitignored and never deployed): `GOOGLE_API_KEY` (or `GEMINI_API_KEY`), `DATABASE_URL`,
   `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, and any other overrides from
   the table above. `ALLOWED_ORIGINS` (comma-separated) can add extra CORS origins beyond the
   defaults hardcoded in `main.py` (localhost + `atlas.avipra.com`).
3. `DATABASE_URL` must point at a reachable Postgres (the project already uses Supabase pgvector,
   which works fine from Vercel's serverless functions).
4. Deploy — Vercel auto-detects the Python function from `api/index.py` and `requirements.txt`.

**Known constraints of this setup:** the ReAct agent streams SSE over several Gemini hops per
request, which doesn't map cleanly onto serverless functions — `maxDuration` is set to Vercel's
current 300s ceiling to give long agent runs room, but very deep tool-call loops can still be cut
off. There's also no persistent connection pooling across invocations (each cold start opens its
own DB connection).

## Status / gotchas

- The agent has **no tools wired yet** — `app/tools/tools.py` is empty, so the agent
  answers only from conversation context. Wiring a `retrieve` tool over the ingestion
  store is the natural next step.
- Schema changes go through the **Supabase MCP `apply_migration`** (tracked), not ad-hoc
  SQL. The pgvector `chunks` table + HNSW index already exist.
- **GraphRAG is intentionally deferred** and should not be implemented without a prior
  design pass.
