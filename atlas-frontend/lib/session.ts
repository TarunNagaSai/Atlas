"use client";

/**
 * Per-browser session identity + per-conversation token-usage accounting.
 *
 * A session id is minted once via `crypto.randomUUID()` and cached in
 * localStorage, so it survives reloads and is reused on every visit until
 * explicitly reset. It is sent on every backend request (see lib/api.ts) and
 * keys per-browser state (book choice, display name).
 *
 * Token usage, by contrast, is keyed by *conversation* id — each chat ("New
 * analysis") accumulates and persists its own running total under
 * `atlas.usage.<conversationId>`, so switching chats shows that chat's usage
 * and a brand-new chat starts at zero. See `useConversationUsage`.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const SESSION_KEY = "atlas.session.id";
const USAGE_PREFIX = "atlas.usage.";
const BOOK_PREFIX = "atlas.book.";
const NAME_PREFIX = "atlas.name.";
const DRAFT_PREFIX = "atlas.draft.";

export interface TokenUsage {
  /** Prompt tokens (`prompt_tokens`). */
  input: number;
  /** Visible answer + reasoning (`output_tokens + thoughts_tokens`). */
  output: number;
  total: number;
}

const EMPTY_USAGE: TokenUsage = { input: 0, output: 0, total: 0 };

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

/**
 * Stable session id for this browser. Returns the cached value if present,
 * otherwise mints a new UUID, persists it, and returns it. Returns "" during
 * SSR (no localStorage) — read it from inside an effect or event handler.
 */
export function getSessionId(): string {
  if (!isBrowser()) return "";
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/** Drop the current session (and its usage + book choice); next read mints a fresh id. */
export function resetSession(): string {
  if (!isBrowser()) return "";
  const old = localStorage.getItem(SESSION_KEY);
  if (old) {
    localStorage.removeItem(USAGE_PREFIX + old);
    localStorage.removeItem(BOOK_PREFIX + old);
    localStorage.removeItem(NAME_PREFIX + old);
  }
  localStorage.removeItem(SESSION_KEY);
  return getSessionId();
}

/**
 * The notebook this session has committed to, or null if the user hasn't
 * picked yet. The choice is one-time per session id — see `setSelectedBook`.
 */
export function getSelectedBook(sessionId: string): string | null {
  if (!isBrowser() || !sessionId) return null;
  return localStorage.getItem(BOOK_PREFIX + sessionId);
}

/**
 * Persist the session's notebook choice. This is intended to be written once:
 * the UI only offers the picker while `getSelectedBook` is null, so a session
 * never re-selects unless it's reset.
 */
export function setSelectedBook(sessionId: string, bookId: string): void {
  if (!isBrowser() || !sessionId) return;
  localStorage.setItem(BOOK_PREFIX + sessionId, bookId);
}

/** The display name this session committed to at the picker, or null. */
export function getUserName(sessionId: string): string | null {
  if (!isBrowser() || !sessionId) return null;
  return localStorage.getItem(NAME_PREFIX + sessionId);
}

/** Persist the session's display name (written once at the picker). */
export function setUserName(sessionId: string, name: string): void {
  if (!isBrowser() || !sessionId) return;
  localStorage.setItem(NAME_PREFIX + sessionId, name);
}

/**
 * The composer's unsent text for one conversation, or "" if none. Drafts are
 * keyed per chat so switching conversations shows that chat's own in-progress
 * text and a fresh chat starts empty. Returns "" during SSR or for a null id.
 */
export function getDraft(conversationId: string | null): string {
  if (!isBrowser() || !conversationId) return "";
  return localStorage.getItem(DRAFT_PREFIX + conversationId) ?? "";
}

/** Persist (or clear, when empty) a conversation's unsent composer text. */
export function setDraft(conversationId: string | null, text: string): void {
  if (!isBrowser() || !conversationId) return;
  if (text) localStorage.setItem(DRAFT_PREFIX + conversationId, text);
  else localStorage.removeItem(DRAFT_PREFIX + conversationId);
}

/** Stored token total for one conversation (empty if the id is null/unseen). */
export function getUsage(conversationId: string | null): TokenUsage {
  if (!isBrowser() || !conversationId) return EMPTY_USAGE;
  try {
    const raw = localStorage.getItem(USAGE_PREFIX + conversationId);
    if (!raw) return EMPTY_USAGE;
    const u = JSON.parse(raw) as Partial<TokenUsage>;
    const input = u.input ?? 0;
    const output = u.output ?? 0;
    return { input, output, total: input + output };
  } catch {
    return EMPTY_USAGE;
  }
}

/**
 * Add a turn's token counts to one conversation's running total and persist it.
 *
 * `output` is expected to already include reasoning tokens (the caller folds
 * `output_tokens + thoughts_tokens` together), so `total = input + output`.
 */
export function addUsage(
  conversationId: string,
  input: number,
  output: number,
): TokenUsage {
  const cur = getUsage(conversationId);
  const next: TokenUsage = {
    input: cur.input + input,
    output: cur.output + output,
    total: cur.input + input + cur.output + output,
  };
  if (isBrowser() && conversationId) {
    localStorage.setItem(
      USAGE_PREFIX + conversationId,
      JSON.stringify({ input: next.input, output: next.output }),
    );
  }
  return next;
}

/**
 * React binding for the per-browser session. Resolves the id on mount (avoiding
 * an SSR hydration mismatch) and exposes the one-time book/display-name choice.
 * Token usage lives in `useConversationUsage` (it's per chat, not per browser).
 */
export function useSession() {
  const [sessionId, setSessionId] = useState("");
  const [selectedBook, setSelectedBookState] = useState<string | null>(null);
  const [userName, setUserNameState] = useState<string | null>(null);

  useEffect(() => {
    const id = getSessionId();
    setSessionId(id);
    setSelectedBookState(getSelectedBook(id));
    setUserNameState(getUserName(id));
  }, []);

  /** Commit this session's one-time notebook choice and display name. */
  const selectBook = useCallback(
    (bookId: string, name: string) => {
      if (!sessionId) return;
      setSelectedBook(sessionId, bookId);
      setSelectedBookState(bookId);
      setUserName(sessionId, name);
      setUserNameState(name);
    },
    [sessionId],
  );

  const reset = useCallback(() => {
    const id = resetSession();
    setSessionId(id);
    setSelectedBookState(getSelectedBook(id));
    setUserNameState(getUserName(id));
  }, []);

  // True once the effect has resolved the cached id — distinguishes "no book
  // chosen yet" from "haven't read localStorage yet" (avoids a picker flash).
  const ready = sessionId !== "";

  return {
    sessionId,
    ready,
    reset,
    selectedBook,
    selectBook,
    userName,
  };
}

/**
 * Token usage for one conversation. The visible total reflects the chat passed
 * in `conversationId` (resetting to zero for a brand-new chat where it's null,
 * and reloading that chat's stored total when you switch conversations).
 *
 * `record` writes a turn's counts under the conversation id of that turn — which
 * the caller supplies, since a turn may settle after the active chat has moved
 * on. It updates the visible total only when the recorded id is still the active
 * one. The active id is read through a ref so a turn that started before the id
 * was adopted still settles against the right chat.
 */
export function useConversationUsage(conversationId: string | null) {
  const [usage, setUsage] = useState<TokenUsage>(EMPTY_USAGE);

  const activeRef = useRef(conversationId);
  activeRef.current = conversationId;

  useEffect(() => {
    setUsage(getUsage(conversationId));
  }, [conversationId]);

  const record = useCallback(
    (id: string, input: number, output: number) => {
      if (!id) return;
      const next = addUsage(id, input, output);
      if (id === activeRef.current) setUsage(next);
    },
    [],
  );

  return { usage, record };
}
