"use client";

import { useState } from "react";
import { AlertTriangle, BookOpen, Check, Loader2, RotateCw, User } from "lucide-react";
import { track } from "@/lib/analytics";
import { useBooks } from "@/lib/books";

interface BookStepProps {
  onConfirm: (bookId: string, name: string) => void;
}

/** Step 1 — display name + notebook selection. Owns its own picked/name state. */
export function BookStep({ onConfirm }: BookStepProps) {
  // Books come from the shared store (fetched once at app open), not a per-open
  // network call.
  const { books, loading, error: fetchError, reload } = useBooks();
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");

  const trimmedName = name.trim();

  const handleConfirm = () => {
    if (!picked || !trimmedName) return;
    track("book_selected", { book_id: picked });
    onConfirm(picked, trimmedName);
  };

  return (
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
              onClick={reload}
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
            onClick={handleConfirm}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <Check className="h-4 w-4" />
            Continue
          </button>
        </div>
      )}
    </>
  );
}
