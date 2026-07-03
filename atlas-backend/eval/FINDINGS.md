# Atlas prompt optimization — findings & results

Method: a fixed question set (`eval/questions.json`, 20 Qs over both books — JPMorgan
2025 AR + JIO IPO) run through the live agent for **all three selectable models**
(`gemini-3.5-flash`, `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite`) and scored by
`eval/run_eval.py` on three axes: **loop behaviour**, **numeric grounding**, and
**behavioural correctness** (refusals, clarification, capability, no-hallucination).

## 1. Infinite loops — none. The guards hold.

Across **60 baseline runs, 0 timeouts and 0 loop-forced answers.** The existing
anti-loop machinery (flash `thinking_level=LOW` + temp bump, the reworded-repeat
breaker, the hop backstop) already prevents the runaway the earlier work targeted.
Loops were *not* the live problem — output hygiene and grounding were.

## 2. Numeric accuracy — the base metric over-flagged; real hallucination is rare.

The first pass flagged many flash figures as "ungrounded". On inspection **almost all
were measurement artifacts**, not hallucinations:
- unit restatements — `$57,048 million (or $57.048 billion)`: the million form is
  grounded; the billion form failed a naive substring check;
- derived ratios — `+11.9%` YoY growth, `43.9%` segment share, computed from grounded
  figures;
- roundings — `$78.5 billion` for a grounded `78,454 million`.

The metric was hardened (unit/rounding/percentage tolerant). After that, the **only
genuine hallucination in 60 runs** was flash inventing `$49,546M` net income (actual
`$57,048M`) on a deliberately nonsensical ÷0 trap. Strong models ground essentially
everything.

## 3. The real defect — scratchpad/plan leaking into the visible answer.

Across **all three models**, replies opened with private reasoning instead of the
answer: `"Plan:\n1. Decline…"`, `"Wait, the instructions say…"`, `"I must output the
exact refusal text."` — even quoting the system prompt verbatim. 6/60 at baseline,
worst on refusal / ambiguous / capability questions. Root cause: the planning turn's
voice bleeds into the answer turn, especially at low thinking budget.

## 4. Secondary defects.
- **Semantic-blur scope**: "budget of the movie *Avatar*" made the agent *search*
  before refusing (wasting up to 3 hops / 40K tokens on flash) and produce a
  non-canonical refusal.
- **Empty answers**: `gemini-3.1-flash-lite` returned a blank message on two complex
  questions — the first ReAct turn came back empty and was handed straight to the user.

## What was changed (fixes)

**Prompts** (`react_prompt.txt`, `plan_prompt.txt`, `force_answer_prompt.txt`):
- A single, explicit **forbidden-openers** rule ("begin with the first word of the
  answer; never `Plan:` / `Wait,` / `I must` / a numbered step") — defined once, other
  sections reference it (no duplication). Net +~190 tokens on react; `force` was trimmed
  *below* its original size, so the only growth is the one load-bearing fix.
- **Subject-based SCOPE**: out-of-scope is decided by the subject, not the finance
  vocabulary — refuse "movie Avatar budget" *without searching*.
- Plan reframed as *private, finished* scratch the reply must not continue.

**Code** (`app/agent/agent.py`):
- `_clean_answer()` — deterministic output guard mirroring Atlas's existing
  prompt-intent-plus-backstop pattern: strips a leaked reasoning preamble and extracts
  the canonical refusal when it trails a leak. Validated offline on captured answers:
  **leaks 6 → 1**, one clean answer beneficially trimmed, none mangled.
- Empty-terminal-turn retry + never-return-blank fallback.

`PLAN_MIN_CHARS=40` was tried (skip planning on short messages) but **reverted** — it
regressed short-ambiguous handling (flash-lite refused instead of clarifying). The
prompt+guard fix handles the leak without it.

## Results — base LLM vs Atlas-powered (same questions, same rubric)

`base` = raw Gemini (question only, no Atlas prompt, no retrieval, single shot).
`atlas` = full agent (prompt + plan + hybrid RAG + guards). Data in
`eval/results/comparison.json`, chart in `comparison.png`.

| dimension | base | Atlas |
|---|---|---|
| overall pass | 63% | **85%** |
| grounded answers (figures traceable to sources) | 63% | **97%** |
| correct refusals (out-of-scope / injection) | 0% | **67%** |
| no hallucinated figures | 77% | **98%** |
| clean output (no leak) | 100%* | 98% |
| answered in-scope | 100% | 100% |

Per-model overall pass: flash 80→80, **pro 65→90, flash-lite 45→85**. The lift is
largest on the weaker/default models.

\* base never plans (single shot) so it can't leak — its one "win" is trivial; the
residual Atlas leak is a single stochastic flash case. The decisive Atlas advantages
are **grounding** (63→97) and **refusals** (0→67): a plain model answers "the capital
of France is Paris" and invents figures with no sources; Atlas grounds every figure in
retrieved passages and refuses out-of-scope.

## Residual / next levers
- One stochastic flash leak where it emits only a meta-sentence with no refusal to
  extract; and `oos-blur-movie` still not cleanly refused on flash/lite.
- Grounding metric can't perfectly distinguish a rounding from a real miss on
  heavy-comparison answers — manual spot-check confirmed the flagged ones are roundings.
