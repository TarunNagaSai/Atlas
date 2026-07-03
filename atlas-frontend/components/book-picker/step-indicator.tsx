"use client";

import { Check } from "lucide-react";

/** Two-dot progress header for the setup flow (notebook → API key). */
export function StepIndicator({ step }: { step: "book" | "key" }) {
  return (
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
  );
}
