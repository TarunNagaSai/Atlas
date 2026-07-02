"use client";

/**
 * Client-side chat persistence for "client" storage mode (NEXT_PUBLIC_CHAT_STORAGE).
 *
 * In this mode the backend stores nothing — the browser owns every transcript.
 * Each conversation's full `Message[]` is cached in localStorage under
 * `atlas.chat.<id>`, and a lightweight index (`atlas.chats.index`) holds the
 * `{ id, title, updatedAt }` entries the sidebar renders. Both survive reloads.
 *
 * The DB-mode counterpart is the backend's `/chat/sessions` endpoints; this file
 * is only consulted when `getChatStorageMode() === "client"`.
 */

import type { Message } from "@/types";
import { isBrowser } from "@/lib/utils";
import { getSelectedBook, getSessionId } from "@/lib/session";

const CHAT_PREFIX = "atlas.chat.";
const INDEX_KEY = "atlas.chats.index";
// Ids of DB-seeded conversations already pulled into localStorage. Seeding is a
// one-time hydrate per id: this set is what makes it one-time, so a seed the
// visitor later deletes locally isn't re-added on the next load, and a revisit
// doesn't re-fetch what's already here.
const SEEDED_KEY = "atlas.seeded.ids";

/** One conversation in the local sidebar index. */
export interface LocalChatMeta {
  id: string;
  title: string;
  updatedAt: number;
  /**
   * The notebook this chat belongs to. Undefined for legacy entries written
   * before history was book-scoped — those match no book and stay hidden.
   */
  bookId?: string;
}

/** The notebook currently in use, mirroring `sessionHeaders()` in lib/api.ts. */
function currentBookId(): string | null {
  return getSelectedBook(getSessionId());
}

/** The full, unfiltered index (all books), most-recently-updated first. */
function readIndex(): LocalChatMeta[] {
  if (!isBrowser()) return [];
  try {
    const raw = localStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as LocalChatMeta[];
    return Array.isArray(list)
      ? [...list].sort((a, b) => b.updatedAt - a.updatedAt)
      : [];
  } catch {
    return [];
  }
}

/**
 * The sidebar index for the active notebook, most-recently-updated first.
 * Scoped to the current book so switching notebooks shows only that book's
 * chats (its own DB/static seeds included). Empty during SSR or if unset.
 */
export function listLocalChats(): LocalChatMeta[] {
  const book = currentBookId();
  if (!book) return [];
  return readIndex().filter((c) => c.bookId === book);
}

/** True once this conversation id has been hydrated from the DB seed source. */
export function isSeeded(id: string): boolean {
  if (!isBrowser() || !id) return false;
  try {
    const raw = localStorage.getItem(SEEDED_KEY);
    const ids = raw ? (JSON.parse(raw) as string[]) : [];
    return Array.isArray(ids) && ids.includes(id);
  } catch {
    return false;
  }
}

/** Record that a conversation id has been seeded, so it's never re-hydrated. */
export function markSeeded(id: string): void {
  if (!isBrowser() || !id) return;
  try {
    const raw = localStorage.getItem(SEEDED_KEY);
    const ids = raw ? (JSON.parse(raw) as string[]) : [];
    const set = Array.isArray(ids) ? ids : [];
    if (!set.includes(id)) {
      set.push(id);
      localStorage.setItem(SEEDED_KEY, JSON.stringify(set));
    }
  } catch {
    // localStorage unavailable — worst case the seed is re-pulled next load.
  }
}

/** The stored transcript for one conversation (empty if none). */
export function loadLocalChat(id: string): Message[] {
  if (!isBrowser() || !id) return [];
  try {
    const raw = localStorage.getItem(CHAT_PREFIX + id);
    if (!raw) return [];
    const msgs = JSON.parse(raw) as Message[];
    return Array.isArray(msgs) ? msgs : [];
  } catch {
    return [];
  }
}

/**
 * Persist a conversation's transcript and refresh its index entry. Turns still
 * streaming (`pending`) are dropped so a reload never restores a half-finished
 * bubble. A conversation with no real content yet is skipped (no empty entries
 * in the sidebar).
 *
 * Two rules keep the sidebar stable:
 *  - The title is taken from the first question once, then frozen — a later turn
 *    never rewrites it.
 *  - `updatedAt` (which drives the top-of-list ordering) is only bumped when the
 *    transcript actually grew. Merely *opening* a conversation re-saves the same
 *    settled messages, and that must not float it to the top; only asking a new
 *    question does.
 */
export function saveLocalChat(id: string, messages: Message[]): void {
  if (!isBrowser() || !id) return;
  const settled = messages.filter((m) => !m.pending);
  if (settled.length === 0) return;
  try {
    const serialized = JSON.stringify(settled);
    const prevRaw = localStorage.getItem(CHAT_PREFIX + id);
    localStorage.setItem(CHAT_PREFIX + id, serialized);

    // The full index (all books) — never filter here, or rewriting would drop
    // every other notebook's chats.
    const index = readIndex();
    const existing = index.find((c) => c.id === id);
    // Nothing changed (this is an open/replay of an already-stored chat): leave
    // the index — and thus the title and ordering — exactly as it was.
    if (existing && prevRaw === serialized) return;

    const firstUser = settled.find((m) => m.role === "user")?.content ?? "";
    const title =
      existing?.title ??
      (firstUser.trim().slice(0, 80) || "Untitled conversation");
    // Tag the chat with the notebook it belongs to so the sidebar can scope by
    // book. Preserve an existing entry's book (chats never migrate notebooks).
    const bookId = existing?.bookId ?? currentBookId() ?? undefined;
    const others = index.filter((c) => c.id !== id);
    const next = [{ id, title, updatedAt: Date.now(), bookId }, ...others];
    localStorage.setItem(INDEX_KEY, JSON.stringify(next));
  } catch {
    // localStorage full/unavailable — non-critical; the in-memory thread is intact.
  }
}
