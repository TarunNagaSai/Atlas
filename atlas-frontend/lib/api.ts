import { getApiKey } from "./api-key";
import { getSelectedBook, getSessionId } from "./session";
import type { Attachment } from "./attachments";
import type { Citation } from "@/types";
import {
  getChatStorageMode,
  type Book,
  type CancelResponse,
  type Conversation,
  type SessionSummary,
  type StreamHandlers,
  type StreamSource,
  type UploadResponse,
  type WireMessage,
  MissingApiKeyError,
  InvalidApiKeyError,
  AttachmentError,
} from "./models";

export * from "./models";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/** Attachment error `code`s the backend emits in a 400 detail object. */
const ATTACHMENT_ERROR_CODES = new Set([
  "too_large",
  "unsupported_type",
  "bad_encoding",
  "empty",
]);

function sessionHeaders(): Record<string, string> {
  const id = getSessionId();
  if (!id) return {};
  const headers: Record<string, string> = { "X-Session-Id": id };
  const book = getSelectedBook(id);
  if (book) headers["X-Book-Id"] = book;
  return headers;
}

/** Response shape of GET /books. */
interface BooksResponse {
  books: Book[];
}

export async function fetchBooks(
  opts: { signal?: AbortSignal } = {}
): Promise<Book[]> {
  const res = await fetch(`${API_URL}/books`, {
    headers: sessionHeaders(),
    signal: opts.signal,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // Non-JSON error body — fall back to the status text.
    }
    throw new Error(`Failed to load notebooks (${res.status}): ${detail}`);
  }

  const data = (await res.json()) as BooksResponse;
  return data.books ?? [];
}

export async function fetchSessions(
  opts: { limit?: number; offset?: number; signal?: AbortSignal } = {}
): Promise<SessionSummary[]> {
  const { limit = 50, offset = 0, signal } = opts;
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  const res = await fetch(`${API_URL}/chat/sessions?${params}`, {
    headers: sessionHeaders(),
    signal,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // Non-JSON error body — fall back to the status text.
    }
    throw new Error(`Failed to load conversations (${res.status}): ${detail}`);
  }

  return (await res.json()) as SessionSummary[];
}

export async function fetchConversation(
  sessionId: string,
  opts: { signal?: AbortSignal } = {}
): Promise<Conversation> {
  const res = await fetch(
    `${API_URL}/chat/sessions/${encodeURIComponent(sessionId)}`,
    { headers: sessionHeaders(), signal: opts.signal }
  );

  if (res.status === 404) {
    return { session_id: sessionId, turns: [] };
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // Non-JSON error body — fall back to the status text.
    }
    throw new Error(`Failed to load conversation (${res.status}): ${detail}`);
  }

  return (await res.json()) as Conversation;
}

export async function cancelChat(
  streamSessionId?: string,
): Promise<CancelResponse | null> {
  const headers = sessionHeaders();
  const sid = streamSessionId ?? headers["X-Session-Id"];
  if (!sid) return null;
  headers["X-Session-Id"] = sid;

  const res = await fetch(`${API_URL}/chat/cancel`, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // Non-JSON error body — fall back to the status text.
    }
    throw new Error(`Cancel failed (${res.status}): ${detail}`);
  }

  return (await res.json()) as CancelResponse;
}

export async function uploadDocument(
  file: File,
  opts: { persist?: boolean; semantic?: boolean; signal?: AbortSignal } = {}
): Promise<UploadResponse> {
  const { persist = true, semantic = false, signal } = opts;

  const params = new URLSearchParams({
    persist: String(persist),
    semantic: String(semantic),
  });

  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_URL}/documents/upload?${params}`, {
    method: "POST",
    headers: sessionHeaders(),
    body: form,
    signal,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // Non-JSON error body — fall back to the status text.
    }
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }

  return (await res.json()) as UploadResponse;
}

export async function streamAsk(
  question: string,
  handlers: StreamHandlers,
  opts: {
    signal?: AbortSignal;
    model?: string;
    conversationId?: string;
    attachments?: Attachment[];
    messages?: WireMessage[];
  } = {}
): Promise<void> {
  const {
    onChunk,
    onSession,
    onPlan,
    onThought,
    onToolCall,
    onToolResult,
    onSources,
    onUsage,
    onCancelled,
    onDone,
    onError,
  } = handlers;
  try {
    const mode = getChatStorageMode();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Chat-Storage": mode,
    };
    const browserId = getSessionId();
    const book = getSelectedBook(browserId);
    if (book) headers["X-Book-Id"] = book;
    if (opts.conversationId) headers["X-Session-Id"] = opts.conversationId;
    const apiKey = getApiKey();
    if (apiKey) headers["X-Gemini-Api-Key"] = apiKey;

    const res = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        prompt: question,
        ...(opts.model ? { model: opts.model } : {}),
        ...(opts.attachments?.length ? { attachments: opts.attachments } : {}),
        ...(opts.messages?.length ? { messages: opts.messages } : {}),
      }),
      signal: opts.signal,
    });

    if (res.status === 400) {
      const detail = await res
        .json()
        .then((b) => b?.detail)
        .catch(() => undefined);
      if (
        detail &&
        typeof detail === "object" &&
        ATTACHMENT_ERROR_CODES.has(detail.code)
      ) {
        throw new AttachmentError(detail.code, detail.message ?? "Attachment rejected.");
      }
      throw new MissingApiKeyError();
    }

    if (!res.ok || !res.body) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(`Request failed (${res.status}): ${detail}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);

        const line = frame
          .split("\n")
          .find((l) => l.startsWith("data:"));
        if (!line) continue;

        const payload = line.slice(5).trim();
        if (payload === "[DONE]") {
          onDone?.();
          return;
        }

        try {
          const event = JSON.parse(payload);
          switch (event.type) {
            case "session":
              onSession?.(event.session_id as string);
              break;
            case "text":
              onChunk(event.text as string);
              break;
            case "plan":
              onPlan?.(event.text as string);
              break;
            case "thought":
              onThought?.(event.text as string);
              break;
            case "tool_call":
              onToolCall?.({ name: event.name, args: event.args ?? {} });
              break;
            case "tool_result":
              onToolResult?.({ name: event.name, result: event.result ?? "" });
              break;
            case "sources":
              onSources?.(event.sources);
              break;
            case "usage":
              onUsage?.({
                scope: event.scope === "total" ? "total" : "turn",
                promptTokens: event.prompt_tokens ?? 0,
                thoughtsTokens: event.thoughts_tokens ?? 0,
                outputTokens: event.output_tokens ?? 0,
                totalTokens: event.total_tokens ?? 0,
              });
              break;
            case "cancelled":
              onCancelled?.();
              break;
            case "error":
              if (event.code === "invalid_api_key") {
                onError?.(new InvalidApiKeyError(event.message));
              } else {
                onError?.(
                  new Error(event.message ?? "The assistant hit an error."),
                );
              }
              return;
          }
        } catch {
          // Ignore malformed frames rather than aborting the whole stream.
        }
      }
    }
    onDone?.();
  } catch (err) {
    if ((err as Error)?.name === "AbortError") return;
    onError?.(err);
  }
}

/** Turn a backend citation string ("file.pdf#12") into a UI Citation. */
export function toCitation(src: StreamSource): Citation {
  const [source, loc] = src.citation.split("#");
  const digits = loc?.match(/\d+/)?.[0];
  const page = digits ? Number(digits) : undefined;
  return {
    id: `c${src.n}`,
    source: source || src.citation,
    snippet: "",
    page,
  };
}
