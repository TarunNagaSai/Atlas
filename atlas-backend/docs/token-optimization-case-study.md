# Case Study: Cutting Atlas's Per-Query Token Cost by ~70%

**Date:** 2026-07-02
**Scope:** `atlas-backend` — the streaming ReAct agent (`app/agent/agent.py`) and its supporting layers
**Result:** A representative query dropped from **~34K tokens → ~10K tokens** with no loss of
answer quality (identical grounded figures, same chart, tighter prose).

---

## 1. The problem

A single financial question —

> *"Compare total revenue and net income for the last three fiscal years and show it as a chart."*

— consumed **34,000 tokens** end to end. For an answer that surfaces ~6 numbers and one chart,
that is wildly disproportionate. Token cost is real money on a per-visitor (BYO-key) product and
also drives latency, so the spend needed to come down without degrading the grounded, cited
answers Atlas is built to give.

### Why it was so expensive

Atlas answers through a **ReAct loop**: plan → (retrieve → reason)* → answer. The structural cost
driver in any ReAct agent is that **the entire conversation is re-sent to the model on every
hop**. So costs compound rather than add. The specific culprits:

| Driver | Detail | Cost shape |
|---|---|---|
| System prompt re-sent every hop | `react_prompt.txt` was ~220 lines / ~2.3K tokens, passed as `system` on *every* turn | ~2.3K × N hops |
| Fat retrieved passages | Parent-document retrieval returned whole pages (`parent_chunk_tokens` ≈ 1,200 tokens ≈ 4,800 chars), `final_top_k = 6` of them, and they **persisted in context across all later hops** | ~7K per retrieve, re-sent each hop |
| Wide retrieval | `fused_top_k = 12` candidates reranked to 6 | more + larger passages |
| Separate planning turn | An extra full-model Gemini call before the loop, whose plan output then rode along in every subsequent hop | +1 call + ongoing overhead |
| High hop ceiling | `agent_max_hops = 12` allowed long, repetitive search runs | unbounded accumulation |

The two superlinear costs — *system prompt × hops* and *fat passages × hops* — are why a 6-number
answer ballooned to 34K.

---

## 2. What we changed

Six changes, ordered here by impact. All values are env-overridable (`app/schema/llm_settings.py`)
so every optimization is tunable and reversible without a code change.

### 2.1 Trimmed the system prompt (biggest fixed-cost cut)
`react_prompt.txt`: ~2.3K → ~1.6K tokens. The prompt restated the "don't narrate your reasoning"
rule four separate ways; that was collapsed into one tight section. **Every functional contract
was preserved verbatim** — the exact refusal string, the exact greeting string, both tool
contracts, the grounding/citation rules, and the full `chart` JSON shape. Because the prompt is
re-sent on every hop, ~700 tokens saved is ~700 × N tokens saved per query.

> **Constraint honored:** we deliberately did *not* trim below ~1.3K tokens, because Gemini's
> implicit cache has a minimum-cacheable prefix size. Trimming too far would have dropped the
> prompt below that floor and *killed caching* — a real tension between two optimizations.

### 2.2 Capped retrieved passage length (biggest per-retrieve cut)
`app/tools/tools.py` now bounds each passage to `PASSAGE_MAX_CHARS` (default **1400**). It keeps
the full page while it fits, and past the cap **falls back to the matched child span** (the
actually-relevant sentences that scored the hit) rather than an arbitrary slice of the page head,
with a hard truncate as a last-resort guard. This attacks the single largest line item.

### 2.3 Narrowed retrieval breadth
`FINAL_TOP_K` **6 → 4**, `FUSED_TOP_K` **12 → 8**. Fewer candidates reranked, fewer passages
returned — each of which was being re-sent every hop.

### 2.4 Made the planning turn cheaper and skippable
The planning turn now runs on a lighter model (`PLAN_MODEL`, default `gemini-3.1-flash-lite`) —
a 3–5 sentence plan does not need the full generation model. It can also be skipped entirely for
trivial short messages via `PLAN_MIN_CHARS` (greetings / one-line lookups the ReAct prompt handles
on its own). Default keeps planning on, just cheaper.

### 2.5 Added implicit-caching observability
Gemini automatically caches a stable request prefix (system prompt + unchanged head of `contents`)
and bills the reused slice at a discount. We surfaced `cached_tokens` on `UsageEvent` (from
`usage_metadata.cached_content_token_count`) and into Langfuse (`cache_read`) so cache hits are
**visible and debuggable** — a zero there means the prefix changed or fell below the size floor.

> **Why implicit, not explicit caching:** explicit `CachedContent` was rejected because (a) Atlas
> is BYO-key, so an explicit cache would bill *hourly against the visitor's own project*; (b) tools
> vary per turn (normal turns advertise both tools, forced turns none, the plan turn uses a
> different system prompt) and an explicit cache can't hold varying tools/system; (c) the ~2K
> system prompt sits near the explicit-cache minimum-token floor. Implicit caching has no storage
> cost, needs no lifecycle management, and fits bursty chat traffic.

### 2.6 Evict superseded tool results from context
Once a newer retrieve result is in hand, older passage dumps are collapsed to a short stub
(`app/agent/agent.py: _compact_old_tool_results`), keeping the most recent
`KEEP_RECENT_TOOL_RESULTS` (default **2**) intact. Only the `function_response` payload is
rewritten; the paired model `function_call` part is left untouched so the Gemini 3.x
`thought_signature` still survives. The operation is idempotent, so the prefix re-stabilizes.

---

## 3. The result

| | Before | After |
|---|---|---|
| Total tokens (same query) | ~34,000 | ~10,000 |
| Answer figures | correct, grounded | **identical** |
| Chart | rendered | **identical** |
| Prose | included an off-topic "gross revenue" tangent | tighter, on-question |

The ~70% reduction came mostly from the prompt trim (§2.1) and the passage cap (§2.2); the lighter
plan model (§2.4) removed fixed overhead; eviction (§2.6) only materially helps on longer
multi-search runs; caching (§2.5) discounts the repeated prefix on hop 2+.

An unplanned bonus: the leaner prompt and tighter context made the answer **more focused** — it
stopped volunteering the unrequested gross-revenue breakdown it produced in the 34K run.

---

## 4. Advantages

- **~70% lower cost per query** — direct savings on a per-visitor billing model, compounding at scale.
- **Lower latency** — fewer tokens in and out means faster time-to-answer.
- **No quality regression** — same grounded, cited figures and chart; arguably *better* prose focus.
- **Fully tunable & reversible** — every lever is an env var; nothing is hardcoded at a call site.
- **Observable** — `cached_tokens` / Langfuse `cache_read` make the caching win measurable, not assumed.
- **Robust defaults** — conservative settings (`KEEP_RECENT_TOOL_RESULTS = 2`) avoid the failure modes below.

## 5. Disadvantages & trade-offs

Every change bought savings by giving something up. Being honest about the edges:

- **Passage cap can drop supporting context (§2.2).** Falling back to the child span past the cap
  keeps the *matched* text, but a question whose answer is spread across a full page could now miss
  the surrounding context. Mitigation: `PASSAGE_MAX_CHARS` is tunable; raise it if grounding suffers.
- **Narrower retrieval can lower recall (§2.3).** `FINAL_TOP_K = 4` means fewer chances to catch a
  figure that ranked 5th–6th. For broad "compare everything" questions this is the riskiest knob.
- **Eviction can trigger re-searches (§2.6).** This is the sharpest edge. Evict something the model
  still needs and it re-searches → burns a hop → risks hitting `agent_max_hops` and the
  *force-answer* path, which answers from **incomplete** evidence. The conservative `keep_recent = 2`
  default is what keeps this safe; lowering it trades more savings for this risk.
- **Eviction fights caching (§2.5 vs §2.6).** Rewriting older results busts the implicit cache from
  that point forward. Net-positive (full removal beats a ~25%-discounted re-send), but it means you
  won't see cache hits covering the evicted region.
- **Implicit caching is not guaranteed.** It only engages above a model-tier minimum prefix size and
  requires a byte-identical prefix. If `cached_tokens` reads 0, the discount simply isn't happening —
  and there's no explicit knob to force it (that was the deliberate trade for avoiding hourly storage cost).
- **Skipping the planning turn changes behavior (§2.4).** For genuinely complex multi-part questions,
  the upfront plan improves the approach. `PLAN_MIN_CHARS` defaults to *off* precisely because the
  skip heuristic (message length) is crude; enable it knowingly.
- **Prompt-trim floor.** The prompt can't be shrunk indefinitely — below the cache floor it would
  *cost* tokens by disabling caching. There's a hard lower bound on this particular lever.

---

## 6. Configuration reference

| Env var | Default | Purpose |
|---|---|---|
| `PASSAGE_MAX_CHARS` | `1400` | Per-passage char cap; `0` = uncapped (old behavior) |
| `FINAL_TOP_K` | `4` | Passages the reranker keeps and the agent sees |
| `FUSED_TOP_K` | `8` | Candidates kept after RRF fusion, handed to the reranker |
| `PLAN_MODEL` | `gemini-3.1-flash-lite` | Model for the planning turn |
| `PLAN_MIN_CHARS` | `0` | Skip planning below this message length (0 = never skip) |
| `KEEP_RECENT_TOOL_RESULTS` | `2` | Recent tool results kept intact before eviction |
| `AGENT_MAX_HOPS` | `12` | Safety backstop on the ReAct loop |

## 7. How to verify

1. Re-run the benchmark query and read the token counter in the UI (should land near ~10K).
2. In Langfuse, inspect the turn generations: `cache_read` should be **non-zero on hop 2+**. If it's
   zero, the model tier isn't meeting the implicit-cache minimum prefix size.
3. Watch for re-searches in the trace — a sign `KEEP_RECENT_TOOL_RESULTS` is too low for your workload.

## 8. What's next (not yet done)

Build a **Langfuse eval dataset** from real traces (~30–50 queries with expected answers/behaviors).
That converts any further prompt trimming from "looks safe" into "measured safe," and is the
prerequisite for an automated prompt-optimization loop (e.g. PhaseEvo-style evolutionary search
with token count folded into the fitness function).
