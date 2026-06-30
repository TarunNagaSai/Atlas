export type Role = "user" | "assistant";

export interface AgentStep {
  name: string;
  args?: Record<string, unknown>;
  /** Undefined while the result is still streaming. */
  result?: string;
}

/**
 * One entry in the agent's reasoning timeline (the "thinking" panel shown above
 * an answer). Mirrors the SSE event vocabulary so the same shape drives both
 * live streaming and replayed history:
 *
 * - `plan` / `thought` — streamed prose; consecutive chunks of the same kind are
 *   coalesced into one entry (its `text` grows token-by-token).
 * - `tool_call` / `tool_result` — a search the agent ran and what it returned;
 *   each is its own entry.
 */
export type ThinkingStep =
  | { kind: "plan"; text: string }
  | { kind: "thought"; text: string }
  | { kind: "tool_call"; name: string; args: Record<string, unknown> }
  | { kind: "tool_result"; name: string; result: string };

export interface Citation {
  id: string;
  /** Source document the snippet came from. */
  source: string;
  /** Retrieved text chunk used to ground the answer. */
  snippet: string;
  page?: number;
}

/** Lightweight attachment descriptor shown on a sent user message. */
export interface MessageAttachment {
  name: string;
  /** Coarse kind, drives the chip icon. Mirrors lib/attachments AttachmentKind. */
  kind: "image" | "pdf" | "word" | "excel";
  size: number;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  /** Grounding sources surfaced beneath an assistant answer. */
  citations?: Citation[];
  /** Tool calls the agent made on this turn, in order. */
  steps?: AgentStep[];
  /**
   * The agent's reasoning timeline for this turn (plan → thoughts → tool steps),
   * in order. Drives the collapsible "thinking" panel above the answer.
   */
  thinking?: ThinkingStep[];
  /** Files the user attached to this turn (user messages only). */
  attachments?: MessageAttachment[];
  /** Streaming / awaiting-backend state. */
  pending?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  updatedAt: number;
  /** Short preview of the last exchange. */
  preview?: string;
}

export type FileStatus = "ready" | "processing" | "error";

export interface RagFile {
  id: string;
  name: string;
  size: number;
  status: FileStatus;
  /** Number of indexed vector chunks. */
  chunks?: number;
  addedAt?: number;
}
