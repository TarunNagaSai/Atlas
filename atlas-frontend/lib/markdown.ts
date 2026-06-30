import MarkdownIt from "markdown-it";
import type StateInline from "markdown-it/lib/rules_inline/state_inline.mjs";
import katex from "katex";

/**
 * Markdown renderer with LaTeX math support.
 *
 * Math handling is deliberately conservative for *financial* answers:
 *
 * - Only `$$...$$`, `\[...\]` (display) and `\(...\)` (inline) are treated as
 *   math. A bare single `$` is NEVER a math delimiter, because the model emits
 *   currency like "$3,875,393 million" in normal prose — treating `$` as math
 *   would swallow whole sentences between two unrelated dollar amounts.
 * - Literal `$` *inside* a math block (e.g. `\frac{$4,002,814}{$3,875,393}`) is
 *   escaped to `\$` before being handed to KaTeX, so currency renders instead
 *   of erroring.
 */

function renderMath(src: string, displayMode: boolean): string {
  // Escape un-escaped `$` (currency) so KaTeX renders a literal dollar sign.
  const tex = src.trim().replace(/(?<!\\)\$/g, "\\$");
  try {
    return katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      strict: false,
    });
  } catch {
    return `<code>${displayMode ? "$$" : "$"}${src}${
      displayMode ? "$$" : "$"
    }</code>`;
  }
}

/** Scans for a closing delimiter and emits a math token; shared by all rules. */
function mathRule(
  open: string,
  close: string,
  displayMode: boolean,
  name: string,
) {
  return (state: StateInline, silent: boolean): boolean => {
    const { src, pos } = state;
    if (!src.startsWith(open, pos)) return false;

    const contentStart = pos + open.length;
    const end = src.indexOf(close, contentStart);
    if (end === -1) return false;

    if (!silent) {
      const token = state.push(name, "", 0);
      token.content = src.slice(contentStart, end);
      token.meta = { displayMode };
    }
    state.pos = end + close.length;
    return true;
  };
}

/** A grounding source parsed from an inline `[Source: file#page]` tag. */
export interface SourceRef {
  /** Raw citation string, e.g. "jpm_3pages.pdf#p2". */
  ref: string;
  source: string;
  page?: number;
}

interface MarkdownEnv {
  refs?: SourceRef[];
}

function parseRef(ref: string): SourceRef {
  const [source, loc] = ref.split("#");
  const digits = loc?.match(/\d+/)?.[0];
  return {
    ref,
    source: source?.trim() || ref,
    page: digits ? Number(digits) : undefined,
  };
}

/**
 * Inline rule for `[Source: file#page]` tags the model writes into prose.
 * Each unique tag is collected into `env.refs` (in order of first appearance)
 * and replaced with a compact numbered chip that maps to the Sources list.
 */
function sourceRefRule(state: StateInline, silent: boolean): boolean {
  const TAG = "[Source:";
  const { src, pos } = state;
  if (!src.startsWith(TAG, pos)) return false;

  const end = src.indexOf("]", pos + TAG.length);
  if (end === -1) return false;

  if (!silent) {
    const ref = src.slice(pos + TAG.length, end).trim();
    const env = state.env as MarkdownEnv;
    const refs = (env.refs ??= []);
    let idx = refs.findIndex((r) => r.ref === ref);
    if (idx === -1) idx = refs.push(parseRef(ref)) - 1;

    const token = state.push("source_ref", "", 0);
    token.content = String(idx + 1);
  }
  state.pos = end + 1;
  return true;
}

let cached: MarkdownIt | null = null;

export function getMarkdown(): MarkdownIt {
  if (cached) return cached;

  const md = new MarkdownIt({ linkify: true, breaks: true });

  // Order matters: match `$$` before any single-`$` handling, and `\[`/`\(`
  // before markdown-it's own backslash-escape rule consumes the backslash.
  md.inline.ruler.before(
    "escape",
    "math_display_dollar",
    mathRule("$$", "$$", true, "math"),
  );
  md.inline.ruler.before(
    "escape",
    "math_display_bracket",
    mathRule("\\[", "\\]", true, "math"),
  );
  md.inline.ruler.before(
    "escape",
    "math_inline_paren",
    mathRule("\\(", "\\)", false, "math"),
  );

  // Claim `[Source: ...]` before the default link rule sees the `[`.
  md.inline.ruler.before("link", "source_ref", sourceRefRule);

  md.renderer.rules.math = (tokens, idx) => {
    const token = tokens[idx];
    return renderMath(token.content, Boolean(token.meta?.displayMode));
  };

  md.renderer.rules.source_ref = (tokens, idx) =>
    `<sup class="cite-ref">${tokens[idx].content}</sup>`;

  cached = md;
  return md;
}

/**
 * Render assistant markdown to HTML and extract any inline source references.
 * Use `refs` to build the Sources list when the backend sends no structured
 * `sources` event.
 */
export function renderMarkdown(content: string): {
  html: string;
  refs: SourceRef[];
} {
  const env: MarkdownEnv = {};
  const html = getMarkdown().render(content, env);
  return { html, refs: env.refs ?? [] };
}
