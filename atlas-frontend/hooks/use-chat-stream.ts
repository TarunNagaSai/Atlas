"use client";

import { useCallback, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import {
  AttachmentError,
  cancelChat,
  InvalidApiKeyError,
  isApiKeyError,
  streamAsk,
  toCitation,
  type WireMessage,
} from "@/lib/api";
import { classifyFile, fileToAttachment } from "@/lib/attachments";
import { uid } from "@/lib/utils";
import type { ChatInputHandle } from "@/components/chat-input";
import type { Message, MessageAttachment, ThinkingStep } from "@/types";

/**
 * Fold one streamed thinking entry into a turn's reasoning timeline. Consecutive
 * `plan`/`thought` chunks of the same kind are coalesced into a single growing
 * entry; tool calls and results are each appended as their own entry.
 */
function appendThinking(
  steps: ThinkingStep[] | undefined,
  step: ThinkingStep,
): ThinkingStep[] {
  const list = steps ?? [];
  const last = list[list.length - 1];
  if (
    (step.kind === "plan" || step.kind === "thought") &&
    last &&
    last.kind === step.kind
  ) {
    return [...list.slice(0, -1), { ...last, text: last.text + step.text }];
  }
  return [...list, step];
}

const WINDOW_TURNS = 7;

/**
 * Flatten the rendered thread into the `{ role, content }` turns the backend
 * replays for context. Caps at the last WINDOW_TURNS turns so the model
 * receives a bounded context window regardless of conversation length.
 * Empty/still-streaming bubbles are dropped.
 */
function toWireMessages(messages: Message[]): WireMessage[] {
  const settled = messages.filter(
    (m) => !m.pending && m.content.trim().length > 0,
  );
  return settled
    .slice(-WINDOW_TURNS * 2)
    .map((m) => ({ role: m.role, content: m.content }));
}

interface Params {
  /** Fold a turn's token counts into the given conversation's running total. */
  record: (conversationId: string, input: number, output: number) => void;
  chatInputRef: React.RefObject<ChatInputHandle | null>;
  /**
   * The conversation this turn belongs to. The page owns this id — it mints one
   * on app-open and on "New analysis" — so a turn never creates a session; it
   * just sends into the active one (as X-Session-Id). Null only in the brief
   * window before the page has resolved the id, during which sends are ignored.
   */
  conversationId: string | null;
  /** Called when a turn settles (done/error/cancel) so the sidebar can refresh. */
  onTurnComplete?: () => void;
  /**
   * Called when the backend rejects the request for a missing/invalid Gemini
   * key. The turn is rolled back (pending bubble dropped, prompt restored to the
   * input) so the visitor can resend after the key prompt is satisfied.
   * `invalid` is true when a key was attached but rejected, false when none
   * reached the backend (HTTP 400).
   */
  onAuthError?: (invalid: boolean) => void;
}

export function useChatStream({
  record,
  chatInputRef,
  conversationId,
  onTurnComplete,
  onAuthError,
}: Params) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);

  // Latest transcript, readable synchronously inside handleSend (state would be
  // stale there). Used to snapshot the prior turns we replay to the backend.
  const messagesRef = useRef<Message[]>(messages);
  messagesRef.current = messages;

  // Handles on the in-flight turn so the Stop button can cancel it.
  const abortRef = useRef<AbortController | null>(null);
  const streamSessionIdRef = useRef<string | null>(null);
  const pendingIdRef = useRef<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const userTextRef = useRef("");
  const gotChunkRef = useRef(false);

  const handleSend = useCallback(
    (text: string, model?: string, files: File[] = []) => {
      // The page owns the conversation id (minted on app-open / New analysis).
      // If it hasn't resolved yet there's nothing to send into — ignore.
      if (!conversationId) return;
      track("message_sent", { char_count: text.length, attachments: files.length });

      // Snapshot the conversation so far (before this turn's bubbles are added)
      // to replay to the backend in client-side storage mode.
      const priorMessages = toWireMessages(messagesRef.current);

      // Lightweight descriptors so the sent bubble can show what was attached
      // (kind drives the icon). The raw bytes are encoded separately below.
      const attachmentMeta: MessageAttachment[] = files.map((f) => ({
        name: f.name,
        kind: classifyFile(f) ?? "pdf",
        size: f.size,
      }));

      const userMsg: Message = {
        id: uid(),
        role: "user",
        content: text,
        createdAt: Date.now(),
        ...(attachmentMeta.length ? { attachments: attachmentMeta } : {}),
      };
      // Reuse the active conversation id (guaranteed non-null by the guard
      // above). A turn never mints a session — the page does, so the same chat
      // is reused for every turn and the sidebar entry only materializes once
      // this turn's content is persisted.
      const sessionId = conversationId;

      const pendingId = uid();
      const pendingMsg: Message = {
        id: pendingId,
        role: "assistant",
        content: "",
        createdAt: Date.now() + 1,
        pending: true,
      };
      setMessages((prev) => [...prev, userMsg, pendingMsg]);
      setThinking(true);

      const patch = (fn: (m: Message) => Message) =>
        setMessages((prev) => prev.map((m) => (m.id === pendingId ? fn(m) : m)));

      pendingIdRef.current = pendingId;
      userIdRef.current = userMsg.id;
      userTextRef.current = text;
      gotChunkRef.current = false;
      streamSessionIdRef.current = null;
      const controller = new AbortController();
      abortRef.current = controller;

      const settle = () => {
        if (abortRef.current === controller) {
          abortRef.current = null;
          pendingIdRef.current = null;
          userIdRef.current = null;
          gotChunkRef.current = false;
          streamSessionIdRef.current = null;
        }
        setThinking(false);
        onTurnComplete?.();
      };

      const run = async () => {
        // Encode attachments to base64 before opening the stream. A read failure
        // here means the turn never starts — surface it like any other error.
        let attachments;
        try {
          attachments = files.length
            ? await Promise.all(files.map(fileToAttachment))
            : undefined;
        } catch {
          patch((m) => ({
            ...m,
            pending: false,
            content: "Couldn't read one of the attached files. Please try again.",
          }));
          settle();
          return;
        }

        streamAsk(
        text,
        {
          onSession: (sid) => {
            // The conversation id is UI-owned (minted above and sent as
            // X-Session-Id), so we only track the per-stream id here for
            // cancellation — no adoption of a server-minted id needed.
            streamSessionIdRef.current = sid;
          },
          onChunk: (chunk) => {
            gotChunkRef.current = true;
            patch((m) => ({ ...m, pending: false, content: m.content + chunk }));
        },
          onPlan: (text) =>
            patch((m) => ({
              ...m,
              thinking: appendThinking(m.thinking, { kind: "plan", text }),
            })),
          onThought: (text) =>
            patch((m) => ({
              ...m,
              thinking: appendThinking(m.thinking, { kind: "thought", text }),
            })),
          onSources: (sources) =>
            patch((m) => ({ ...m, citations: sources.map(toCitation) })),
          onToolCall: (call) =>
            patch((m) => ({
              ...m,
              steps: [...(m.steps ?? []), { name: call.name, args: call.args }],
              thinking: appendThinking(m.thinking, {
                kind: "tool_call",
                name: call.name,
                args: call.args,
              }),
            })),
          onToolResult: (res) =>
            patch((m) => {
              // Mirror the result into the agent-flow `steps` (RagPanel) by
              // filling the most recent still-pending tool call…
              const steps = m.steps;
              let nextSteps = steps;
              if (steps) {
                const idx = steps.map((s) => !s.result).lastIndexOf(true);
                if (idx !== -1) {
                  nextSteps = steps.map((s, i) =>
                    i === idx ? { ...s, result: res.result } : s,
                  );
                }
              }
              // …and append it as its own entry in the thinking timeline.
              return {
                ...m,
                steps: nextSteps,
                thinking: appendThinking(m.thinking, {
                  kind: "tool_result",
                  name: res.name,
                  result: res.result,
                }),
              };
            }),
          onUsage: (u) => {
            // Fold the turn's final totals into the session counter. The
            // incremental per-turn events were only used for live limiting,
            // which is gone now.
            if (u.scope === "turn") return;
            // Attribute the usage to this turn's conversation (sessionId),
            // which is correct even if the active chat has since changed.
            record(sessionId, u.promptTokens, u.outputTokens + u.thoughtsTokens);
          },
          onDone: () => {
            patch((m) => ({ ...m, pending: false }));
            settle();
          },
          onError: (err) => {
            // A missing/invalid key isn't a chat failure — roll the turn back
            // and hand off to the key prompt so the visitor can resend.
            if (isApiKeyError(err)) {
              setMessages((prev) =>
                prev.filter((m) => m.id !== pendingId && m.id !== userMsg.id),
              );
              chatInputRef.current?.setText(text);
              settle();
              onAuthError?.(err instanceof InvalidApiKeyError);
              return;
            }
            // A rejected attachment carries a friendly, specific message — show
            // it as-is rather than the generic backend-failure copy.
            if (err instanceof AttachmentError) {
              patch((m) => ({ ...m, pending: false, content: err.message }));
              settle();
              return;
            }
            patch((m) => ({
              ...m,
              pending: false,
              content:
                m.content ||
                `Sorry — something went wrong reaching the backend.\n\n${
                  err instanceof Error ? err.message : String(err)
                }`,
            }));
            settle();
          },
        },
        {
          signal: controller.signal,
          conversationId: sessionId,
          ...(model ? { model } : {}),
          ...(attachments ? { attachments } : {}),
          ...(priorMessages.length ? { messages: priorMessages } : {}),
        },
        );
      };

      void run();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [record, conversationId, onTurnComplete, onAuthError, chatInputRef],
  );

  const handleStop = useCallback(() => {
    track("generation_stopped");
    cancelChat(
      streamSessionIdRef.current ?? conversationId ?? undefined,
    ).catch(() => {});
    abortRef.current?.abort();
    abortRef.current = null;

    const assistantId = pendingIdRef.current;
    const userId = userIdRef.current;
    if (assistantId) {
      if (gotChunkRef.current) {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, pending: false } : m)),
        );
      } else {
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantId && m.id !== userId),
        );
        chatInputRef.current?.setText(userTextRef.current);
      }
    }
    pendingIdRef.current = null;
    userIdRef.current = null;
    gotChunkRef.current = false;
    streamSessionIdRef.current = null;
    setThinking(false);
  }, [chatInputRef, conversationId]);

  const clearMessages = useCallback(() => setMessages([]), []);

  /** Replace the thread with a replayed conversation (history click). */
  const loadMessages = useCallback((next: Message[]) => {
    // Drop any in-flight turn state so a replayed thread starts clean.
    abortRef.current?.abort();
    abortRef.current = null;
    pendingIdRef.current = null;
    userIdRef.current = null;
    gotChunkRef.current = false;
    streamSessionIdRef.current = null;
    setThinking(false);
    setMessages(next);
  }, []);

  return { messages, thinking, handleSend, handleStop, clearMessages, loadMessages };
}
