"""Base-model vs Atlas-powered comparison.

Same question set (eval/questions.json), same scoring rubric (run_eval._score),
two systems per model:

  • BASE      — the raw Gemini model: the question alone, no Atlas system prompt,
                no retrieval, single shot. What a plain LLM does.
  • ATLAS     — the full Atlas agent (system prompt + plan + hybrid RAG grounding
                + tool loop + guards). Scores are read from eval/results/<atlas>.json
                (already computed), with the output-hygiene guard applied offline.

Emits eval/results/comparison.json (the graph data) and comparison.png (the image).

    uv run --with matplotlib python eval/compare_base.py            # full
    uv run --with matplotlib python eval/compare_base.py --limit 6  # cheaper
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR.parent))   # backend root, for `app.*`
sys.path.insert(0, str(EVAL_DIR))          # eval/, for `run_eval`

from app.agent.agent import _clean_answer  # noqa: E402
from app.llm.gemini import get_gemini  # noqa: E402
from app.schema.llm_settings import ModelSettings  # noqa: E402

import run_eval as R  # noqa: E402  reuse the exact scoring rubric + helpers

RESULTS = EVAL_DIR / "results"
MODELS = R.MODELS
ATLAS_SOURCE = "optimized"  # which run_eval result file holds the Atlas scores


async def _base_answer(question: str, model: str) -> str:
    """One raw model call: no system prompt, no tools, no retrieval."""
    gem = get_gemini(None)
    parts: list[str] = []
    settings = ModelSettings(model=model, temperature=0.0, max_output_tokens=500)
    async for chunk in gem.generate_content_stream_async(question, settings=settings):
        parts.append(chunk)
    return "".join(parts).strip()


def _score_base(q: dict, model: str, answer: str) -> R.RunResult:
    r = R.RunResult(
        qid=q["id"], book_id=q["book_id"], model=model,
        category=q["category"], expect=q["expect"], question=q["question"],
        max_hops=0,
    )
    r.answer = answer
    r.has_chart = "```chart" in answer
    r.is_refusal = R.REFUSAL_MARKER in answer.lower()
    r.leaked = R._leaked(answer)
    R._score(r, q, passages=[])  # no retrieval -> nothing to ground against
    return r


# ---- comparison dimensions (fractions 0..1), computed over a set of RunResults --

def _dims(rows: list[R.RunResult]) -> dict[str, float]:
    def frac(nums, dens):
        return round(sum(nums) / sum(dens), 3) if sum(dens) else 0.0

    inscope = [r for r in rows if r.expect in
               ("grounded_numeric", "comparison", "thematic")]
    numeric = [r for r in rows if r.expect in ("grounded_numeric", "comparison")]
    refuse = [r for r in rows if r.expect == "refuse"]
    return {
        "overall_pass": frac([r.passed for r in rows], [1] * len(rows)),
        # in-scope questions answered with grounded (source-backed) figures
        "grounded_answers": frac(
            [not r.ungrounded_numbers and bool(r.answer) for r in numeric],
            [1] * len(numeric)),
        # out-of-scope / injection correctly refused
        "correct_refusals": frac([r.is_refusal for r in refuse], [1] * len(refuse)),
        # no invented (ungrounded) figures anywhere
        "no_hallucinated_figures": frac(
            [not r.ungrounded_numbers for r in rows], [1] * len(rows)),
        # clean output: no scratchpad/plan leak in the visible reply
        "clean_output": frac([not r.leaked for r in rows], [1] * len(rows)),
        # in-scope questions actually answered (non-empty, not wrongly refused)
        "answered_in_scope": frac(
            [bool(r.answer) and not r.is_refusal for r in inscope],
            [1] * len(inscope)),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    spec = json.loads((EVAL_DIR / "questions.json").read_text())
    questions = spec["questions"]
    if args.limit:
        questions = questions[: args.limit]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    # --- Atlas scores: read the already-computed run, apply the hygiene guard ---
    atlas_raw = json.loads((RESULTS / f"{ATLAS_SOURCE}.json").read_text())
    atlas_by: dict[tuple[str, str], R.RunResult] = {}
    for d in atlas_raw:
        r = R.RunResult(**{k: v for k, v in d.items() if k in R.RunResult.__annotations__})
        r.answer = _clean_answer(r.answer)          # guard applied
        r.leaked = R._leaked(r.answer)              # recompute leak post-guard
        r.is_refusal = R.REFUSAL_MARKER in r.answer.lower()
        atlas_by[(r.qid, r.model)] = r

    # --- Base scores: one raw call per question x model ---
    print(f"Base runs: {len(questions)} x {len(models)} = "
          f"{len(questions) * len(models)}")
    base_rows: list[R.RunResult] = []
    for model in models:
        for q in questions:
            print(f"  [base/{model}] {q['id']:<20} ", end="", flush=True)
            try:
                ans = await _base_answer(q["question"], model)
            except Exception as e:  # noqa: BLE001
                ans = ""
                print(f"ERR {e}")
            r = _score_base(q, model, ans)
            base_rows.append(r)
            print("refusal" if r.is_refusal else ("empty" if not ans else "answered"))

    # persist base rows so the comparison can be re-scored offline (no re-calls)
    (RESULTS / "base_rows.json").write_text(
        json.dumps([r.__dict__ for r in base_rows], indent=2))

    atlas_rows = [atlas_by[(q["id"], m)] for m in models for q in questions
                  if (q["id"], m) in atlas_by]

    # --- assemble comparison data ---
    data: dict = {"models": models, "per_model": {}, "overall": {}}
    for m in models:
        b = [r for r in base_rows if r.model == m]
        a = [r for r in atlas_rows if r.model == m]
        data["per_model"][m] = {"base": _dims(b), "atlas": _dims(a)}
    data["overall"] = {"base": _dims(base_rows), "atlas": _dims(atlas_rows)}
    (RESULTS / "comparison.json").write_text(json.dumps(data, indent=2))
    print(f"\nWrote {RESULTS / 'comparison.json'}")

    _plot(data, models)


def _plot(data: dict, models: list[str]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    dim_keys = ["overall_pass", "grounded_answers", "correct_refusals",
                "no_hallucinated_figures", "clean_output", "answered_in_scope"]
    dim_lbl = ["Overall\npass", "Grounded\nanswers", "Correct\nrefusals",
               "No halluc.\nfigures", "Clean\noutput", "Answered\nin-scope"]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    base_c, atlas_c = "#c0504d", "#2e7d5b"

    # Panel 1: capability dimensions, overall (avg across models)
    ax = axes[0]
    b = [data["overall"]["base"][k] * 100 for k in dim_keys]
    a = [data["overall"]["atlas"][k] * 100 for k in dim_keys]
    x = np.arange(len(dim_keys)); w = 0.38
    ax.bar(x - w / 2, b, w, label="Base model", color=base_c)
    ax.bar(x + w / 2, a, w, label="Atlas-powered", color=atlas_c)
    for i, (bb, aa) in enumerate(zip(b, a)):
        ax.text(i - w / 2, bb + 1, f"{bb:.0f}", ha="center", va="bottom", fontsize=9)
        ax.text(i + w / 2, aa + 1, f"{aa:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(dim_lbl, fontsize=9)
    ax.set_ylabel("Score (%)"); ax.set_ylim(0, 108)
    ax.set_title("Capability comparison (all models)", fontweight="bold")
    ax.legend(loc="upper center", ncol=2); ax.grid(axis="y", alpha=0.3)

    # Panel 2: overall pass rate per model
    ax = axes[1]
    bm = [data["per_model"][m]["base"]["overall_pass"] * 100 for m in models]
    am = [data["per_model"][m]["atlas"]["overall_pass"] * 100 for m in models]
    x = np.arange(len(models))
    ax.bar(x - w / 2, bm, w, label="Base model", color=base_c)
    ax.bar(x + w / 2, am, w, label="Atlas-powered", color=atlas_c)
    for i, (bb, aa) in enumerate(zip(bm, am)):
        ax.text(i - w / 2, bb + 1, f"{bb:.0f}", ha="center", va="bottom", fontsize=9)
        ax.text(i + w / 2, aa + 1, f"{aa:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("gemini-", "") for m in models], fontsize=9)
    ax.set_ylabel("Overall pass rate (%)"); ax.set_ylim(0, 108)
    ax.set_title("Overall pass rate per model", fontweight="bold")
    ax.legend(loc="upper center", ncol=2); ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Base LLM  vs  Atlas-powered  —  financial-document QA",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = RESULTS / "comparison.png"
    fig.savefig(out, dpi=130)
    print(f"Wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
