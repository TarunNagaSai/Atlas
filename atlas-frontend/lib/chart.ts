/**
 * Inline chart support for assistant answers.
 *
 * The agent draws a chart by writing a fenced code block tagged ```chart into
 * its answer, containing a single JSON object (see {@link ChartSpec}). Because
 * the chart lives in the answer text, it needs no new SSE event and it replays
 * for free from persisted history — it is just part of `message.content`.
 *
 * `parseAnswerSegments` splits an answer into an ordered list of markdown and
 * chart segments so `MessageBubble` can render prose as markdown and each chart
 * block as a real React component (`ChartBlock`) exactly where it appears. A
 * chart fence that has not finished streaming yet becomes a `chart-pending`
 * segment (a placeholder), so a half-arrived block never flashes raw JSON.
 */

export type ChartType = "bar" | "line";

/** One plotted series — its values line up 1:1 with {@link ChartSpec.categories}. */
export interface ChartSeries {
  name: string;
  data: number[];
}

/** A validated chart the agent asked to draw. */
export interface ChartSpec {
  type: ChartType;
  title: string;
  /** Axis captions and a unit hint (e.g. "USD M") — all optional. */
  xLabel?: string;
  yLabel?: string;
  unit?: string;
  /** X-axis tick labels (fiscal years, departments, quarters, …). */
  categories: string[];
  series: ChartSeries[];
}

/** An ordered piece of an answer: prose, a finished chart, or one still streaming. */
export type AnswerSegment =
  | { kind: "markdown"; text: string }
  | { kind: "chart"; spec: ChartSpec }
  | { kind: "chart-invalid" }
  | { kind: "chart-pending" };

// Opening fence: ```chart at a line start (allowing leading indentation and
// trailing whitespace), followed by a newline. `m` so ^ matches each line.
const OPEN_FENCE = /^[ \t]*```chart[ \t]*\r?\n/m;
// Closing fence: a line that is just ``` (any indent / trailing space).
const CLOSE_FENCE = /\r?\n[ \t]*```[ \t]*(?:\r?\n|$)/;

function pushMarkdown(out: AnswerSegment[], text: string): void {
  if (text.trim().length > 0) out.push({ kind: "markdown", text });
}

/**
 * Coerce a parsed JSON value into a {@link ChartSpec}, or return null if it does
 * not describe a chart we can draw. Kept strict on purpose: a malformed block
 * renders nothing rather than a broken axis.
 */
export function validateChartSpec(value: unknown): ChartSpec | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;

  const type = v.type;
  if (type !== "bar" && type !== "line") return null;

  const categories = v.categories;
  if (!Array.isArray(categories) || categories.length === 0) return null;
  const cats = categories.map((c) => String(c));

  const rawSeries = v.series;
  if (!Array.isArray(rawSeries) || rawSeries.length === 0) return null;

  const series: ChartSeries[] = [];
  for (const s of rawSeries) {
    if (!s || typeof s !== "object") return null;
    const so = s as Record<string, unknown>;
    const data = so.data;
    if (!Array.isArray(data) || data.length !== cats.length) return null;
    const nums = data.map((n) => Number(n));
    if (nums.some((n) => !Number.isFinite(n))) return null;
    series.push({ name: String(so.name ?? "Series"), data: nums });
  }

  return {
    type,
    title: typeof v.title === "string" && v.title.trim() ? v.title : "Chart",
    xLabel: typeof v.xLabel === "string" ? v.xLabel : undefined,
    yLabel: typeof v.yLabel === "string" ? v.yLabel : undefined,
    unit: typeof v.unit === "string" ? v.unit : undefined,
    categories: cats,
    series,
  };
}

/** Split an answer into ordered markdown / chart segments. */
export function parseAnswerSegments(content: string): AnswerSegment[] {
  const out: AnswerSegment[] = [];
  let rest = content;

  for (;;) {
    const open = OPEN_FENCE.exec(rest);
    if (!open) {
      pushMarkdown(out, rest);
      break;
    }

    pushMarkdown(out, rest.slice(0, open.index));
    const bodyStart = open.index + open[0].length;
    const body = rest.slice(bodyStart);

    const close = CLOSE_FENCE.exec(body);
    if (!close) {
      // Fence opened but not yet closed — still streaming in.
      out.push({ kind: "chart-pending" });
      break;
    }

    const json = body.slice(0, close.index);
    let spec: ChartSpec | null = null;
    try {
      spec = validateChartSpec(JSON.parse(json));
    } catch {
      spec = null;
    }
    out.push(spec ? { kind: "chart", spec } : { kind: "chart-invalid" });

    rest = body.slice(close.index + close[0].length);
  }

  return out;
}

/**
 * Strip ```chart blocks from an answer, leaving just the prose. Used when copying
 * a message so the clipboard gets readable text, not raw chart JSON.
 */
export function stripChartBlocks(content: string): string {
  return parseAnswerSegments(content)
    .map((seg) => (seg.kind === "markdown" ? seg.text : ""))
    .join("")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
