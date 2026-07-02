"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { ChartSpec } from "@/lib/chart";

/**
 * Renders one agent-drawn chart (the `` ```chart `` block, already parsed into a
 * validated {@link ChartSpec}) with Recharts. Two shapes, both aimed at financial
 * comparison: a grouped `bar` chart (metrics side by side across categories) and a
 * multi-series `line` chart (trends over an ordered axis). Colors come from the
 * `--chart-N` CSS palette so both light and dark themes track automatically.
 */

// The six series colors, as CSS-var references so the active theme resolves them.
const PALETTE = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const;

const seriesColor = (i: number) => PALETTE[i % PALETTE.length];

/** Compact axis-tick formatting (4680 → "4.68K", 1_200_000 → "1.2M"). */
function formatCompact(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const trim = (n: number) => Number(n.toFixed(2)).toString();
  if (abs >= 1e12) return `${sign}${trim(abs / 1e12)}T`;
  if (abs >= 1e9) return `${sign}${trim(abs / 1e9)}B`;
  if (abs >= 1e6) return `${sign}${trim(abs / 1e6)}M`;
  if (abs >= 1e3) return `${sign}${trim(abs / 1e3)}K`;
  return trim(value);
}

/** Full, grouped formatting for tooltip values (4680 → "4,680"). */
function formatFull(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** Reshape parallel {categories, series[]} into Recharts' per-category rows. */
function toRows(spec: ChartSpec): Record<string, string | number>[] {
  return spec.categories.map((category, i) => {
    const row: Record<string, string | number> = { category };
    for (const s of spec.series) row[s.name] = s.data[i];
    return row;
  });
}

/** Themed tooltip so the popover matches the app surface instead of Recharts' default white. */
function ChartTooltip({
  active,
  payload,
  label,
  unit,
}: Partial<TooltipContentProps<number, string>> & { unit?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-[var(--shadow-md)]">
      <p className="mb-1 font-medium text-[var(--foreground)]">{label}</p>
      <ul className="space-y-0.5">
        {payload.map((entry) => (
          <li key={String(entry.name)} className="flex items-center gap-2">
            <span
              className="h-2 w-2 shrink-0 rounded-[2px]"
              style={{ background: entry.color }}
            />
            <span className="text-[var(--subtle)]">{entry.name}</span>
            <span className="ml-auto font-medium tabular-nums text-[var(--foreground)]">
              {typeof entry.value === "number" ? formatFull(entry.value) : entry.value}
              {unit ? ` ${unit}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChartBlock({ spec }: { spec: ChartSpec }) {
  // Recharts' ResponsiveContainer measures the DOM, so only render it after mount
  // to avoid a zero-width SSR pass and hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const rows = toRows(spec);

  const axisTick = { fill: "var(--subtle)", fontSize: 11 };
  const axisLabelStyle = { fill: "var(--muted)", fontSize: 11 };
  const gridStroke = "var(--border)";

  const xAxis = (
    <XAxis
      dataKey="category"
      tick={axisTick}
      tickLine={false}
      stroke="var(--border-strong)"
      label={
        spec.xLabel
          ? {
              value: spec.xLabel,
              position: "insideBottom",
              offset: -2,
              style: axisLabelStyle,
            }
          : undefined
      }
    />
  );

  const yAxis = (
    <YAxis
      tick={axisTick}
      tickLine={false}
      stroke="var(--border-strong)"
      width={48}
      tickFormatter={formatCompact}
      label={
        spec.yLabel
          ? {
              value: spec.yLabel,
              angle: -90,
              position: "insideLeft",
              style: { ...axisLabelStyle, textAnchor: "middle" },
            }
          : undefined
      }
    />
  );

  const shared = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
      {xAxis}
      {yAxis}
      <Tooltip
        cursor={{ fill: "var(--surface-2)", fillOpacity: 0.5 }}
        content={<ChartTooltip unit={spec.unit} />}
      />
      <Legend
        wrapperStyle={{ fontSize: 12, color: "var(--muted)", paddingTop: 8 }}
      />
    </>
  );

  const margin = {
    top: 8,
    right: 12,
    bottom: spec.xLabel ? 16 : 0,
    left: spec.yLabel ? 8 : 0,
  };

  return (
    <figure className="my-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
      {spec.title && (
        <figcaption className="mb-2 px-1 text-sm font-semibold text-[var(--foreground)]">
          {spec.title}
        </figcaption>
      )}
      <div className="h-[280px] w-full">
        {mounted && (
          <ResponsiveContainer width="100%" height="100%">
            {spec.type === "bar" ? (
              <BarChart data={rows} margin={margin} barGap={2} barCategoryGap="24%">
                {shared}
                {spec.series.map((s, i) => (
                  <Bar
                    key={s.name}
                    dataKey={s.name}
                    fill={seriesColor(i)}
                    radius={[3, 3, 0, 0]}
                    maxBarSize={56}
                  />
                ))}
              </BarChart>
            ) : (
              <LineChart data={rows} margin={margin}>
                {shared}
                {spec.series.map((s, i) => (
                  <Line
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={seriesColor(i)}
                    strokeWidth={2}
                    dot={{ r: 3, fill: seriesColor(i), strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </figure>
  );
}
