"use client";

/**
 * The visitor's Gemini API key.
 *
 * Lives in localStorage, like the session id, so it survives reloads, new tabs,
 * and full browser restarts — the visitor is only asked for a key once. It is
 * attached as `X-Gemini-Api-Key` on every /chat/stream request (see lib/api.ts)
 * and cleared + re-prompted whenever the backend reports it missing or invalid.
 */

import { useCallback, useEffect, useState } from "react";
import { isBrowser } from "@/lib/utils";

const KEY = "atlas.gemini.key";
const SKIPPED = "atlas.gemini.key.skipped";

/** The stored key, or "" during SSR / when the visitor hasn't entered one. */
export function getApiKey(): string {
  if (!isBrowser()) return "";
  return localStorage.getItem(KEY) ?? "";
}

/** Persist the visitor's key indefinitely (until they delete it). */
export function setApiKey(key: string): void {
  if (!isBrowser()) return;
  localStorage.setItem(KEY, key);
  // Entering a key supersedes any earlier "skip" decision.
  localStorage.removeItem(SKIPPED);
}

/** Forget the stored key (called on a 400 or an invalid_api_key event). */
export function clearApiKey(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY);
}

/**
 * Whether the visitor chose to skip the key prompt. Persisted so we don't
 * re-ask on every refresh — the prompt appears once and only comes back if the
 * backend rejects a request (which resets this).
 */
export function getKeySkipped(): boolean {
  if (!isBrowser()) return false;
  return localStorage.getItem(SKIPPED) === "1";
}

export function setKeySkipped(skipped: boolean): void {
  if (!isBrowser()) return;
  if (skipped) localStorage.setItem(SKIPPED, "1");
  else localStorage.removeItem(SKIPPED);
}

/**
 * React binding for the key. Resolves from localStorage on mount (avoiding an
 * SSR hydration mismatch) and exposes setters that keep React state and storage
 * in sync. `ready` flips true once the effect has run, so callers can tell
 * "no key yet" from "haven't read storage yet".
 */
export function useApiKey() {
  const [apiKey, setKeyState] = useState("");
  const [skipped, setSkippedState] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setKeyState(getApiKey());
    setSkippedState(getKeySkipped());
    setReady(true);
  }, []);

  const save = useCallback((key: string) => {
    const trimmed = key.trim();
    setApiKey(trimmed); // also clears the persisted "skipped" flag
    setKeyState(trimmed);
    setSkippedState(false);
  }, []);

  const clear = useCallback(() => {
    clearApiKey();
    setKeyState("");
  }, []);

  const skip = useCallback(() => {
    setKeySkipped(true);
    setSkippedState(true);
  }, []);

  const unskip = useCallback(() => {
    setKeySkipped(false);
    setSkippedState(false);
  }, []);

  return { apiKey, hasKey: apiKey !== "", skipped, ready, save, clear, skip, unskip };
}
