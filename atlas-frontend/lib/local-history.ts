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

const CHAT_PREFIX = "atlas.chat.";
const INDEX_KEY = "atlas.chats.index";

/** One conversation in the local sidebar index. */
export interface LocalChatMeta {
  id: string;
  title: string;
  updatedAt: number;
}

/** The sidebar index, most-recently-updated first. Empty during SSR or if unset. */
export function listLocalChats(): LocalChatMeta[] {
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

    const index = listLocalChats();
    const existing = index.find((c) => c.id === id);
    // Nothing changed (this is an open/replay of an already-stored chat): leave
    // the index — and thus the title and ordering — exactly as it was.
    if (existing && prevRaw === serialized) return;

    const firstUser = settled.find((m) => m.role === "user")?.content ?? "";
    const title =
      existing?.title ??
      (firstUser.trim().slice(0, 80) || "Untitled conversation");
    const others = index.filter((c) => c.id !== id);
    const next = [{ id, title, updatedAt: Date.now() }, ...others];
    localStorage.setItem(INDEX_KEY, JSON.stringify(next));
  } catch {
    // localStorage full/unavailable — non-critical; the in-memory thread is intact.
  }
}
