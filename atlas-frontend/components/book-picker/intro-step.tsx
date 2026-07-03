"use client";

import { ArrowRight, Sparkles } from "lucide-react";

/** Welcome/overview screen shown once before notebook selection. */
export function IntroStep({ onStart }: { onStart: () => void }) {
  return (
    <>
      <div className="flex flex-col items-center gap-4 px-6 py-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
          <Sparkles className="h-6 w-6" />
        </div>
        <p className="max-w-sm text-sm leading-relaxed text-[var(--muted)]">
          Atlas is a demo project that showcases accurate data retrieval. Explore
          the curated notebooks, then start your own chats with the same data.
        </p>
      </div>

      <div className="border-t border-[var(--border)] px-5 py-3">
        <button
          type="button"
          onClick={onStart}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent)] py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
        >
          Start demo
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </>
  );
}
