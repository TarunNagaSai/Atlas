"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  RotateCw,
  TrendingUp,
  User,
} from "lucide-react";
import { track } from "@vercel/analytics";
import { fetchBooks, type Book } from "@/lib/api";

interface BookPickerProps {
  /** "book" = step 1, "key" = step 2, null = closed */
  step: "book" | "key" | null;
  /** True when re-prompting after a backend key rejection */
  keyInvalid?: boolean;
  onConfirmBook: (bookId: string, name: string) => void;
  onSaveKey: (key: string) => void;
  /** Called when the user opts to skip the key step */
  onSkip?: () => void;
}

async function validateGeminiKey(key: string): Promise<boolean> {
  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(key)}`,
      { signal: AbortSignal.timeout(8000) },
    );
    return res.ok;
  } catch {
    return false;
  }
}

export function BookPicker({ step, keyInvalid = false, onConfirmBook, onSaveKey, onSkip }: BookPickerProps) {
  // ── Step 1: book selection ────────────────────────────────────────────────
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // ── Step 2: API key ───────────────────────────────────────────────────────
  const [keyInput, setKeyInput] = useState("");
  const [reveal, setReveal] = useState(false);
  const [validating, setValidating] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);

  const trimmedName = name.trim();
  const trimmedKey = keyInput.trim();

  // Reset key fields whenever we arrive at step 2
  useEffect(() => {
    if (step === "key") {
      setKeyInput("");
      setReveal(false);
      setValidating(false);
      setKeyError(null);
    }
  }, [step]);

  // Load books when step 1 is shown
  useEffect(() => {
    if (step !== "book") return;
    const ctrl = new AbortController();
    setLoading(true);
    setFetchError(null);

    fetchBooks({ signal: ctrl.signal })
      .then((b) => setBooks(b))
      .catch((e) => {
        if ((e as Error)?.name !== "AbortError") {
          setFetchError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [reloadKey, step]);

  if (!step) return null;

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleConfirmBook = () => {
    if (!picked || !trimmedName) return;
    track("book_selected", { book_id: picked });
    onConfirmBook(picked, trimmedName);
  };

  const handleSaveKey = async () => {
    if (!trimmedKey || validating) return;
    setKeyError(null);
    setValidating(true);
    const valid = await validateGeminiKey(trimmedKey);
    setValidating(false);
    if (!valid) {
      setKeyError("Key is invalid.");
      return;
    }
    onSaveKey(trimmedKey);
  };

  // ── Shared header branding ────────────────────────────────────────────────
  const brand = (
    <div className="flex flex-col items-center border-b border-[var(--border)] px-5 py-5 text-center">
      <h2 className="mt-3 text-base font-semibold tracking-tight">Welcome to Atlas</h2>
      <p className="mt-1 text-xs text-[var(--subtle)]">
         Atlas is a curated demo designed to highlight my work with Agentic AI. I invite you to take your time exploring the project and learning about its features.
      </p>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div aria-hidden className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      <div className="relative z-10 flex w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">

        {/* ── Step indicator ── */}
        <div className="flex items-center gap-1.5 px-5 pt-4">
          {(["book", "key"] as const).map((s, i) => (
            <div key={s} className="flex items-center gap-1.5">
              <div
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold transition-colors ${
                  step === s
                    ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                    : step === "key" && s === "book"
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "bg-[var(--surface-3)] text-[var(--muted)]"
                }`}
              >
                {step === "key" && s === "book" ? <Check className="h-3 w-3" /> : i + 1}
              </div>
              <span className={`text-[11px] font-medium ${step === s ? "text-[var(--foreground)]" : "text-[var(--subtle)]"}`}>
                {s === "book" ? "Select notebook" : "Add API key"}
              </span>
              {i === 0 && <div className="mx-1 h-px w-6 bg-[var(--border)]" />}
            </div>
          ))}
        </div>

        {brand}

        {/* ── Step 1: book + name ── */}
        {step === "book" && (
          <>
            <div className="max-h-[60vh] overflow-y-auto px-5 py-4 space-y-4">
              {/* Name */}
              <div>
                <label htmlFor="user-name" className="mb-1.5 block text-sm font-medium">
                  Your name
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                  <input
                    id="user-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Tarun Kodali"
                    autoComplete="off"
                    className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-2.5 pl-9 pr-3 text-sm text-[var(--foreground)] placeholder:text-[var(--subtle)] transition-colors focus:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                  />
                </div>
              </div>

              <p className="text-sm font-medium">Select notebook</p>

              {loading ? (
                <div className="flex items-center justify-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-8 text-sm text-[var(--muted)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading notebooks…
                </div>
              ) : fetchError ? (
                <div className="flex flex-col items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-6 text-center">
                  <div className="flex items-center gap-2 text-sm text-[var(--negative)]">
                    <AlertTriangle className="h-4 w-4" />
                    Couldn&apos;t load notebooks
                  </div>
                  <p className="max-w-sm text-xs text-[var(--muted)]">{fetchError}</p>
                  <button
                    type="button"
                    onClick={() => setReloadKey((k) => k + 1)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  >
                    <RotateCw className="h-3.5 w-3.5" />
                    Retry
                  </button>
                </div>
              ) : books.length === 0 ? (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-8 text-center text-sm text-[var(--muted)]">
                  No notebooks are available yet.
                </div>
              ) : (
                <ul className="flex flex-col gap-2">
                  {books.map((book, i) => {
                    const active = picked === book.book_id;
                    const source = i === 0
                      ? "SEBI / JIO DRHP Document"
                      : i === 1
                      ? "JP Morgan Official Website"
                      : null;
                    return (
                      <li key={book.book_id}>
                        <button
                          type="button"
                          onClick={() => setPicked(book.book_id)}
                          aria-pressed={active}
                          className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] ${
                            active
                              ? "border-[var(--accent)] bg-[var(--accent-soft)] shadow-[var(--shadow-sm)]"
                              : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--accent)]"
                          }`}
                        >
                          <div
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                              active
                                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                                : "bg-[var(--accent-soft)] text-[var(--accent)]"
                            }`}
                          >
                            {active ? <Check className="h-[18px] w-[18px]" /> : <BookOpen className="h-[18px] w-[18px]" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium">{book.title}</div>
                            {source && (
                              <div className="mt-0.5 text-xs text-[var(--muted)]">{source}</div>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {!loading && !fetchError && books.length > 0 && (
              <div className="border-t border-[var(--border)] px-5 py-3">
                <button
                  type="button"
                  disabled={!picked || !trimmedName}
                  onClick={handleConfirmBook}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                >
                  <Check className="h-4 w-4" />
                  Continue
                </button>
              </div>
            )}
          </>
        )}

        {/* ── Step 2: API key ── */}
        {step === "key" && (
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

              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                <input
                  type={reveal ? "text" : "password"}
                  value={keyInput}
                  onChange={(e) => { setKeyInput(e.target.value); setKeyError(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && trimmedKey) handleSaveKey(); }}
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
                  onClick={handleSaveKey}
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
        )}
      </div>
    </div>
  );
}
