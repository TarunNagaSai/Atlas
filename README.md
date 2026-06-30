# Atlas

A **financial RAG assistant over Google Gemini**. Upload financial documents (PDF /
DOCX / text), turn them into embeddings in a pgvector store, and ask questions answered
by a streaming ReAct agent — with grounding citations surfaced in the UI.

The project is a monorepo with two halves:

| Part | Stack | What it does |
| --- | --- | --- |
| [`atlas-backend`](./atlas-backend) | FastAPI · Python ≥3.12 · pgvector · Gemini | Document ingestion (load → chunk → embed → store) and a streaming ReAct query agent |
| [`atlas-frontend`](./atlas-frontend) | Next.js 16 · React 19 · Tailwind 4 · TypeScript | Chat UI that streams answers, shows citations, and uploads documents into the knowledge base |

## Architecture at a glance

```
┌─────────────────┐      SSE / multipart      ┌──────────────────────┐
│  atlas-frontend  │ ───────────────────────▶ │     atlas-backend     │
│  (Next.js chat)  │                          │       (FastAPI)        │
│                  │ ◀─────────────────────── │                        │
└─────────────────┘   streamed answer +       │  ┌──────────────────┐  │
                       citations              │  │ Ingestion        │  │
                                              │  │ load→chunk→embed │  │
                                              │  └────────┬─────────┘  │
                                              │           ▼            │
                                              │     pgvector store      │
                                              │           ▲            │
                                              │  ┌────────┴─────────┐  │
                                              │  │ ReAct agent      │  │
                                              │  │ over Gemini      │  │
                                              │  └──────────────────┘  │
                                              └──────────────────────┘
```

- **Ingestion** (`atlas-backend/app/rag/`) — column-aware PDF extraction, a
  page-as-parent chunking strategy, and a `HybridStore` (dense cosine + Postgres FTS,
  RRF-fused) over pgvector.
- **Query** (`atlas-backend/app/agent/`) — a streaming ReAct loop over Gemini, scoped to
  refuse non-financial questions. The frontend renders the SSE stream with citations.

## Features

### Ingestion & Retrieval

- **Column-aware PDF extraction** — detects two-column layouts and crops each column so text is not interleaved across columns.
- **Page-as-parent chunking** — each page becomes one parent document; overlapping sentence-window children are indexed for retrieval and swapped back for the full parent text at generation time.
- **Semantic chunker** — optional topic-shift splitter (`SemanticChunker`) that uses the embedder to split on meaning boundaries rather than fixed token windows.
- **Hybrid search** — `HybridStore` over pgvector combines dense cosine similarity, Postgres full-text search, and RRF (Reciprocal Rank Fusion) into a single ranked result set. An HNSW index keeps ANN lookup fast.
- **Idempotent ingestion** — chunks are content-hashed (`Chunk.make_id`), so re-ingesting the same document is a no-op (`ON CONFLICT DO NOTHING`).
- **Dry-run preview** — upload without `persist=true` to validate the pipeline (load → chunk → embed a sample) without touching the database.

### Agent & Tools

- **Streaming ReAct agent** — a Gemini-native function-calling loop that emits a structured `AgentStep` (thought / action / action\_input / final\_answer) on each turn, streamed as Server-Sent Events.
- **Retrieve tool** — the agent calls `retrieve` to run a hybrid search over the pgvector store and receives top-ranked parent-page passages with citations, grounding its answer in real figures.
- **GraphRAG** — a per-book knowledge graph built at ingestion time (entity–relation triples extracted by Gemini, stitched into a `networkx` graph with community detection and summarised embeddings). The agent can call `graph_search` in two modes:
  - `local` — walks the graph from named entities to gather specific facts and how they connect.
  - `global` — returns book-wide thematic summaries for high-level questions that span the whole document.
- **Cooperative stream cancellation** — a `CancellationRegistry` lets the frontend POST to `/chat/cancel` to tear down an in-flight agent loop and Gemini socket cleanly; the stream emits a `cancelled` SSE event rather than an error.
- **Multimodal attachments** — chat messages can include attached files alongside the question:
  - Images and PDFs are sent to Gemini as native `inline_data` parts (the model sees charts, scanned pages, layout).
  - DOCX and XLSX files have their text/tables extracted and sent as a plain-text part.

### Chat & History

- **Postgres-backed chat history** — every conversation is persisted across three tables (`chats`, `chat_steps`). Turns group a user prompt, the agent's reasoning trace, and the final assistant reply under a shared `turn_id`.
- **Dual storage modes** — controlled by `NEXT_PUBLIC_CHAT_STORAGE` / `X-Chat-Storage`:
  - `db` — the backend persists every turn; the history sidebar and session replay load from Postgres.
  - `client` — the browser owns the transcript in `localStorage`; the backend stores nothing.
- **Session management API** — `GET /chat/sessions` lists all conversations; `GET /chat/sessions/{id}` replays a full conversation with its reasoning trace.
- **Visitor API key** — visitors can supply their own Gemini API key via the UI (stored in `sessionStorage`, sent as `X-Gemini-Api-Key`). The backend substitutes it for the server key on that request.

### Frontend UI

- **Streaming chat** — answers appear token-by-token via SSE; a cancel button stops generation mid-stream.
- **Thinking steps panel** — collapsible trace of the agent's reasoning (thoughts, tool calls, tool results) shown alongside each assistant reply.
- **Token usage badge** — displays total input + output tokens consumed in the current session.
- **Book picker** — dropdown to scope the chat to a specific ingested book; the backend filters retrieval to that `book_id`.
- **RAG panel (knowledge base sidebar)** — drag-and-drop or browse to upload PDF / TXT / MD / DOCX files; each file shows processing → ready with its real chunk count (or error on failure).
- **Chat history sidebar** — lists past conversations; clicking one replays the full session including reasoning traces.
- **Model selector** — switch between Gemini models from the settings modal without restarting the server.
- **API key modal** — prompts for and stores the visitor's Gemini API key; auto-re-prompts when the backend reports the key missing or invalid.
- **About modal** — tabbed panel with an overview, the full tech stack, and developer info.
- **Markdown rendering** — assistant answers are rendered as rich markdown (headings, tables, code blocks) via `markdown-it`.

### Observability

- **Langfuse** — LLM traces (spans, generations, tool calls, scores) sent to the Langfuse platform. Always-on; self-configured from `LANGFUSE_*` env vars.
- **Logfire** — structured instrumentation for every FastAPI request/response, Pydantic validation, psycopg2 DB query, and outbound HTTP call (Gemini API). Python `logging` is routed into the same trace stream. Console fallback when `LOGFIRE_TOKEN` is absent.

## Quick start

You need a **Google Gemini API key** and, for persistence, a **Postgres database with
the pgvector extension**.

### 1. Backend

```bash
cd atlas-backend
uv sync                 # install deps into .venv
cp .env.example .env    # then set GOOGLE_API_KEY (or GEMINI_API_KEY)

# NOTE: invoke uvicorn via `python -m` — `uv run uvicorn ...` fails to spawn.
uv run python -m uvicorn main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs> · Health: <http://localhost:8000/health>

### 2. Frontend

```bash
cd atlas-frontend
npm install
npm run dev             # http://localhost:3000
```

The UI defaults to `http://localhost:8000`; override with `NEXT_PUBLIC_API_URL` in
`atlas-frontend/.env.local`.

## Documentation

- [`atlas-backend/README.md`](./atlas-backend/README.md) — setup, env vars, API reference,
  and architecture
- [`atlas-backend/CLAUDE.md`](./atlas-backend/CLAUDE.md) — deeper architecture notes and
  current gotchas
- [`atlas-frontend/README.md`](./atlas-frontend/README.md) — frontend stack, backend
  client, and component structure

## Status

- The `retrieve` tool and `graph_search` tool are both wired into the agent.
- GraphRAG (`app/rag/graph.py`) is implemented; the `graph_search` tool exposes it to the agent.
- Schema changes (new tables, indexes) go through the **Supabase MCP `apply_migration`**, not ad-hoc SQL.
