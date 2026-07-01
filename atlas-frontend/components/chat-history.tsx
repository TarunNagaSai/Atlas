"use client";

import { useEffect, useMemo, useState } from "react";
import { MessageSquare, Plus, Settings, TrendingUp, X } from "lucide-react";
import { SettingsModal } from "./settings-modal";
import { DAY_MS } from "@/lib/settings";

function useTheme() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    const dark = stored ? stored === "dark" : prefersDark;
    document.documentElement.classList.toggle("dark", dark);
    setIsDark(dark);
  }, []);

  const toggle = () => {
    setIsDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle("dark", next);
      localStorage.setItem("theme", next ? "dark" : "light");
      return next;
    });
  };

  return { isDark, toggle };
}
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/types";

interface ChatHistoryProps {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  /** Display name chosen at the picker; shown in the footer. */
  userName: string | null;
  /** Mobile drawer open state (always visible inline on desktop). */
  open: boolean;
  onClose: () => void;
  hasKey: boolean;
  onSaveKey: (key: string) => void;
  selectedBook: string | null;
  onSwitchBook: (bookId: string) => void;
}


/** Up to two uppercase initials from a display name (falls back to "?"). */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Bucket sessions into human-readable time groups. */
function groupSessions(sessions: ChatSession[]) {
  const now = Date.now();
  const groups: { label: string; items: ChatSession[] }[] = [
    { label: "Today", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Earlier", items: [] },
  ];
  for (const s of [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const age = now - s.updatedAt;
    if (age < DAY_MS) groups[0].items.push(s);
    else if (age < 7 * DAY_MS) groups[1].items.push(s);
    else groups[2].items.push(s);
  }
  return groups.filter((g) => g.items.length > 0);
}

export function ChatHistory({
  sessions,
  activeId,
  onSelect,
  onNewChat,
  userName,
  open,
  onClose,
  hasKey,
  onSaveKey,
  selectedBook,
  onSwitchBook,
}: ChatHistoryProps) {
  const { isDark, toggle } = useTheme();
  const displayName = userName?.trim() || "Demo user";
  const [query, setQuery] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);

  // The active chat is a fresh "New analysis" until its first turn is persisted
  // and it shows up in `sessions`. While it's an unlisted draft (or truly null),
  // the pinned row stands in for it — so it, not any saved entry, is highlighted.
  const newActive = !sessions.some((s) => s.id === activeId);

  // On mobile, picking a conversation or starting a new one dismisses the drawer.
  const handleSelect = (id: string) => {
    onSelect(id);
    onClose();
  };
  const handleNewChat = () => {
    onNewChat();
    onClose();
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, query]);

  const groups = useMemo(() => groupSessions(filtered), [filtered]);

  return (
    <>
      {/* Backdrop — mobile only, dismisses the drawer on tap. */}
      <div
        onClick={onClose}
        aria-hidden
        className={cn(
          "fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-full w-72 max-w-[85vw] shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] pl-[env(safe-area-inset-left)] transition-transform duration-300 ease-out",
          "lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:pl-0 lg:transition-none",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-sm)]">
          <TrendingUp className="h-[18px] w-[18px]" strokeWidth={2.4} />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">Atlas</div>
          <div className="text-[11px] font-medium text-[var(--subtle)]">
            AI Research Agent
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close sidebar"
          className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] lg:hidden"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={handleNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
        >
          <Plus className="h-4 w-4" strokeWidth={2.4} />
          New analysis
        </button>
      </div>

      {/* History */}
      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {/* New analysis is always the first/most-recent item */}
        <div className="mb-3">
          <div className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
            Today
          </div>
          <div className="space-y-0.5">
            <button
              type="button"
              onClick={newActive ? onClose : handleNewChat}
              className={cn(
                "group flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
                newActive ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
              )}
            >
              <MessageSquare
                className={cn(
                  "mt-0.5 h-4 w-4 shrink-0",
                  newActive ? "text-[var(--accent)]" : "text-[var(--subtle)]"
                )}
              />
              <span className={cn(
                "block truncate text-sm",
                newActive ? "font-medium text-[var(--accent-hover)]" : "text-[var(--foreground)]"
              )}>
                New analysis
              </span>
            </button>
            {/* Saved sessions in the Today group */}
            {(groups.find((g) => g.label === "Today")?.items ?? []).map((session) => {
              const active = session.id === activeId;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => handleSelect(session.id)}
                  className={cn(
                    "group flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
                    active ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                  )}
                >
                  <MessageSquare
                    className={cn(
                      "mt-0.5 h-4 w-4 shrink-0",
                      active ? "text-[var(--accent)]" : "text-[var(--subtle)]"
                    )}
                  />
                  <span className="min-w-0 flex-1">
                    <span className={cn(
                      "block truncate text-sm",
                      active ? "font-medium text-[var(--accent-hover)]" : "text-[var(--foreground)]"
                    )}>
                      {session.title}
                    </span>
                    {session.preview && (
                      <span className="block truncate text-xs text-[var(--subtle)]">
                        {session.preview}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
        {/* Previous 7 days and Earlier groups */}
        {groups
          .filter((g) => g.label !== "Today")
          .map((group) => (
            <div key={group.label} className="mb-3">
              <div className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.items.map((session) => {
                  const active = session.id === activeId;
                  return (
                    <button
                      key={session.id}
                      type="button"
                      onClick={() => handleSelect(session.id)}
                      className={cn(
                        "group flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
                        active ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                      )}
                    >
                      <MessageSquare
                        className={cn(
                          "mt-0.5 h-4 w-4 shrink-0",
                          active ? "text-[var(--accent)]" : "text-[var(--subtle)]"
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className={cn(
                          "block truncate text-sm",
                          active ? "font-medium text-[var(--accent-hover)]" : "text-[var(--foreground)]"
                        )}>
                          {session.title}
                        </span>
                        {session.preview && (
                          <span className="block truncate text-xs text-[var(--subtle)]">
                            {session.preview}
                          </span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        <div className="flex w-full items-center gap-2.5 text-left">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-3)] text-xs font-semibold text-[var(--muted)]">
            {initials(displayName)}
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-medium">{displayName}</div>
            <div className="truncate text-xs text-[var(--subtle)]">
              Demo workspace
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Open settings"
            title="Settings"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>

    <SettingsModal
      open={settingsOpen}
      onClose={() => setSettingsOpen(false)}
      isDark={isDark}
      onToggleTheme={toggle}
      hasKey={hasKey}
      onSaveKey={onSaveKey}
      selectedBook={selectedBook}
      onSwitchBook={onSwitchBook}
    />
    </>
  );
}
