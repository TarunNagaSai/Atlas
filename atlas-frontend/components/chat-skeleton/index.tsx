/** Two-turn shimmer shown while a persisted conversation is being fetched (DB mode). */
export function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      {/* User message */}
      <div className="flex justify-end">
        <div className="h-9 w-48 rounded-2xl rounded-br-md bg-[var(--surface-2)]" />
      </div>
      {/* Assistant message */}
      <div className="flex gap-3">
        <div className="h-8 w-8 shrink-0 rounded-lg bg-[var(--surface-2)]" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 w-16 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-full rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-5/6 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-4/6 rounded bg-[var(--surface-2)]" />
        </div>
      </div>
      {/* User message */}
      <div className="flex justify-end">
        <div className="h-9 w-64 rounded-2xl rounded-br-md bg-[var(--surface-2)]" />
      </div>
      {/* Assistant message */}
      <div className="flex gap-3">
        <div className="h-8 w-8 shrink-0 rounded-lg bg-[var(--surface-2)]" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 w-16 rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-full rounded bg-[var(--surface-2)]" />
          <div className="h-3 w-3/4 rounded bg-[var(--surface-2)]" />
        </div>
      </div>
    </div>
  );
}
