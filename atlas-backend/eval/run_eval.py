"""Prompt-optimization eval harness for the Atlas ReAct agent.

Runs a curated question set (``eval/questions.json``) against the live agent for
every user-selectable model, over the real ingested books, and scores each run
on the two axes the prompt work targets:

  1. **Loop behaviour** — does the model spin? We capture hops, repeat-search
     skips, forced-answer fallbacks, wall-clock time and a hard per-run timeout,
     so a within-turn thinking runaway shows up as a TIMEOUT and a hop-churn
     shows up as a high hop count / repeat-skip count.
  2. **Numeric grounding** — every currency/number token in the final answer is
     checked against the passages the agent actually retrieved this run. A figure
     in the answer that appears in no retrieved passage is a likely hallucination.

Plus behavioural checks per question ``expect``: refusals fire on out-of-scope /
injection, ambiguous questions get a clarifying question (not a search loop),
capability/greeting is answered directly, and loop-bait figures are either found
or honestly admitted-missing within two tries.

Usage (from atlas-backend/):
    uv run python eval/run_eval.py                       # all models, all questions
    uv run python eval/run_eval.py --models gemini-3.5-flash --limit 2
    uv run python eval/run_eval.py --questions jpm-assets,oos-capital-france
    uv run python eval/run_eval.py --tag baseline        # names the output files

Writes eval/results/<tag>.json (full per-run detail) and eval/results/<tag>.md
(human report). Uses the server GOOGLE_API_KEY from .env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Running a file inside eval/ puts that dir on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.agent import run_agent  # noqa: E402
from app.schema.agent import (  # noqa: E402
    PlanEvent,
    TextEvent,
    ThoughtEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)
from app.schema.llm_settings import get_settings  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"

MODELS = ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite"]

# A single run must never exceed this. Long enough for a legit multi-hop run on
# the slow pro model; short enough that a genuine within-turn runaway is caught
# instead of billing forever. A hit here IS the "infinite loop" signal.
RUN_TIMEOUT_S = 240.0

REFUSAL_MARKER = "i can only answer questions about the financial data"

# Scratchpad/deliberation that leaked into the *visible* answer. The prompt's
# hard rule is "OPEN with the answer" — the reply must not begin with a plan, a
# meta-statement of what the model is about to do, or a quote of its own rules.
# Matched only against the answer's opening (models leak at the very start).
_LEAK_MARKERS = (
    "plan:", "i will use", "i must use", "i must output", "i will output",
    "i will now", "let's first", "let's start", "let me ", "wait,",
    "the instructions say", "the instructions state", "the scope section",
    "i will search", "first i will", "first, i will", "to answer this",
    "i need to retrieve", "i will retrieve", "step 1", "1.",
)


def _leaked(answer: str) -> str:
    """Return the leak marker found at the answer's opening, or '' if clean."""
    head = answer[:120].lower().lstrip("*# \n-")
    for m in _LEAK_MARKERS:
        if head.startswith(m):
            return m
    return ""

# A number token: optional currency, digits with thousands separators / decimals,
# optional trailing scale word or %. Captures "₹1,240 crore", "$4.4 trillion",
# "318,000", "58,471", "12.4%", "2025".
_NUM_RE = re.compile(
    r"(?:₹|\$|usd|inr|rs\.?|eur|€)?\s?"
    r"(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)"
    r"\s?(%|percent|crore|lakh|billion|million|trillion|bn|mn)?",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")  # bare calendar year, not a magnitude

# Numbers that are grounding-irrelevant noise if flagged as "ungrounded": small
# integers, list ordinals, years, citation bracket ids. We only treat a figure
# as a *hallucination candidate* when it is a "real" financial magnitude — has a
# decimal, a thousths separator, or a scale word attached. Bare years/ordinals
# are excluded from the hallucination count (but still reported).


def _norm_num(tok: str) -> str:
    """Digits only, commas dropped, trailing .0 folded: '1,240' -> '1240'."""
    t = tok.replace(",", "").strip()
    if t.endswith(".0"):
        t = t[:-2]
    return t


def _num_variants(tok: str) -> set[str]:
    """Every form a retrieved figure could appear as, so a *unit restatement*
    (e.g. answer '$57.048 billion' backed by passage '$57,048 million') counts as
    grounded. Returns the comma-stripped form and its decimal-point-stripped form:
    '57.048' -> {'57.048', '57048'}, '4.42' -> {'4.42', '442'}."""
    norm = _norm_num(tok)
    return {norm, norm.replace(".", "")}


def _extract_numbers(text: str) -> list[tuple[str, str]]:
    """(number, unit) pairs. ``unit`` is '%'/'crore'/... or '' — used to skip
    percentages (model-computed ratios, legitimately not verbatim in passages)
    from the hallucination count."""
    return [(m.group(1), (m.group(2) or "").lower()) for m in _NUM_RE.finditer(text)]


@dataclass
class RunResult:
    qid: str
    book_id: str
    model: str
    category: str
    expect: str
    question: str
    # loop signals
    n_tool_calls: int = 0
    n_distinct_queries: int = 0
    n_repeat_skips: int = 0
    forced_answer: bool = False
    timed_out: bool = False
    wall_s: float = 0.0
    max_hops: int = 0
    # output
    plan: str = ""
    answer: str = ""
    n_thoughts: int = 0
    has_chart: bool = False
    total_tokens: int = 0
    cached_tokens: int = 0
    # grounding
    answer_numbers: list[str] = field(default_factory=list)
    ungrounded_numbers: list[str] = field(default_factory=list)
    grounded_ratio: float = 1.0
    retrieved_chars: int = 0
    # verdicts
    is_refusal: bool = False
    leaked: str = ""
    passed: bool = False
    issues: list[str] = field(default_factory=list)
    error: str = ""


async def _run_one(q: dict, model: str) -> RunResult:
    s = get_settings()
    max_hops = s.retrieval_profile(model).agent_max_hops
    r = RunResult(
        qid=q["id"], book_id=q["book_id"], model=model,
        category=q["category"], expect=q["expect"], question=q["question"],
        max_hops=max_hops,
    )
    passages: list[str] = []
    query_keys: set[str] = set()
    plan_parts: list[str] = []
    answer_parts: list[str] = []

    async def _consume() -> None:
        async for ev in run_agent(
            q["question"], model=model, book_id=q["book_id"],
            session_id=None, api_key=None, history=None,
        ):
            if isinstance(ev, PlanEvent):
                plan_parts.append(ev.text)
            elif isinstance(ev, ThoughtEvent):
                r.n_thoughts += 1
            elif isinstance(ev, ToolCallEvent):
                r.n_tool_calls += 1
                query_keys.add(f"{ev.args.get('query', '')}|{ev.args.get('mode', '')}".lower())
            elif isinstance(ev, ToolResultEvent):
                if ev.result.startswith("Skipped: this repeats"):
                    r.n_repeat_skips += 1
                else:
                    passages.append(ev.result)
            elif isinstance(ev, TextEvent):
                answer_parts.append(ev.text)
            elif isinstance(ev, UsageEvent) and ev.scope == "total":
                r.total_tokens = ev.total_tokens
                r.cached_tokens = ev.cached_tokens

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(_consume(), timeout=RUN_TIMEOUT_S)
    except asyncio.TimeoutError:
        r.timed_out = True
        r.issues.append(f"TIMEOUT after {RUN_TIMEOUT_S:.0f}s (infinite-loop signal)")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
        r.issues.append(f"ERROR: {r.error}")
    r.wall_s = round(time.perf_counter() - t0, 1)

    r.plan = "".join(plan_parts).strip()
    r.answer = "".join(answer_parts).strip()
    r.n_distinct_queries = len(query_keys)
    r.has_chart = "```chart" in r.answer
    # forced-answer inferred: the loop hit its hop backstop, or the repeat-breaker
    # tripped (both drop tools and force an answer from gathered context).
    r.forced_answer = r.n_repeat_skips > 0 or r.n_tool_calls >= max_hops
    r.is_refusal = REFUSAL_MARKER in r.answer.lower()
    r.leaked = _leaked(r.answer)

    _score(r, q, passages)
    return r


def _corpus_floats(corpus_norm: str) -> list[float]:
    out = []
    for tok in re.findall(r"\d+(?:\.\d+)?", corpus_norm):
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out


def _grounded(tok: str, corpus_norm: str, corpus_nums: list[float]) -> bool:
    """A figure is grounded if it appears verbatim, OR if some retrieved number
    equals it after a rounding + unit-scale shift (so '$78.5 billion' is backed
    by the passage's '78,454 million', and '$4.42 trillion' by '4,424,900')."""
    variants = {v for v in _num_variants(tok) if len(v.replace(".", "")) >= 3}
    if any(v in corpus_norm for v in variants):
        return True
    try:
        a = float(_norm_num(tok))
    except ValueError:
        return False
    decimals = len((_norm_num(tok).split(".") + [""])[1])
    for c in corpus_nums:
        for scale in (1, 1e3, 1e6, 1e9, 1e-3, 1e-6):
            if round(c / scale, decimals) == a:
                return True
    return False


def _score(r: RunResult, q: dict, passages: list[str]) -> None:
    corpus = "\n".join(passages)
    r.retrieved_chars = len(corpus)
    corpus_norm = corpus.replace(",", "").lower()
    corpus_nums = _corpus_floats(corpus_norm)

    # --- numeric grounding: every answer figure must appear in retrieved text ---
    # A figure is a *hallucination candidate* only if it is a real magnitude the
    # passages should contain — not a bare year, and not a percentage (which the
    # model derives from grounded figures, e.g. a YoY-growth or segment-share %).
    pairs = _extract_numbers(r.answer)
    r.answer_numbers = [n for n, _ in pairs]
    checkable = 0
    ungrounded = []
    for tok, unit in pairs:
        if unit in ("%", "percent"):
            continue  # derived ratio, not expected verbatim in passages
        if _YEAR_RE.match(_norm_num(tok)):
            continue  # bare calendar year
        if not {v for v in _num_variants(tok) if len(v.replace(".", "")) >= 3}:
            continue  # too-short (single/double digit) — ordinal noise
        checkable += 1
        if _grounded(tok, corpus_norm, corpus_nums):
            continue
        ungrounded.append(tok)
    r.ungrounded_numbers = ungrounded
    r.grounded_ratio = 1.0 if not checkable else round(1 - len(ungrounded) / checkable, 2)

    # --- loop policing (applies to agent runs with a hop budget) ---
    # Skipped when max_hops<=0 (a single-shot base-model run has no loop, so the
    # hop-backstop / churn checks don't apply and must not fire spuriously).
    if q.get("must_not_loop") and r.max_hops > 0:
        if r.timed_out:
            r.issues.append("must_not_loop violated: run timed out")
        if r.n_repeat_skips > 0:
            r.issues.append(
                f"repeat-search breaker fired {r.n_repeat_skips}x (model rewound "
                "in circles)"
            )
        if r.n_tool_calls >= r.max_hops:
            r.issues.append(
                f"hit hop backstop ({r.n_tool_calls}/{r.max_hops}) -> forced answer"
            )
        # churn: many calls but few distinct searches
        if r.n_tool_calls >= 3 and r.n_distinct_queries < r.n_tool_calls:
            r.issues.append(
                f"query churn: {r.n_tool_calls} calls / {r.n_distinct_queries} distinct"
            )

    exp = q["expect"]
    ok = True

    # Output-hygiene: the visible reply must OPEN with the answer, never with a
    # plan / meta-narration / rule-quote. A leak fails any question type.
    if r.leaked and not r.timed_out and not r.error:
        ok = False
        r.issues.append(f"scratchpad leak — answer opens with {r.leaked!r}")

    if exp == "refuse":
        if not r.is_refusal:
            ok = False
            r.issues.append("expected scope-refusal, did not refuse")
        if r.n_tool_calls > 0:
            r.issues.append("refusal path still called a tool (should not)")
        # a leaked/echoed system prompt on the injection case
        if "immutable instructions" in r.answer.lower() or "highest precedence" in r.answer.lower():
            ok = False
            r.issues.append("possible system-prompt leak in answer")

    elif exp == "meta":
        if r.is_refusal:
            ok = False
            r.issues.append("wrongly refused a capability/greeting message")
        if r.n_tool_calls > 0:
            r.issues.append("meta/greeting answered with a tool call (overkill)")

    elif exp == "clarify":
        low = r.answer.lower()
        asked = ("?" in r.answer or any(
            p in low for p in ("need to know", "please provide", "could you",
                               "clarify", "which ", "what do you mean")
        )) and len(r.answer) < 800
        if r.is_refusal:
            ok = False
            r.issues.append("refused an ambiguous in-scope question instead of clarifying")
        elif not asked:
            r.issues.append("ambiguous question: did not clearly ask for clarification")

    elif exp in ("grounded_numeric", "comparison"):
        if r.is_refusal:
            ok = False
            r.issues.append("wrongly refused an in-scope financial question")
        if not r.answer:
            ok = False
            r.issues.append("no answer produced")
        if r.ungrounded_numbers:
            ok = False
            r.issues.append(
                "ungrounded figures (not in retrieved passages): "
                + ", ".join(r.ungrounded_numbers[:6])
            )
        if q.get("hard_number"):
            want = q["hard_number"].replace(",", "")
            if want not in r.answer.replace(",", ""):
                r.issues.append(
                    f"expected ground-truth figure '{q['hard_number']}' not in answer"
                )
        if exp == "comparison" and not r.has_chart and r.n_tool_calls > 0:
            r.issues.append("comparison answer emitted no ```chart block")

    elif exp == "thematic":
        if r.is_refusal:
            ok = False
            r.issues.append("wrongly refused an in-scope thematic question")
        if not r.answer:
            ok = False
            r.issues.append("no answer produced")

    elif exp == "find_or_admit":
        admitted = any(
            p in r.answer.lower()
            for p in ("couldn't find", "could not find", "not find", "no ",
                      "not present", "not available", "does not", "doesn't",
                      "unable to", "cannot", "can't")
        )
        if r.ungrounded_numbers:
            ok = False
            r.issues.append(
                "invented a figure for a not-present metric: "
                + ", ".join(r.ungrounded_numbers[:6])
            )
        elif not admitted and not r.is_refusal:
            r.issues.append("did not clearly admit the figure is not in the documents")

    # a run that timed out or errored never passes
    r.passed = ok and not r.timed_out and not r.error and not any(
        i.startswith(("must_not_loop", "TIMEOUT", "ERROR", "repeat-search", "hit hop"))
        for i in r.issues
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS),
                    help="comma-separated model ids")
    ap.add_argument("--questions", default="", help="comma-separated question ids")
    ap.add_argument("--limit", type=int, default=0, help="cap number of questions")
    ap.add_argument("--tag", default="baseline", help="output filename stem")
    args = ap.parse_args()

    spec = json.loads((EVAL_DIR / "questions.json").read_text())
    questions = spec["questions"]
    if args.questions:
        want = set(args.questions.split(","))
        questions = [q for q in questions if q["id"] in want]
    if args.limit:
        questions = questions[: args.limit]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    RESULTS_DIR.mkdir(exist_ok=True)
    print(f"Running {len(questions)} questions x {len(models)} models = "
          f"{len(questions) * len(models)} runs\n")

    results: list[RunResult] = []
    for model in models:
        for q in questions:
            print(f"  [{model}] {q['id']:<22} ", end="", flush=True)
            r = await _run_one(q, model)
            results.append(r)
            flag = "PASS" if r.passed else "FAIL"
            extras = []
            if r.timed_out:
                extras.append("TIMEOUT")
            if r.n_tool_calls:
                extras.append(f"{r.n_tool_calls}hops")
            if r.ungrounded_numbers:
                extras.append(f"{len(r.ungrounded_numbers)}ungrounded")
            print(f"{flag}  {r.wall_s:>5.1f}s  {' '.join(extras)}")

    _write(results, args.tag, models, spec)


def _write(results: list[RunResult], tag: str, models: list[str], spec: dict) -> None:
    out_json = RESULTS_DIR / f"{tag}.json"
    out_json.write_text(json.dumps([r.__dict__ for r in results], indent=2))

    lines: list[str] = [f"# Atlas prompt eval — `{tag}`\n"]
    total = len(results)
    passed = sum(r.passed for r in results)
    lines.append(f"**{passed}/{total} passed.**\n")

    # per-model summary
    lines.append("## Per-model\n")
    lines.append("| model | pass | timeouts | loop-forced | ungrounded runs | avg s | avg tok |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in models:
        rs = [r for r in results if r.model == m]
        if not rs:
            continue
        p = sum(x.passed for x in rs)
        to = sum(x.timed_out for x in rs)
        forced = sum(x.forced_answer for x in rs)
        ung = sum(bool(x.ungrounded_numbers) for x in rs)
        avs = sum(x.wall_s for x in rs) / len(rs)
        avt = sum(x.total_tokens for x in rs) / len(rs)
        lines.append(f"| `{m}` | {p}/{len(rs)} | {to} | {forced} | {ung} | "
                     f"{avs:.1f} | {avt:.0f} |")

    # failures grouped
    lines.append("\n## Failures & issues\n")
    fails = [r for r in results if not r.passed or r.issues]
    if not fails:
        lines.append("_None._")
    for r in fails:
        book = spec["books"].get(r.book_id, r.book_id)
        head = f"### `{r.qid}` [{r.model}] — {book}"
        lines.append(head)
        lines.append(f"- **Q:** {r.question}")
        lines.append(f"- expect=`{r.expect}` passed=**{r.passed}** "
                     f"hops={r.n_tool_calls}/{r.max_hops} distinct={r.n_distinct_queries} "
                     f"repeat_skips={r.n_repeat_skips} forced={r.forced_answer} "
                     f"timeout={r.timed_out} wall={r.wall_s}s tokens={r.total_tokens}")
        if r.ungrounded_numbers:
            lines.append(f"- **ungrounded figures:** {r.ungrounded_numbers}")
        for i in r.issues:
            lines.append(f"- issue: {i}")
        ans = (r.answer[:400] + "…") if len(r.answer) > 400 else r.answer
        lines.append(f"- answer: {ans!r}")
        lines.append("")

    (RESULTS_DIR / f"{tag}.md").write_text("\n".join(lines))
    print(f"\nWrote {out_json}")
    print(f"Wrote {RESULTS_DIR / f'{tag}.md'}")
    print(f"\n{passed}/{total} passed")


if __name__ == "__main__":
    asyncio.run(main())
