"use client";

import { useState } from "react";
import { X, Layers, Cpu, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { OverviewTab } from "./overview-tab";
import { StackTab } from "./stack-tab";
import { DeveloperTab } from "./developer-tab";

const TABS = ["Overview", "Tech Stack", "Developer"] as const;
type Tab = (typeof TABS)[number];

interface AboutModalProps {
  open: boolean;
  onClose: () => void;
}

export function AboutModal({ open, onClose }: AboutModalProps) {
  const [tab, setTab] = useState<Tab>("Overview");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        aria-hidden
        onClick={onClose}
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
      />

      <div className="relative z-10 flex w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border)] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight">About Atlas</h2>
            <p className="mt-0.5 text-xs text-[var(--subtle)]">Finance AgenticRAG</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-[var(--border)] px-4 pt-3">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                "flex items-center gap-1.5 rounded-t-md px-3 pb-2.5 pt-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
                tab === t
                  ? "border-b-2 border-[var(--accent)] text-[var(--foreground)]"
                  : "text-[var(--subtle)] hover:text-[var(--foreground)]"
              )}
            >
              {t === "Overview" ? (
                <Layers className="h-3.5 w-3.5" />
              ) : t === "Tech Stack" ? (
                <Cpu className="h-3.5 w-3.5" />
              ) : (
                <User className="h-3.5 w-3.5" />
              )}
              {t}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
          {tab === "Overview" ? (
            <OverviewTab />
          ) : tab === "Tech Stack" ? (
            <StackTab />
          ) : (
            <DeveloperTab />
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--border)] px-5 py-3">
          <p className="text-center text-xs text-[var(--subtle)]">
            ✦ Thanks for visiting ✦
          </p>
        </div>
      </div>
    </div>
  );
}
