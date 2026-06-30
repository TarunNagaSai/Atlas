export type ChatStorageMode = "db" | "client";

export function getChatStorageMode(): ChatStorageMode {
  return process.env.NEXT_PUBLIC_CHAT_STORAGE === "client" ? "client" : "db";
}

/** A prior turn replayed to the backend in client-side storage mode. */
export interface WireMessage {
  role: "user" | "assistant";
  content: string;
}

/** A conversation summary from GET /chat/sessions (history sidebar). */
export interface SessionSummary {
  session_id: string;
  /** First prompt of the conversation, used as the list title. */
  title: string;
  /** The book this conversation is scoped to (null = not pinned to one). */
  book_id: string | null;
  n_turns: number;
  /** ISO-8601 timestamps. */
  started_at: string;
  last_at: string;
}

/**
 * One step of a persisted turn — mirrors the SSE event vocabulary
 * (thought / tool_call / tool_result / usage / text / sources), so the same
 * renderer can drive both live streaming and replayed history.
 */
export interface ConversationStep {
  type: string;
  [key: string]: unknown;
}

/** One turn (prompt + answer + step trace) of a persisted conversation. */
export interface ConversationTurn {
  turn_id: string;
  prompt: string;
  answer: string;
  steps?: ConversationStep[];
}

export interface Conversation {
  session_id: string;
  turns: ConversationTurn[];
}

export interface CancelResponse {
  status: string;
  session_id: string;
}
