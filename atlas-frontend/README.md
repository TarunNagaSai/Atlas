# Atlas Frontend

The web UI for **Atlas**, a financial RAG assistant. A Next.js + Tailwind chat interface
that streams answers from the [Atlas backend](../atlas-backend), shows grounding citations,
and lets you upload documents into the knowledge base.

## Stack

- **Next.js 16** (App Router) + **React 19**
- **Tailwind CSS 4**
- **TypeScript**
- `lucide-react` icons, `markdown-it` for rendering answers

## Requirements

- Node.js (the toolchain targets current LTS)
- A running [Atlas backend](../atlas-backend) (default `http://localhost:8000`)

## Setup

```bash
npm install
```

Point the UI at your backend via an environment variable (optional — defaults to
`http://localhost:8000`):

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000

# Where chat transcripts are stored (default "db"):
#   db     — the backend persists every turn (Postgres) and serves the
#            history sidebar / replay.
#   client — the browser keeps history in localStorage and replays it to the
#            backend on every query; the backend persists nothing.
# Sent to the backend per request as the X-Chat-Storage header.
NEXT_PUBLIC_CHAT_STORAGE=db
```

## Running

```bash
npm run dev      # start the dev server (http://localhost:3000)
npm run build    # production build
npm run start    # serve the production build
npm run lint     # lint
```

## How it talks to the backend

All backend calls live in [`lib/api.ts`](./lib/api.ts):

- **`streamAsk(question, handlers)`** — POSTs the question and parses the Server-Sent
  Events stream, dispatching `onChunk` / `onSources` / `onDone` / `onError`. Supports
  cancellation via an `AbortSignal`.
- **`uploadDocument(file, opts)`** — POSTs a multipart file to `/documents/upload` and
  returns the ingest report (`n_chunks`, sample chunks, embed dim). Defaults to
  `persist: true` (embed every chunk into pgvector); pass `persist: false` for a dry-run
  preview. Surfaces the backend's error `detail` on failure.

## Structure

```
app/            App Router pages (page.tsx = the chat shell, layout, globals)
components/      chat-history, chat-input, message-bubble, rag-panel, top-bar
lib/            api.ts (backend client), utils.ts
types/          shared TypeScript types (Message, Citation, RagFile, …)
```

The `RagPanel` (right sidebar) is the knowledge-base dropzone: drop or browse for
PDF / TXT / MD / DOCX files and they're ingested through the backend, flipping from
*processing* to *ready* with their real chunk count (or *error* on failure). Each file is
uploaded independently, so one failure doesn't block the rest.
