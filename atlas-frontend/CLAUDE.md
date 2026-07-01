# CLAUDE.md

This file provides guidance to Claude Code when working with code in this directory.

## What this is

Atlas frontend — a Next.js 16 / React 19 / TypeScript / Tailwind 4 single-page app that
wraps the Atlas RAG backend. The user picks a financial "notebook" (book), enters a Gemini
API key, then chats with the agent. The agent's full reasoning loop (plan → thoughts → tool
calls → answer) is streamed live and rendered in a collapsible "thinking" panel.

## Commands

```bash
bun install          # install deps (lockfile is bun.lock)
bun dev              # dev server on :3000 with hot reload
bun build            # production build
bun lint             # next lint
```

The backend must be running on `:8000` (or `NEXT_PUBLIC_API_URL`) for any API call to work.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |
| `NEXT_PUBLIC_CHAT_STORAGE` | `"db"` | `"db"` = backend owns history; `"client"` = localStorage only |

## Architecture

### Page (`app/page.tsx`)

The single root page owns all top-level state: active conversation id, session list,
setup step (book → key), RAG panel visibility, nav drawer. It orchestrates:
- `useSession` — browser session id + book choice + display name
- `useConversationUsage` — per-chat token totals
- `useApiKey` — Gemini key from sessionStorage
- `useChatStream` — the streaming hook (see below)

Session ids are minted exactly two places — on app-open and on "New analysis" (`handleNewChat`).
A turn never mints a session; it sends into the active one via `X-Session-Id`. A new chat stays
a "draft" (not listed in the sidebar) until its first turn is persisted.

### Core hook (`hooks/use-chat-stream.ts`)

Manages the live `Message[]` thread and the streaming lifecycle. `handleSend` builds the
user+pending bubble, calls `streamAsk`, and patches the pending message token-by-token as SSE
events arrive. `handleStop` fires `POST /chat/cancel` (server-side gate) **and** aborts the
`AbortController` (client-side gate). `loadMessages` replaces the thread for history replay.

Multi-turn context: the last 7 turns are serialised to `{ role, content }` and sent as
`messages` in the POST body (client-storage mode) or replayed from the backend (DB mode).

### API client (`lib/api.ts`)

Thin fetch wrappers over the backend:
- `streamAsk` — `POST /chat/stream`, parses the SSE frame-by-frame, dispatches typed
  `StreamHandlers` callbacks (`onChunk`, `onPlan`, `onThought`, `onToolCall`, `onToolResult`,
  `onSources`, `onUsage`, `onCancelled`, `onDone`, `onError`). Raises `MissingApiKeyError` on
  HTTP 400, `InvalidApiKeyError` on `invalid_api_key` SSE events, `AttachmentError` on
  attachment-specific 400 detail codes.
- `fetchBooks` — `GET /books`
- `fetchSessions` / `fetchConversation` — `GET /chat/sessions[/:id]`
- `cancelChat` — `POST /chat/cancel`
- `uploadDocument` — `POST /documents/upload`

Wire types (`lib/models/`) are re-exported from `lib/api.ts` so callers import from one place.

### State slices (`lib/`)

| Module | Storage | Lifetime | Purpose |
|---|---|---|---|
| `session.ts` | `localStorage` | permanent | Browser session id, book choice, display name, per-conversation token totals, per-chat composer drafts |
| `api-key.ts` | `sessionStorage` | tab | Gemini API key — cleared on tab close, re-prompted on auth errors |
| `local-history.ts` | `localStorage` | permanent | Full `Message[]` transcripts + sidebar index (client-storage mode only) |
| `settings.ts` | — | build-time | `MODELS` list, `DEFAULT_MODEL`, time constants |
| `attachments.ts` | — | — | File validation, MIME→kind mapping, base64 encoding |
| `validate-gemini-key.ts` | — | — | Probes Google's API to confirm a key is live before saving |

Session state is keyed by the browser session id (a UUID in localStorage). Book choice and
display name are written once at the picker and never re-asked for the same session id.
Token usage is keyed by *conversation* id so switching chats shows that chat's own total.

### Types

- `types/index.ts` — UI types: `Message`, `AgentStep`, `ThinkingStep`, `Citation`,
  `MessageAttachment`, `ChatSession`, `RagFile`
- `lib/models/` — wire types: `Book`, `SessionSummary`, `Conversation`, `ConversationTurn`,
  `ConversationStep`, `StreamHandlers`, `StreamSource`, `WireMessage`, error classes

`ThinkingStep` mirrors the SSE event vocabulary: `plan`, `thought`, `tool_call`, `tool_result`.
Consecutive `plan`/`thought` chunks of the same kind are coalesced into one growing entry by
`appendThinking` (in the hook) and `thinkingFromConversation` (for history replay).

### Components (`components/`)

| Component | Role |
|---|---|
| `BookPicker` | Two-step setup modal: book selection → Gemini key entry. Controls `setupStep` (`"book"` → `"key"` → `null`). |
| `ChatHistory` | Left-sidebar drawer: session list, "New analysis" button, book switcher, inline key entry. |
| `MessageBubble` | Renders one message: markdown (via `lib/markdown.ts`), collapsible `ThinkingSteps`, `TokenUsage`, citation list. |
| `ChatInput` | Composer with auto-resize, model picker, file-attach chip row, send/stop button. Exposes `ChatInputHandle` (`.setText`) for rollback on auth errors. |
| `TopBar` | Header: active chat title, RAG-panel toggle, nav-open button. |
| `EmptyState` | Shown on a blank new chat; suggested-question chips call `onPick`. |
| `RagPanel` | Right-side panel: agent tool-call steps for the latest assistant turn. Inline on desktop (`lg:`), overlay drawer on mobile. |
| `ThinkingSteps` | Collapsible reasoning timeline inside a message: plan prose, thought prose, tool-call+result pairs. |
| `TokenUsage` | Compact token counter under an assistant bubble. |
| `SettingsModal` | Model picker + key management UI, opened from `ChatHistory`. |
| `ApiKeyModal` | Standalone key-entry modal (re-shown on auth errors). |
| `about/about-modal.tsx` | Product info overlay. |

### Attachment flow

Files travel **base64-encoded inside the POST body** — there is no separate upload endpoint
for chat attachments. `lib/attachments.ts` validates (type, size ≤ 4 MB, non-empty) and
encodes client-side before `streamAsk` sends. The server decodes and forwards to Gemini.
Supported: PNG, JPEG, WEBP, HEIC/HEIF (native Gemini), PDF (native Gemini), .docx, .xlsx
(text-extracted server-side). Legacy .xls is explicitly rejected with a friendly message.

### Storage modes

`NEXT_PUBLIC_CHAT_STORAGE` selects how transcripts are persisted:
- **`"db"` (default)** — the backend owns history. The sidebar fetches from
  `/chat/sessions`; clicking a session fetches `/chat/sessions/:id` and replays it.
- **`"client"`** — the browser owns everything. `saveLocalChat` / `listLocalChats` /
  `loadLocalChat` in `lib/local-history.ts` write to localStorage. The sidebar reads from
  there; replays are synchronous. No backend session calls are made.

The mode is read once at module level (`getChatStorageMode()`, from `lib/models/chat.ts`) and
is consistent for the lifetime of the page load.

### Responsive layout

The `RagPanel` and nav `ChatHistory` are inline on desktop (`lg:` = 1024 px) and overlay
drawers on mobile. A `ResizeObserver`-free approach is used: a `resize` event listener in
`page.tsx` tracks breakpoint crossings and auto-opens/closes the panel — only on an actual
crossing, leaving manual toggles intact between them.

## Conventions

- `"use client"` at the top of every file that uses React hooks or browser APIs.
- UI types in `types/index.ts`; API wire types in `lib/models/` (re-exported via `lib/api.ts`).
- CSS custom properties for theming: `var(--background)`, `var(--surface-2)`, etc.
- `@/` path alias for imports from the project root.
- Vercel Analytics is instrumented at key user events (`track("message_sent")`,
  `track("generation_stopped")`).
