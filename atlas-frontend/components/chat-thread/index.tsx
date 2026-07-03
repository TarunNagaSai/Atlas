"use client";

import { forwardRef } from "react";
import { ChatSkeleton } from "@/components/chat-skeleton";
import { EmptyState } from "@/components/empty-state";
import { MessageBubble } from "@/components/message-bubble";
import type { Message } from "@/types";

interface ChatThreadProps {
  /** True while a persisted conversation is being fetched (DB mode) — shows a skeleton. */
  chatLoading: boolean;
  messages: Message[];
  /** Fires a suggested question from the empty state. */
  onPick: (text: string, model?: string, files?: File[]) => void;
  selectedBook: string | null;
}

/**
 * The scrollable message area: a skeleton while loading, the empty state on a
 * blank chat, otherwise the message thread. The scroll container ref is forwarded
 * so the page's auto-scroll effect can drive it.
 */
export const ChatThread = forwardRef<HTMLDivElement, ChatThreadProps>(
  function ChatThread({ chatLoading, messages, onPick, selectedBook }, ref) {
    return (
      <div ref={ref} className="flex-1 lg:overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 sm:py-8">
          {chatLoading ? (
            <ChatSkeleton />
          ) : messages.length === 0 ? (
            <EmptyState onPick={onPick} selectedBook={selectedBook} />
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
        </div>
      </div>
    );
  },
);
