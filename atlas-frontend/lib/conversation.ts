import {
  toCitation,
  type ConversationStep,
  type ConversationTurn,
  type StreamSource,
} from "@/lib/api";
import type { AgentStep, Message, ThinkingStep } from "@/types";

/** Map a persisted conversation's turns into the flat Message list the thread renders. */
export function turnsToMessages(turns: ConversationTurn[]): Message[] {
  const out: Message[] = [];
  let t = Date.now();
  for (const turn of turns) {
    out.push({
      id: `${turn.turn_id}:user`,
      role: "user",
      content: turn.prompt,
      createdAt: t++,
    });
    out.push({
      id: `${turn.turn_id}:assistant`,
      role: "assistant",
      content: turn.answer,
      createdAt: t++,
      citations: citationsFromSteps(turn.steps),
      steps: stepsFromConversation(turn.steps),
      thinking: thinkingFromConversation(turn.steps),
    });
  }
  return out;
}

/** Pair up `tool_call`/`tool_result` steps from a persisted turn into AgentSteps. */
export function stepsFromConversation(
  steps: ConversationStep[] | undefined,
): AgentStep[] | undefined {
  const toolSteps = steps?.filter(
    (s) => s.type === "tool_call" || s.type === "tool_result",
  );
  if (!toolSteps?.length) return undefined;
  const out: AgentStep[] = [];
  for (const s of toolSteps) {
    if (s.type === "tool_call") {
      out.push({
        name: s.name as string,
        args: s.args as Record<string, unknown>,
      });
    } else {
      const last = out.at(-1);
      if (last && !last.result) last.result = s.result as string;
    }
  }
  return out.length ? out : undefined;
}

/**
 * Rebuild the reasoning timeline (plan → thoughts → tool steps) from a persisted
 * turn's steps, so a replayed conversation re-renders the same "thinking" panel.
 * Consecutive `plan`/`thought` chunks are coalesced into one entry.
 */
export function thinkingFromConversation(
  steps: ConversationStep[] | undefined,
): ThinkingStep[] | undefined {
  if (!steps?.length) return undefined;
  const out: ThinkingStep[] = [];
  for (const s of steps) {
    if (s.type === "plan" || s.type === "thought") {
      const last = out.at(-1);
      const text = (s.text as string) ?? "";
      if (last && last.kind === s.type) last.text += text;
      else out.push({ kind: s.type, text });
    } else if (s.type === "tool_call") {
      out.push({
        kind: "tool_call",
        name: s.name as string,
        args: (s.args as Record<string, unknown>) ?? {},
      });
    } else if (s.type === "tool_result") {
      out.push({
        kind: "tool_result",
        name: s.name as string,
        result: (s.result as string) ?? "",
      });
    }
  }
  return out.length ? out : undefined;
}

/** Pull citations out of a turn's `sources` step, if the backend persisted one. */
export function citationsFromSteps(steps: ConversationStep[] | undefined) {
  const sourcesStep = steps?.find((s) => s.type === "sources");
  const sources = sourcesStep?.sources as StreamSource[] | undefined;
  if (!Array.isArray(sources)) return undefined;
  return sources.map(toCitation);
}
