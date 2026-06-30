"use client";

import { STACK, AI_TECHNIQUES } from "./data";

export function StackTab() {
  return (
    <div className="space-y-5">
      {STACK.map((group) => (
        <div key={group.layer}>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
            {group.layer}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {group.items.map((item) => (
              <div
                key={item.name}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5"
              >
                <p className="text-sm font-medium text-[var(--foreground)]">
                  {item.name}
                </p>
                <p className="mt-0.5 text-xs text-[var(--subtle)]">
                  {item.note}
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--subtle)]">
          AI Engineering
        </p>
        <div className="space-y-2">
          {AI_TECHNIQUES.map((t) => (
            <div
              key={t.title}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3"
            >
              <p className="text-sm font-medium text-[var(--foreground)]">
                {t.title}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[var(--subtle)]">
                {t.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
