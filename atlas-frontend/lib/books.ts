"use client";

import { useCallback, useSyncExternalStore } from "react";
import { fetchBooks, type Book } from "@/lib/api";

/**
 * Global books store. The notebook list is fetched exactly once at app open
 * (via `loadBooks`) and shared with every consumer through `useBooks`, so the
 * BookPicker, SettingsModal, and EmptyState never re-hit `GET /books` each time
 * they mount or open. Concurrent callers dedupe onto a single in-flight request.
 */

interface BooksState {
  books: Book[];
  loading: boolean;
  error: string | null;
  loaded: boolean;
}

let state: BooksState = { books: [], loading: false, error: null, loaded: false };
const listeners = new Set<() => void>();
let inflight: Promise<void> | null = null;

function setState(patch: Partial<BooksState>) {
  state = { ...state, ...patch };
  for (const listener of listeners) listener();
}

/**
 * Fetch the books once and cache them. Subsequent calls are no-ops (an
 * in-flight request is reused; an already-loaded list is kept) unless `force`
 * is passed to retry after an error.
 */
export function loadBooks(force = false): Promise<void> {
  if (inflight) return inflight;
  if (state.loaded && !force) return Promise.resolve();

  setState({ loading: true, error: null });
  inflight = fetchBooks()
    .then((books) => setState({ books, loaded: true, loading: false }))
    .catch((e) =>
      setState({
        error: e instanceof Error ? e.message : String(e),
        loading: false,
      }),
    )
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot() {
  return state;
}

/** Read the shared books list. Triggers the one-time load lazily if needed. */
export function useBooks() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const reload = useCallback(() => {
    loadBooks(true);
  }, []);
  return { ...snapshot, reload };
}
