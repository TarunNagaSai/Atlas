/** Centralised app-wide configuration. Change values here; nothing else needs to move. */

// ── Time constants ─────────────────────────────────────────────────────────────

export const HOUR_MS = 60 * 60 * 1000;
export const DAY_MS = 24 * HOUR_MS;

// ── Models ────────────────────────────────────────────────────────────────────

export const MODELS = [
  { id: "gemini-3.5-flash", tag: "3.5 flash" },
  { id: "gemini-3.1-pro-preview", tag: "3.1 pro" },
  { id: "gemini-3.1-flash-lite", tag: "3.1 flash-lite" },
] as const satisfies ReadonlyArray<{ id: string; tag: string }>;

export type ModelId = (typeof MODELS)[number]["id"];

export const DEFAULT_MODEL: ModelId = "gemini-3.5-flash";
