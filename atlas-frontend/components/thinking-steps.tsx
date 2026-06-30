"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, FileText, Search, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { renderMarkdown } from "@/lib/markdown";
import type { ThinkingStep } from "@/types";

/** Friendly labels for the tools the agent can call. */
const TOOL_LABEL: Record<string, string> = {
  retrieve: "Searched the documents",
  graph_search: "Explored the knowledge graph",
};

/**
 * The agent's reasoning timeline, rendered as a collapsible "thinking" panel
 * above the answer (Gemini-style). It auto-expands while the agent works and
 * collapses to a one-line summary once the answer starts streaming; the user can
 * re-open it anytime.
 */
export function ThinkingSteps({
  steps,
  busy,
}: {
  steps: ThinkingStep[];
  /** True until the final answer starts streaming. */
  busy: boolean;
}) {
  // Open while thinking; collapse once the answer arrives. A manual toggle in
  // between is respected — only the busy→idle transition auto-collapses.
  const [open, setOpen] = useState(busy);
  const prevBusy = useRef(busy);
  useEffect(() => {
    if (prevBusy.current && !busy) setOpen(false);
    else if (!prevBusy.current && busy) setOpen(true);
    prevBusy.current = busy;
  }, [busy]);

  if (steps.length === 0) return null;

  const label = busy
    ? "Thinking…"
    : open
      ? "Hide thinking"
      : "Show thinking";

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-2)] py-1.5 pl-2.5 pr-3 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-3)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]",
        )}
      >
        <Sparkles
          className={cn(
            "h-4 w-4 text-[var(--accent)]",
            busy && "animate-pulse",
          )}
          strokeWidth={2.2}
        />
        <span className={cn(busy && "thinking-shimmer")}>{label}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-[var(--subtle)] transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <ol className="mt-3 ml-2 space-y-4 border-l border-[var(--border)] pl-4">
          {steps.map((step, i) => (
            <li key={i} className="animate-rise">
              {(step.kind === "plan" || step.kind === "thought") && (
                <ProseStep text={step.text} />
              )}
              {step.kind === "tool_call" && (
                <div className="text-sm">
                  <div className="flex items-center gap-2 font-medium text-[var(--foreground)]">
                    <Search className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
                    {TOOL_LABEL[step.name] ?? step.name}
                  </div>
                  {queryOf(step.args) && (
                    <code className="mt-1 ml-[1.375rem] block w-fit max-w-full truncate rounded-md bg-[var(--surface-2)] px-2 py-0.5 font-mono text-xs text-[var(--muted)]">
                      {queryOf(step.args)}
                    </code>
                  )}
                </div>
              )}
              {step.kind === "tool_result" && (
                <ToolResult name={step.name} result={step.result} />
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/**
 * A streamed plan/thought block. The model writes markdown (often a bold section
 * header followed by a short paragraph), so render it through the shared markdown
 * pipeline and style it as muted reasoning prose.
 */
function ProseStep({ text }: { text: string }) {
  const { html } = renderMarkdown(text);
  return (
    <div
      className="thinking-prose"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** One retrieved passage, parsed out of a `retrieve` tool result. */
interface Passage {
  citation: string;
  text: string;
}

/**
 * The `retrieve` tool joins passages with `\n\n---\n\n`, each prefixed with a
 * `[Source: file#page]` tag (see `retrieve()` in app/tools/tools.py). Split them
 * back apart so each doc-search hit renders as its own sourced card. Returns an
 * empty list for non-retrieval / message results (handled by the fallback).
 */
function parsePassages(result: string): Passage[] {
  return result
    .split(/\n\n-{3,}\n\n/)
    .map((block) => {
      const m = block.match(/^\s*\[Source:\s*([^\]]+)\]\s*([\s\S]*)$/);
      return m ? { citation: m[1].trim(), text: m[2].trim() } : null;
    })
    .filter((p): p is Passage => p !== null && p.text.length > 0);
}

/**
 * A tool's result. Retrieval hits are parsed into per-source passage cards and
 * shown expanded by default (so every doc search and retrieval is visible);
 * anything else falls back to a collapsed raw view.
 */
function ToolResult({ name, result }: { name: string; result: string }) {
  const passages = parsePassages(result);
  // Show retrieved passages by default; keep opaque/error results tucked away.
  const [show, setShow] = useState(passages.length > 0);
  if (!result) return null;

  if (passages.length > 0) {
    return (
      <div className="text-sm">
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="flex items-center gap-2 font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
        >
          <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--subtle)]" />
          Retrieved {passages.length} passage{passages.length === 1 ? "" : "s"}
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
              show && "rotate-180",
            )}
          />
        </button>
        {show && (
          <ol className="mt-2 ml-[1.375rem] space-y-2">
            {passages.map((p, i) => (
              <li
                key={i}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2.5"
              >
                <div className="flex items-center gap-1.5 font-mono text-xs font-medium text-[var(--accent)]">
                  <FileText className="h-3 w-3 shrink-0" />
                  <span className="truncate">{p.citation}</span>
                </div>
                <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-xs leading-relaxed text-[var(--muted)]">
                  {p.text}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    );
  }

  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="flex items-center gap-2 text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
      >
        <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--subtle)]" />
        Result from {TOOL_LABEL[name] ?? name}
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
            show && "rotate-180",
          )}
        />
      </button>
      {show && (
        <pre className="mt-1.5 ml-[1.375rem] max-h-60 overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-xs text-[var(--muted)]">
          {result}
        </pre>
      )}
    </div>
  );
}

/** Best-effort one-line summary of a tool call's arguments. */
function queryOf(args: Record<string, unknown>): string {
  const q = args.query ?? args.q;
  if (typeof q === "string") return q;
  const keys = Object.keys(args);
  return keys.length ? JSON.stringify(args) : "";
}
