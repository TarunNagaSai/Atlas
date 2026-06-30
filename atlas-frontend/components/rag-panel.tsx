"use client";

import { useState } from "react";
import { Download, FileText, Database, Github, ChevronDown, ChevronUp, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentStep } from "@/types";
import { AboutModal } from "./about-modal";

const BOOK_MAP: Record<string, { title: string; filename: string }> = {
  "92cca65f9a719c17": {
    title: "JP Morgan Annual Report 2025",
    filename: "jp-morgan-annual-report-2025.pdf",
  },
  "bf18b7be76e3aec2": {
    title: "JIO IPO",
    filename: "jio-ipo.pdf",
  },
};

interface RagPanelProps {
  selectedBook: string | null;
  fileCount: number;
  /** Open state. Inline when open on desktop; an overlay drawer on mobile. */
  open: boolean;
  onClose: () => void;
  /** Tool calls from the current assistant turn, shown below the document. */
  steps?: AgentStep[];
}

export function RagPanel({ selectedBook, fileCount, open, onClose, steps }: RagPanelProps) {
  const book = selectedBook ? BOOK_MAP[selectedBook] : undefined;
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <>
      {/* Backdrop — mobile only. */}
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
          "fixed inset-y-0 right-0 z-50 flex h-full w-80 max-w-[85vw] shrink-0 flex-col border-l border-[var(--border)] bg-[var(--surface)] pr-[env(safe-area-inset-right)] transition-transform duration-300 ease-out",
          "lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:pr-0 lg:transition-none",
          open ? "translate-x-0 lg:flex" : "translate-x-full lg:hidden",
        )}
      >
      <div className="flex items-center justify-between px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Knowledge base</h2>
          <p className="mt-0.5 text-xs text-[var(--subtle)]">
            Documents indexed for retrieval
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--muted)]">
          <Database className="h-3.5 w-3.5 text-[var(--accent)]" />
          {fileCount} {fileCount === 1 ? "source" : "sources"}
        </span>
      </div>

      <div className="px-3 py-2">
        {book ? (
          <div className="flex items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--accent)]">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[var(--foreground)]">
                {book.title}
              </p>
              <p className="text-xs text-[var(--subtle)]">PDF</p>
            </div>
            <a
              href={`/${book.filename}`}
              download={book.filename}
              aria-label={`Download ${book.title}`}
              className="shrink-0 text-[var(--subtle)] transition-colors hover:text-[var(--accent)]"
            >
              <Download className="h-4 w-4" />
            </a>
          </div>
        ) : (
          <div className="px-3 py-8 text-center">
            <FileText className="mx-auto h-6 w-6 text-[var(--subtle)]" />
            <p className="mt-2 text-sm text-[var(--muted)]">No document</p>
          </div>
        )}
      </div>

      <div className="flex-1" />

      <footer className="mt-auto border-t border-[var(--border)] p-2">
        <div className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2">
          <a
            href="https://github.com/TarunNagaSai/Atlas.git"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View source on GitHub"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            <Github className="h-4 w-4" />
          </a>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-medium">Atlas</div>
            <div className="truncate text-xs text-[var(--subtle)]">AI Research Agent</div>
          </div>
          <button
            type="button"
            onClick={() => setAboutOpen(true)}
            className="flex h-6 shrink-0 items-center justify-center rounded-md px-2 text-xs text-[var(--subtle)] transition-colors hover:bg-[var(--surface-3)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            About
          </button>
        </div>
      </footer>
    </aside>


      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </>
  );
}

function StepRow({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);
  const hasResult = Boolean(step.result);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={() => hasResult && setOpen((v) => !v)}
        disabled={!hasResult}
        className="flex w-full items-center gap-2 px-3 py-2 text-left disabled:cursor-default"
      >
        <Wrench className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
        <span className="flex-1 truncate text-xs font-medium text-[var(--foreground)]">
          {step.name}
        </span>
        {hasResult ? (
          open ? (
            <ChevronUp className="h-3.5 w-3.5 shrink-0 text-[var(--subtle)]" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--subtle)]" />
          )
        ) : (
          <span className="shrink-0 text-xs text-[var(--subtle)]">…</span>
        )}
      </button>
      {open && hasResult && (
        <div className="border-t border-[var(--border)] px-3 py-2">
          <p className="line-clamp-6 whitespace-pre-wrap text-xs text-[var(--muted)]">
            {step.result}
          </p>
        </div>
      )}
    </div>
  );
}
