"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, Check, Eye, EyeOff, KeyRound, Loader2, Moon, RotateCw, Settings, Sun, X } from "lucide-react";
import { fetchBooks, type Book } from "@/lib/api";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  isDark: boolean;
  onToggleTheme: () => void;
  hasKey: boolean;
  onSaveKey: (key: string) => void;
  selectedBook: string | null;
  onSwitchBook: (bookId: string) => void;
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

export function SettingsModal({
  open,
  onClose,
  isDark,
  onToggleTheme,
  hasKey,
  onSaveKey,
  selectedBook,
  onSwitchBook,
}: SettingsModalProps) {
  const [keyInput, setKeyInput] = useState("");
  const [reveal, setReveal] = useState(false);
  const [validating, setValidating] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);

  // Book picker state
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);
  const [booksError, setBooksError] = useState<string | null>(null);
  const [pickedBook, setPickedBook] = useState<string | null>(null);
  const [booksReloadKey, setBooksReloadKey] = useState(0);

  useEffect(() => {
    if (open) {
      setKeyInput("");
      setReveal(false);
      setValidating(false);
      setKeyError(null);
      setPickedBook(selectedBook);
    }
  }, [open, selectedBook]);

  // Fetch books when modal opens
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    setBooksLoading(true);
    setBooksError(null);
    fetchBooks({ signal: ctrl.signal })
      .then((b) => setBooks(b))
      .catch((e) => {
        if ((e as Error)?.name !== "AbortError") {
          setBooksError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => setBooksLoading(false));
    return () => ctrl.abort();
  }, [open, booksReloadKey]);

  if (!open) return null;

  const trimmed = keyInput.trim();

  const handleSwitchBook = () => {
    if (!pickedBook || pickedBook === selectedBook) return;
    onSwitchBook(pickedBook);
    onClose();
  };

  const handleSaveKey = async () => {
    if (!trimmed || validating) return;
    setKeyError(null);
    setValidating(true);
    const valid = await validateGeminiKey(trimmed);
    setValidating(false);
    if (!valid) {
      setKeyError("Key is invalid. Try again");
      return;
    }
    onSaveKey(trimmed);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        aria-hidden
        onClick={onClose}
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
      />

      <div className="relative z-10 flex w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--surface-2)]">
              <Settings className="h-4 w-4 text-[var(--muted)]" />
            </div>
            <h2 className="text-base font-semibold tracking-tight">Settings</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-5">

          {/* Appearance */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
              Appearance
            </p>
            <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
              <div className="flex items-center gap-3">
                {isDark ? (
                  <Moon className="h-4 w-4 text-[var(--muted)]" />
                ) : (
                  <Sun className="h-4 w-4 text-[var(--muted)]" />
                )}
                <div>
                  <div className="text-sm font-medium">Theme</div>
                  <div className="text-xs text-[var(--subtle)]">
                    {isDark ? "Dark mode" : "Light mode"}
                  </div>
                </div>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={isDark}
                aria-label="Toggle dark mode"
                onClick={onToggleTheme}
                className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
                style={{ backgroundColor: isDark ? "var(--accent)" : "var(--surface-3)" }}
              >
                <span
                  className="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition-transform duration-200"
                  style={{ transform: isDark ? "translateX(20px)" : "translateX(0px)" }}
                />
              </button>
            </div>
          </div>

          {/* Notebook */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
              Notebook
            </p>
            {booksLoading ? (
              <div className="flex items-center justify-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-5 text-sm text-[var(--muted)]">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading notebooks…
              </div>
            ) : booksError ? (
              <div className="flex flex-col items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-4 text-center">
                <div className="flex items-center gap-2 text-xs text-[var(--negative,#ef4444)]">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Couldn&apos;t load notebooks
                </div>
                <button
                  type="button"
                  onClick={() => setBooksReloadKey((k) => k + 1)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                  Retry
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <ul className="flex flex-col gap-1.5">
                  {books.map((book) => {
                    const active = pickedBook === book.book_id;
                    return (
                      <li key={book.book_id}>
                        <button
                          type="button"
                          onClick={() => setPickedBook(book.book_id)}
                          aria-pressed={active}
                          className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] ${
                            active
                              ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                              : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--accent)]"
                          }`}
                        >
                          <div
                            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                              active
                                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                                : "bg-[var(--surface-3)] text-[var(--muted)]"
                            }`}
                          >
                            {active ? <Check className="h-3.5 w-3.5" /> : <BookOpen className="h-3.5 w-3.5" />}
                          </div>
                          <span className="truncate text-sm font-medium">{book.title}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {pickedBook !== selectedBook && pickedBook && (
                  <button
                    type="button"
                    onClick={handleSwitchBook}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                  >
                    <Check className="h-4 w-4" />
                    Switch notebook
                  </button>
                )}
              </div>
            )}
          </div>

          {/* API Key */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
                Gemini API Key
              </p>
              {hasKey && (
                <span className="flex items-center gap-1 text-[11px] text-[var(--positive,#22c55e)]">
                  <Check className="h-3 w-3" />
                  Key saved
                </span>
              )}
            </div>

            <div className="space-y-2">
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                <input
                  type={reveal ? "text" : "password"}
                  value={keyInput}
                  onChange={(e) => { setKeyInput(e.target.value); setKeyError(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSaveKey(); }}
                  placeholder={hasKey ? "Enter new key to replace…" : "AIza…"}
                  autoComplete="off"
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

              {keyError && (
                <div className="flex items-start gap-2 rounded-lg border border-[var(--negative,#ef4444)]/30 bg-[var(--negative,#ef4444)]/10 px-3 py-2 text-xs text-[var(--negative,#ef4444)]">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {keyError}
                </div>
              )}

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
              </p>

              <button
                type="button"
                disabled={!trimmed || validating}
                onClick={handleSaveKey}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
              >
                {validating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Validating…
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    {hasKey ? "Update key" : "Save key"}
                  </>
                )}
              </button>

              <p className="text-[11px] text-[var(--subtle)]">
                Your key is never stored in our servers.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--border)] px-5 py-3">
          <p className="text-center text-xs text-[var(--subtle)]">Atlas · AI Research Agent</p>
        </div>
      </div>
    </div>
  );
}
