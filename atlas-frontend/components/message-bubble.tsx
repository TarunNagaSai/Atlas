"use client";

import {
  Copy,
  FileSpreadsheet,
  FileText,
  ImageIcon,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatBytes } from "@/lib/attachments";
import { renderMarkdown } from "@/lib/markdown";
import { ThinkingSteps } from "./thinking-steps";
import type { Message, MessageAttachment } from "@/types";

const ATTACHMENT_ICON: Record<
  MessageAttachment["kind"],
  { Icon: typeof FileText; className: string }
> = {
  image: { Icon: ImageIcon, className: "text-[var(--accent)]" },
  pdf: { Icon: FileText, className: "text-[#e5484d]" },
  word: { Icon: FileText, className: "text-[#4a7cf6]" },
  excel: { Icon: FileSpreadsheet, className: "text-[#16a34a]" },
};

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    const attachments = message.attachments ?? [];
    return (
      <div className="flex animate-rise flex-col items-end gap-1.5">
        {attachments.length > 0 && (
          <div className="flex max-w-[80%] flex-wrap justify-end gap-1.5">
            {attachments.map((a, i) => {
              const { Icon, className } = ATTACHMENT_ICON[a.kind];
              return (
                <div
                  key={`${a.name}-${i}`}
                  className="flex max-w-[200px] items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] py-1.5 pl-1.5 pr-2.5"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-2)]">
                    <Icon className={`h-4 w-4 ${className}`} />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-[var(--foreground)]">
                      {a.name}
                    </p>
                    <p className="text-[11px] text-[var(--subtle)]">
                      {formatBytes(a.size)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {message.content && (
          <div className="max-w-[80%] rounded-2xl rounded-br-md bg-[var(--accent)] px-4 py-2.5 text-sm leading-relaxed text-[var(--accent-fg)] shadow-[var(--shadow-sm)]">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        )}
      </div>
    );
  }

  // Render markdown (+ math) and pull out any inline [Source: …] tags so they
  // become numbered chips and feed the Sources list below.
  const { html } = message.pending
    ? { html: "" }
    : renderMarkdown(message.content);

  const thinking = message.thinking ?? [];
  const hasThinking = thinking.length > 0;

  return (
    <div className="flex animate-rise gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)] ring-1 ring-[var(--border)]">
        <TrendingUp className="h-4 w-4" strokeWidth={2.4} />
      </div>

      <div className="group min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight">Atlas</span>
          <span className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--subtle)]">
            Grounded
          </span>
        </div>

        {hasThinking && (
          <ThinkingSteps steps={thinking} busy={Boolean(message.pending)} />
        )}

        {message.pending ? (
          // While the agent reasons, the thinking panel carries the activity;
          // fall back to the typing dots only before any step has streamed.
          hasThinking ? null : <TypingIndicator />
        ) : (
          <div
            className="markdown"
            // markdown-it output is sanitised (no HTML input from users)
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}

        {!message.pending && (
          <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(message.content)}
              className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)]"
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className={cn("dot h-2 w-2 rounded-full bg-[var(--subtle)]")} />
      <span className={cn("dot h-2 w-2 rounded-full bg-[var(--subtle)]")} />
      <span className={cn("dot h-2 w-2 rounded-full bg-[var(--subtle)]")} />
    </div>
  );
}
