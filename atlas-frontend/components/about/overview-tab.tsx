"use client";

import { BUSINESS_POINTS } from "./data";

export function OverviewTab() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        Atlas is a fully agentic Finance AI platform — built on advanced AI
        engineering primitives that go far beyond basic retrieval.
      </p>
      <div className="space-y-3">
        {BUSINESS_POINTS.map((pt) => (
          <div
            key={pt.title}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3"
          >
            <p className="text-sm font-medium text-[var(--foreground)]">
              {pt.title}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-[var(--subtle)]">
              {pt.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
