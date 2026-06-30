"use client";

import { useEffect, useState } from "react";
import { Check, Eye, EyeOff, KeyRound, AlertTriangle } from "lucide-react";

interface ApiKeyModalProps {
  open: boolean;
  /**
   * True when the modal was opened because a key was rejected (vs. asked for the
   * first time), so we can explain why we're re-prompting.
   */
  invalid?: boolean;
  onSubmit: (key: string) => void;
}

/**
 * Prompt the visitor for their Gemini API key. Shown on first use (no key yet)
 * and again whenever the backend reports the key missing (400) or invalid
 * (invalid_api_key event). Selection is required — there's no dismiss.
 */
export function ApiKeyModal({ open, invalid = false, onSubmit }: ApiKeyModalProps) {
  const [key, setKey] = useState("");
  const [reveal, setReveal] = useState(false);

  // Clear the field each time the prompt reopens (e.g. after a rejected key).
  useEffect(() => {
    if (open) setKey("");
  }, [open]);

  if (!open) return null;

  const trimmed = key.trim();

  const submit = () => {
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      {/* Backdrop — not dismissible; a key is required to chat. */}
      <div aria-hidden className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      <div className="relative z-10 flex w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">
        {/* Header */}
        <div className="flex flex-col items-center border-b border-[var(--border)] px-5 py-5 text-center">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-sm)]">
            <KeyRound className="h-[18px] w-[18px]" strokeWidth={2.4} />
          </div>
          <h2 className="mt-3 text-base font-semibold tracking-tight">
            Enter your Gemini API key
          </h2>
          <p className="mt-1 text-xs text-[var(--subtle)]">
            Atlas uses your own key to run the model. It stays in this tab and is
            sent only with your chat requests.
          </p>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {invalid && (
            <div className="flex items-start gap-2 rounded-lg border border-[var(--negative)]/30 bg-[var(--negative)]/10 px-3 py-2 text-xs text-[var(--negative)]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                That key was rejected. Double-check it and paste it again.
              </span>
            </div>
          )}

          <div className="relative">
            <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type={reveal ? "text" : "password"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              placeholder="AIza…"
              autoComplete="off"
              autoFocus
              spellCheck={false}
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-2.5 pl-9 pr-10 text-sm text-[var(--foreground)] placeholder:text-[var(--subtle)] transition-colors focus:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
            />
            <button
              type="button"
              onClick={() => setReveal((v) => !v)}
              aria-label={reveal ? "Hide key" : "Show key"}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
            >
              {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          <p className="text-[11px] text-[var(--subtle)]">
            Get a key from Google AI Studio. It isn&apos;t stored on our servers.
          </p>
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--border)] px-5 py-3">
          <button
            type="button"
            disabled={!trimmed}
            onClick={submit}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <Check className="h-4 w-4" />
            Save key
          </button>
        </div>
      </div>
    </div>
  );
}
