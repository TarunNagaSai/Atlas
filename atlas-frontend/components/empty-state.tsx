"use client";

import { track } from "@vercel/analytics";
import {
  BarChart3,
  FileSearch,
  ScrollText,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

const suggestions = [
  {
    icon: BarChart3,
    title: "Summarize Q3 earnings",
    prompt: "Summarize the key takeaways from the Q3 earnings report.",
  },
  {
    icon: ShieldAlert,
    title: "Surface risk factors",
    prompt: "What are the most significant risk factors disclosed this year?",
  },
  {
    icon: ScrollText,
    title: "Extract covenants",
    prompt: "List all financial covenants in the credit agreement.",
  },
  {
    icon: FileSearch,
    title: "Compare segments",
    prompt: "Compare revenue growth across business segments year over year.",
  },
];

export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-md)]">
        <TrendingUp className="h-7 w-7" strokeWidth={2.4} />
      </div>
      <h1 className="mt-5 text-2xl font-semibold tracking-tight">
        What can I help you analyze?
      </h1>
      <p className="mt-2 max-w-md text-sm text-[var(--muted)]">
        Ask questions about your filings, contracts, and reports. Atlas retrieves
        the relevant passages and answers with citations.
      </p>

      <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
        {suggestions.map((s) => (
          <button
            key={s.title}
            type="button"
            onClick={() => {
              track("suggestion_clicked", { title: s.title });
              onPick(s.prompt);
            }}
            className="group flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3.5 text-left shadow-[var(--shadow-sm)] transition-all hover:border-[var(--accent)] hover:shadow-[var(--shadow-md)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
              <s.icon className="h-[18px] w-[18px]" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-[var(--foreground)]">
                {s.title}
              </div>
              <div className="mt-0.5 text-xs leading-relaxed text-[var(--muted)]">
                {s.prompt}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
