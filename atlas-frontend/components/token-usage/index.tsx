import { Gauge } from "lucide-react";

interface TokenUsageProps {
  /** Total tokens consumed this session (input + output). */
  tokensUsed: number;
}

/** Compact integer formatting: 100000 -> "100K", 1240 -> "1.2K". */
function fmtTokens(n: number): string {
  if (n < 1000) return String(n);
  const k = n / 1000;
  return `${k % 1 === 0 ? k : k.toFixed(1)}K`;
}

/** Per-session token usage badge — total tokens consumed (input + output). */
export function TokenUsage({ tokensUsed }: TokenUsageProps) {
  return (
    <span
      title={`${tokensUsed.toLocaleString("en-US")} tokens used this session`}
      className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--muted)]"
    >
      <Gauge className="h-3.5 w-3.5 text-[var(--accent)]" />
      {fmtTokens(tokensUsed)} tokens
    </span>
  );
}
