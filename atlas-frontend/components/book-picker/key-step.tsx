"use client";

import { useState } from "react";
import { AlertTriangle, Check, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { validateGeminiKey } from "@/lib/validate-gemini-key";

interface KeyStepProps {
  /** True when re-prompting after a backend key rejection */
  keyInvalid?: boolean;
  onSave: (key: string) => void;
  /** Called when the user opts to skip the key step */
  onSkip?: () => void;
}

/**
 * Step 2 — Gemini API key entry. Mounts only when the flow reaches the key
 * step, so its fields start fresh on each arrival (no reset effect needed).
 */
export function KeyStep({ keyInvalid = false, onSave, onSkip }: KeyStepProps) {
  const [keyInput, setKeyInput] = useState("");
  const [reveal, setReveal] = useState(false);
  const [validating, setValidating] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);

  const trimmedKey = keyInput.trim();

  const handleSave = async () => {
    if (!trimmedKey || validating) return;
    setKeyError(null);
    setValidating(true);
    const valid = await validateGeminiKey(trimmedKey);
    setValidating(false);
    if (!valid) {
      setKeyError("Key is invalid.");
      return;
    }
    onSave(trimmedKey);
  };

  return (
    <>
      <div className="px-5 py-4 space-y-3">
        <p className="text-sm text-[var(--muted)]">
          For the complete experience, add your Gemini API key. You can also add it later from{" "}
          <span className="font-medium text-[var(--foreground)]">Settings</span>.
        </p>

        {(keyInvalid || keyError) && (
          <div className="flex items-start gap-2 rounded-lg border border-[var(--negative,#ef4444)]/30 bg-[var(--negative,#ef4444)]/10 px-3 py-2 text-xs text-[var(--negative,#ef4444)]">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {keyError ?? "Key is invalid."}
          </div>
        )}
        <label htmlFor="gemini-key" className="mb-1.5 block text-sm font-medium">
          Gemini API Key
        </label>
        <div className="relative">
          <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <input
            id="gemini-key"
            type={reveal ? "text" : "password"}
            value={keyInput}
            onChange={(e) => { setKeyInput(e.target.value); setKeyError(null); }}
            onKeyDown={(e) => { if (e.key === "Enter" && trimmedKey) handleSave(); }}
            placeholder="AIza…"
            autoComplete="off"
            autoFocus
            spellCheck={false}
            disabled={validating}
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-2.5 pl-9 pr-10 text-sm text-[var(--foreground)] placeholder:text-[var(--subtle)] transition-colors focus:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] disabled:opacity-60"
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
          Get your free Gemini API key from{" "}
          <a
            href="https://aistudio.google.com/api-keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] underline underline-offset-2 hover:opacity-80"
          >
            AI Studio
          </a>
          . Our servers don&apos;t store your key.
        </p>
      </div>

      <div className="border-t border-[var(--border)] px-5 py-3">
        {trimmedKey ? (
          <button
            type="button"
            disabled={validating}
            onClick={handleSave}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            {validating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Validating…
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                Save key
              </>
            )}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onSkip?.()}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-[var(--border)] py-2.5 text-sm font-semibold text-[var(--muted)] transition-all hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            Skip for now
          </button>
        )}
      </div>
    </>
  );
}
