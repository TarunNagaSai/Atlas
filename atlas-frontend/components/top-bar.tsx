"use client";

import { Menu, PanelRight } from "lucide-react";
import { track } from "@vercel/analytics";
import { cn } from "@/lib/utils";

interface TopBarProps {
  title: string;
  fileCount: number;
  panelOpen: boolean;
  onTogglePanel: () => void;
  /** Opens the chat-history drawer on mobile. */
  onOpenNav: () => void;
}

export function TopBar({
  title,
  panelOpen,
  onTogglePanel,
  onOpenNav,
}: TopBarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--surface)] px-3 pt-[env(safe-area-inset-top)] sm:px-4">
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open menu"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="truncate text-sm font-semibold tracking-tight">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => { track("hire_me_clicked"); window.location.href = "mailto:tarunnagasai@icloud.com"; }}
          className="flex h-8 items-center justify-center rounded-lg bg-[var(--accent)] px-3 text-xs font-semibold text-[var(--accent-fg)] shadow-sm transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
        >
          Hire Me
        </button>
        <button
          type="button"
          onClick={onTogglePanel}
          aria-label="Toggle knowledge base"
          aria-pressed={panelOpen}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
            panelOpen
              ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
              : "border-[var(--border)] text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--foreground)]"
          )}
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
