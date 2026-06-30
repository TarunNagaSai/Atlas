/** A grounding source as emitted by the backend's SSE `sources` event. */
export interface StreamSource {
  n: number;
  citation: string;
  cited: boolean;
}

/** Token usage from the backend's SSE `usage` event. */
export interface StreamUsage {
  scope: "turn" | "total";
  promptTokens: number;
  thoughtsTokens: number;
  outputTokens: number;
  totalTokens: number;
}

/** A tool the agent invoked mid-run (SSE `tool_call` event). */
export interface StreamToolCall {
  name: string;
  args: Record<string, unknown>;
}

/** The result of a tool call (SSE `tool_result`, follows its `tool_call`). */
export interface StreamToolResult {
  name: string;
  /** Can be long (e.g. retrieved passages) — best shown collapsed. */
  result: string;
}

export interface StreamHandlers {
  onChunk: (text: string) => void;
  /** The per-stream session id (first `session` event) — needed to cancel. */
  onSession?: (sessionId: string) => void;
  onPlan?: (text: string) => void;
  onThought?: (text: string) => void;
  onToolCall?: (call: StreamToolCall) => void;
  onToolResult?: (result: StreamToolResult) => void;
  onSources?: (sources: StreamSource[]) => void;
  onUsage?: (usage: StreamUsage) => void;
  onCancelled?: () => void;
  onDone?: () => void;
  onError?: (err: unknown) => void;
}
