"use client";

/**
 * The visitor's Gemini API key.
 *
 * Unlike the session id (localStorage, permanent until reset), the key lives in
 * sessionStorage: it survives reloads within the tab but is dropped when the tab
 * closes, so it isn't persisted indefinitely on a shared machine. It is attached
 * as `X-Gemini-Api-Key` on every /chat/stream request (see lib/api.ts) and
 * cleared + re-prompted whenever the backend reports it missing or invalid.
 */

import { useCallback, useEffect, useState } from "react";

const KEY = "atlas.gemini.key";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

/** The stored key, or "" during SSR / when the visitor hasn't entered one. */
export function getApiKey(): string {
  if (!isBrowser()) return "";
  return sessionStorage.getItem(KEY) ?? "";
}

/** Persist the visitor's key for the lifetime of this tab. */
export function setApiKey(key: string): void {
  if (!isBrowser()) return;
  sessionStorage.setItem(KEY, key);
}

/** Forget the stored key (called on a 400 or an invalid_api_key event). */
export function clearApiKey(): void {
  if (!isBrowser()) return;
  sessionStorage.removeItem(KEY);
}

/**
 * React binding for the key. Resolves from sessionStorage on mount (avoiding an
 * SSR hydration mismatch) and exposes setters that keep React state and storage
 * in sync. `ready` flips true once the effect has run, so callers can tell
 * "no key yet" from "haven't read storage yet".
 */
export function useApiKey() {
  const [apiKey, setKeyState] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setKeyState(getApiKey());
    setReady(true);
  }, []);

  const save = useCallback((key: string) => {
    const trimmed = key.trim();
    setApiKey(trimmed);
    setKeyState(trimmed);
  }, []);

  const clear = useCallback(() => {
    clearApiKey();
    setKeyState("");
  }, []);

  return { apiKey, hasKey: apiKey !== "", ready, save, clear };
}
