"use client";

import { useEffect, useState } from "react";
import { track } from "@vercel/analytics";
import {
  BarChart3,
  Building2,
  FileSearch,
  Landmark,
  ScrollText,
  ShieldAlert,
  TrendingUp,
  Users,
} from "lucide-react";
import { fetchBooks } from "@/lib/api";

const defaultSuggestions = [
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

// Notebook-specific suggestions for the demo books. Indexes mirror the
// ordering baked into BookPicker's source labels (0 = Jio DRHP, 1 = JPMorgan).
const jioSuggestions = [
  {
    icon: Users,
    title: "Management & promoters",
    prompt:
      "Who are the key managerial personnel and promoters listed in the DRHP? Are they founders with a long-term stake in the company, and what is their track record?",
  },
  {
    icon: Building2,
    title: "Business overview",
    prompt:
      "What does the company do, and what are its key products, services, and business segments?",
  },
  {
    icon: BarChart3,
    title: "Revenue & profitability",
    prompt:
      "What was the company's total revenue, EBITDA, and net profit for each of the last three fiscal years?",
  },
  {
    icon: TrendingUp,
    title: "Subscriber metrics",
    prompt:
      "What is the subscriber base and ARPU (average revenue per user), and how have they changed over the last three fiscal years?",
  },
];

const jpMorganSuggestions = [
  {
    icon: Users,
    title: "Management team",
    prompt:
      "Who are the members of the executive management team? How long have they been with the company, and what is their track record?",
  },
  {
    icon: Building2,
    title: "Business overview",
    prompt:
      "What are the company's primary business segments, and what products or services does each one offer?",
  },
  {
    icon: BarChart3,
    title: "Net revenue & income",
    prompt:
      "What was the total net revenue, net income, and diluted EPS reported for the most recent fiscal year?",
  },
  {
    icon: Landmark,
    title: "Capital ratios",
    prompt:
      "What CET1 capital ratio and return on tangible common equity (ROTCE) were reported in the annual report?",
  },
];

export function EmptyState({
  onPick,
  selectedBook,
}: {
  onPick: (prompt: string) => void;
  selectedBook?: string | null;
}) {
  const [suggestions, setSuggestions] = useState(defaultSuggestions);

  useEffect(() => {
    if (!selectedBook) {
      setSuggestions(defaultSuggestions);
      return;
    }
    const ctrl = new AbortController();
    fetchBooks({ signal: ctrl.signal })
      .then((books) => {
        const index = books.findIndex((b) => b.book_id === selectedBook);
        setSuggestions(
          index === 0 ? jioSuggestions : index === 1 ? jpMorganSuggestions : defaultSuggestions
        );
      })
      .catch(() => setSuggestions(defaultSuggestions));
    return () => ctrl.abort();
  }, [selectedBook]);

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
