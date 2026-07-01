"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BookPicker } from "@/components/book-picker";
import { ChatHistory } from "@/components/chat-history";
import { ChatInput, type ChatInputHandle } from "@/components/chat-input";
import { EmptyState } from "@/components/empty-state";
import { MessageBubble } from "@/components/message-bubble";
import { RagPanel } from "@/components/rag-panel";
import { TopBar } from "@/components/top-bar";
import { useApiKey } from "@/lib/api-key";
import { useChatStream } from "@/hooks/use-chat-stream";
import {
  fetchConversation,
  fetchSessions,
  getChatStorageMode,
  toCitation,
  type ConversationStep,
  type ConversationTurn,
  type StreamSource,
} from "@/lib/api";
import { listLocalChats, loadLocalChat, saveLocalChat } from "@/lib/local-history";
import { useConversationUsage, useSession } from "@/lib/session";
import type { AgentStep, ChatSession, Message, ThinkingStep } from "@/types";

/** Map a persisted conversation's turns into the flat Message list the thread renders. */
function turnsToMessages(turns: ConversationTurn[]): Message[] {
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
function stepsFromConversation(
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
function thinkingFromConversation(
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
function citationsFromSteps(steps: ConversationStep[] | undefined) {
  const sourcesStep = steps?.find((s) => s.type === "sources");
  const sources = sourcesStep?.sources as StreamSource[] | undefined;
  if (!Array.isArray(sources)) return undefined;
  return sources.map(toCitation);
}

// Where transcripts live (frontend-chosen, sent to the backend per request):
// "db" → the server persists and serves the sidebar/replay; "client" → the
// browser owns history in localStorage and replays it on every query.
const STORAGE_MODE = getChatStorageMode();

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  // null = a brand-new, unsent chat. Once a turn is sent the server mints an id
  // (or we adopt the one we clicked in the sidebar).
  const [activeId, setActiveId] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  const { ready, selectedBook, selectBook, userName } = useSession();
  // Token usage is tracked per conversation (per chat), so the counter reflects
  // the active chat and a brand-new "New analysis" starts at zero.
  const { usage, record } = useConversationUsage(activeId);

  const { hasKey, ready: keyReady, save: saveKey, clear: clearKey } = useApiKey();
  const [keyInvalid, setKeyInvalid] = useState(false);
  const [keySkipped, setKeySkipped] = useState(false);

  // Derived — no extra open/close state needed.
  // "book" → no notebook chosen yet
  // "key"  → notebook chosen but no valid key (unless user skipped)
  // null   → setup complete, modal closed
  const setupStep: "book" | "key" | null =
    !selectedBook ? "book" : keyReady && !hasKey && !keySkipped ? "key" : null;

  const handleSkipKey = useCallback(() => setKeySkipped(true), []);

  // Re-prompt when the backend rejects the request for a missing/invalid key.
  const handleAuthError = useCallback((invalid: boolean) => {
    clearKey(); // hasKey → false → setupStep becomes "key" automatically
    setKeyInvalid(invalid);
    setKeySkipped(false); // force re-prompt if backend rejects
  }, [clearKey]);

  const handleConfirmBook = useCallback((bookId: string, name: string) => {
    selectBook(bookId, name); // selectedBook → truthy → setupStep advances to "key"
  }, [selectBook]);

  const handleSaveKey = useCallback(
    (key: string) => {
      saveKey(key); // hasKey → true → setupStep becomes null
      setKeyInvalid(false);
    },
    [saveKey],
  );

  const handleSwitchBook = useCallback(
    (bookId: string) => {
      selectBook(bookId, userName ?? "");
    },
    [selectBook, userName],
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<ChatInputHandle>(null);
  // The conversation the user most recently asked to view — used to drop a
  // replay response if they've clicked elsewhere before it arrived.
  const selectedIdRef = useRef<string | null>(null);

  // Refresh the history sidebar (most-recently-active first). Source depends on
  // the storage mode: the backend in DB mode, localStorage in client mode.
  const refreshSessions = useCallback(() => {
    if (STORAGE_MODE === "client") {
      setSessions(
        listLocalChats().map((c) => ({
          id: c.id,
          title: c.title || "Untitled conversation",
          updatedAt: c.updatedAt,
        })),
      );
      return;
    }
    fetchSessions()
      .then((list) =>
        setSessions(
          list.map((s) => ({
            id: s.session_id,
            title: s.title || "Untitled conversation",
            updatedAt: Date.parse(s.last_at) || Date.now(),
          })),
        ),
      )
      .catch(() => {
        // Sidebar is non-critical; leave whatever's there and let the next
        // turn-complete refresh retry.
      });
  }, []);

  const { messages, thinking, handleSend, handleStop, clearMessages, loadMessages } =
    useChatStream({
      record,
      chatInputRef,
      conversationId: activeId,
      onTurnComplete: refreshSessions,
      onAuthError: handleAuthError,
    });

  // Gate sends on having a key: if none, prompt instead of firing a doomed
  // request. The 400/invalid_api_key paths still re-prompt as a backstop.
  const handleSendGated = useCallback(
    (text: string, model?: string, files: File[] = []) => {
      if (!hasKey) return; // setupStep is already "key" when hasKey is false
      handleSend(text, model, files);
    },
    [hasKey, handleSend],
  );

  // Load the history sidebar once the session id is resolved, and mint the id
  // for the fresh "New analysis" this visit lands on. Session ids are created in
  // exactly two places — here on app-open, and in handleNewChat — never on send.
  // A minted id is only a *draft* until its first turn is persisted, so a
  // brand-new chat isn't listed in the sidebar until the visitor asks something
  // (saveLocalChat skips empty transcripts); the pinned "New analysis" row
  // represents it in the meantime.
  const initedRef = useRef(false);
  useEffect(() => {
    if (!ready) return;
    refreshSessions();
    if (!initedRef.current) {
      initedRef.current = true;
      setActiveId(crypto.randomUUID());
    }
  }, [ready, refreshSessions]);

  // Client-side storage mode: persist the live transcript to localStorage and
  // keep the sidebar in sync. No-op in DB mode (the backend owns history there).
  useEffect(() => {
    if (STORAGE_MODE !== "client" || !activeId || messages.length === 0) return;
    saveLocalChat(activeId, messages);
    refreshSessions();
  }, [messages, activeId, refreshSessions]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // The knowledge panel is inline on desktop (open by default) but an overlay
  // drawer on mobile (closed by default). Open it when we cross up into the
  // desktop layout and close it when we cross down into mobile, so it never
  // lingers open over the chat. We only act on an actual breakpoint crossing,
  // leaving the user's manual toggles intact between crossings.
  useEffect(() => {
    const DESKTOP = 1024; // matches the `lg:` breakpoint used in the layout
    let wasDesktop = window.innerWidth >= DESKTOP;
    setPanelOpen(wasDesktop);
    const onResize = () => {
      const isDesktop = window.innerWidth >= DESKTOP;
      if (isDesktop !== wasDesktop) {
        wasDesktop = isDesktop;
        setPanelOpen(isDesktop);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const handleNewChat = () => {
    // Start a brand-new, unsent chat: mint its id now (the second and only other
    // place a session is created) and clear the thread. It stays a draft — not
    // listed in the sidebar, represented by the pinned "New analysis" row — until
    // its first turn is persisted.
    selectedIdRef.current = null;
    setActiveId(crypto.randomUUID());
    clearMessages();
  };

  const handleSelectSession = (id: string) => {
    if (id === activeId) return;
    selectedIdRef.current = id;
    setActiveId(id);
    // Client mode replays from localStorage (synchronous, no backend call);
    // DB mode fetches the persisted conversation from the server.
    if (STORAGE_MODE === "client") {
      loadMessages(loadLocalChat(id));
      return;
    }
    loadMessages([]);
    setChatLoading(true);
    fetchConversation(id)
      .then((conv) => {
        if (selectedIdRef.current !== id) return;
        loadMessages(turnsToMessages(conv.turns));
      })
      .catch(() => {})
      .finally(() => {
        if (selectedIdRef.current === id) setChatLoading(false);
      });
  };

  // Title shown in the top bar. Prefer the saved session title; before the
  // session is persisted (the first turn of a new chat), fall back to the first
  // user message so the title appears the moment the visitor asks. Only a truly
  // empty new chat shows "New analysis".
  const activeTitle =
    sessions.find((s) => s.id === activeId)?.title ??
    messages.find((m) => m.role === "user")?.content.trim().slice(0, 80) ??
    "New analysis";

  // Steps from the most recent assistant turn — shown live in the RagPanel.
  const latestSteps = [...messages]
    .reverse()
    .find((m) => m.role === "assistant")?.steps;

  // Hold the chrome back until we've read localStorage, so the picker doesn't
  // flash for returning users who've already committed to a notebook.
  if (!ready) {
    return <div className="h-[100dvh] w-full bg-[var(--background)]" />;
  }

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-[var(--background)]">
      <BookPicker
        step={setupStep}
        keyInvalid={keyInvalid}
        onConfirmBook={handleConfirmBook}
        onSaveKey={handleSaveKey}
        onSkip={handleSkipKey}
      />
      <ChatHistory
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
        userName={userName}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        hasKey={hasKey}
        onSaveKey={handleSaveKey}
        selectedBook={selectedBook}
        onSwitchBook={handleSwitchBook}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={activeTitle}
          fileCount={1}
          panelOpen={panelOpen}
          onTogglePanel={() => setPanelOpen((v) => !v)}
          onOpenNav={() => setNavOpen(true)}
        />

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 sm:py-8">
            {chatLoading ? (
              <ChatSkeleton />
            ) : messages.length === 0 ? (
              <EmptyState onPick={handleSendGated} />
            ) : (
              messages.map((m) => <MessageBubble key={m.id} message={m} />)
            )}
          </div>
        </div>

        <ChatInput
          ref={chatInputRef}
          onSend={handleSendGated}
          onStop={handleStop}
          streaming={thinking}
          disabled={thinking}
          tokensUsed={usage.total}
          draftKey={activeId}
        />
      </main>

      <RagPanel
        selectedBook={selectedBook}
        fileCount={1}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        steps={latestSteps}
      />
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      {/* User message */}
      <div className="flex justify-end">
        <div className="h-9 w-48 rounded-2xl rounded-br-md bg-[var(--surface-2)]" />
      </div>
      {/* Assistant message */}
      <div className="flex gap-3">
        <div className="h-8 w-8 shrink-0 rounded-lg bg-[var(--surface-2)]" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 w-16 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-full rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-5/6 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-4/6 rounded bg-[var(--surface-2)]" />
        </div>
      </div>
      {/* User message */}
      <div className="flex justify-end">
        <div className="h-9 w-64 rounded-2xl rounded-br-md bg-[var(--surface-2)]" />
      </div>
      {/* Assistant message */}
      <div className="flex gap-3">
        <div className="h-8 w-8 shrink-0 rounded-lg bg-[var(--surface-2)]" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 w-16 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-full rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-3/4 rounded bg-[var(--surface-2)]" />
        </div>
      </div>
    </div>
  );
}
