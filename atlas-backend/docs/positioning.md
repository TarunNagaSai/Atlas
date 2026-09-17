# Atlas: What It Is, What It Proves, What It Sells

**Date:** 2026-07-13
**Status:** Direction locked.
**Replaces:** `product-roadmap.md` and `product-pivot-plan.md` (both written and deleted
2026-07-13 — they aimed Atlas at a product/market it shouldn't chase; see §2).

---

## 1. The frame

**Atlas is not a product. Atlas is a reference implementation.**

> *"Atlas is a production-grade agentic system I built end-to-end — ingestion, retrieval,
> the agent loop, the streaming UI, the observability. I use it as my reference
> implementation: it's where I prove that an AI system is grounded, cheap to run, fully
> traceable, and honest about what it doesn't know. When I build for a client, that's the
> standard I build to."*

We are not selling Atlas. We are selling **the standard Atlas was built to**.

The business is **AI systems consulting** — build the client's system, whatever their domain.
Atlas is the artifact that makes a stranger believe we can do it.

---

## 2. Why not a product (the short version, so we don't relitigate it)

Three findings, each independently fatal to the product path *for a solo founder with no
distribution*:

**Document search doesn't convert.** Microsoft put Copilot directly on customers' own
SharePoint/Word/Excel — perfect distribution, trusted vendor, zero integration. **~15M of
450M M365 subscribers bought it (3.3%). ~6% of pilots scale.** Companies with thousands of
documents, offered AI over them, overwhelmingly said no. "They have lots of documents" is a
false buying signal: the value is *diffuse*, so no one owns the budget line. The one winner
(Glean, ~$300M ARR) wins on **connector breadth** — the exact axis a solo founder can never
compete on.

**Connectors are a treadmill, not a moat.** n8n, Zapier Agents, Make, Relevance, Lindy all
connect agents to business systems; HubSpot ships Breeze, Salesforce ships Agentforce.
Calling an API is not hard and commands no premium. Every connector is auth + rate limits +
schema drift + maintenance, forever.

**We don't know a domain, and we have no distribution.** Domain knowledge is learnable;
*access* is not. Picking a vertical now is a coin flip made from a spreadsheet, not from a
client. The right move is to get paid by real clients first, and let the product — if there
is one — emerge from what we rebuild every single time. See §8.

**Therefore:** stop hunting for the niche. Sell capability, prove it with Atlas, let the
niche find us.

---

## 3. The ROI we actually sell

### 3.1 Clients never buy AI

They buy exactly four things. Every proposal must end in arithmetic in one of these
currencies, using **their** numbers:

| Currency | The question it answers |
|---|---|
| **Time back** | How many hours/week does this take today? |
| **Money in** | Deals won, cycles shortened, capacity freed for billable work |
| **Money not lost** | Errors, rework, fines, churn, missed deadlines |
| **Better decisions, faster** | What are they deciding blind today? |

**The arithmetic template:**

> *"Two people spend 10 hours a week on this. At a $50/hr loaded cost that's ~$52k/year.
> A $25k build that removes 70% of it pays back in about eight months."*

Do this math out loud, in every conversation, with their numbers. Most consultants never do
it, which is why they lose to the ones who do.

### 3.2 But that's table stakes. **This** is the differentiator:

**Most enterprise AI projects die in the pilot.** Microsoft's own Copilot scaled past pilot
in roughly **6% of cases**. They don't die because the model was bad. They die because
**nobody could tell whether the thing was working**, so nobody could justify the next cheque.

The pitch:

> *"Most AI pilots die because nobody can prove they work. I build the evaluation harness on
> day one — so at day 30 you have a number, not a demo. On my own system I took grounding
> from 63% to 97% and cut cost per query by 70%, and I can show you exactly how I measured
> both. What I'm selling isn't an agent. It's an agent you can trust, and a number you can
> take to your board."*

**Why this solves the whole problem: evaluation discipline is domain-agnostic.** We don't
need to know furniture retail, or finance, or construction. We need to know how to *prove a
system works* — and that transfers to every client in every domain. It is the one
differentiator that doesn't require picking a niche.

### 3.3 The four things a buyer is really checking

He is asking one question: *"will this person's thing work when it's my money?"* He decides
on four signals — and Atlas evidences all four:

1. **Can turn a vague business problem into a working system** → Atlas, end to end.
2. **Knows when *not* to use something** → the rarest signal. Say out loud when RAG is the
   wrong tool (see §3.4). Nothing builds trust faster.
3. **Can prove it works with numbers, not vibes** → `eval/`, 63%→97% grounded, 0%→67% refusal.
4. **Can ship the whole thing** → ingestion, backend, agent, Next.js UI, Langfuse/Logfire.

**None of these is "it has a lot of tools."** A system with seven tools says *"this person
likes features."* A system with three tools, a hard problem solved, and numbers proving it
says *"this person ships things that survive contact with reality."* Depth + measurement,
never breadth.

### 3.4 The qualifying test (say it to the client — it sells)

Agentic RAG costs ~$0.02–0.10/query vs ~$0.001 naive: **20–100× more**, plus 5–30s latency.
It's only worth it with **yes to all three**:

- A human spends **>20 minutes** hunting across sources to answer this.
- It happens **weekly or more**.
- A **wrong answer costs real money**.

If it's a 2-minute lookup, an agent is a 100× more expensive way to be slower. Telling a
prospect *"you don't need an agent for this"* is the strongest sales move available, and it
disqualifies the engagements that would have failed anyway.

---

## 4. The engagement shape

1. **Paid discovery** — 1–2 weeks, fixed fee (~$2–4k). Output: the problem written down, the
   ROI arithmetic, an architecture, and **a baseline eval** (how well does a naive approach
   do today?). Never free. A free discovery makes us the junior party and it doesn't convert.
2. **Build** — fixed fee, 6–10 weeks, $18–40k, scoped to *one* job that passes §3.4.
3. **Retainer** — $1.5–4k/mo: hosting, monitoring, the eval loop, iteration.

Rate floor: $60–90/hr. Price the engagement, not the hours, but back-solve so we never quote
under the floor.

---

## 5. What to build in Atlas

Not more tools. **More proof**, plus the *shape* of generality.

### 5.1 Proof surfaces (highest value, mostly already-done work that no buyer can see)

- **A public quality dashboard.** Grounding rate, refusal rate, cost per query, and the
  methodology — visible on the live demo. This is the single highest-leverage thing to build.
  It currently exists only as `eval/run_eval.py` output, where no buyer will ever look.
- **"Show your work" as a headline feature, not a UI nicety.** The thinking panel (plan →
  thoughts → tool call/result) *is* the answer to "can I trust this." Frame it that way.
- **Two written case studies.** `docs/token-optimization-case-study.md` already is one —
  publish it. The eval story (found the scratchpad-leak defect, 63%→97%) is the second.
  Medium is an existing channel; use it.

### 5.2 The three tool archetypes

Every client problem reduces to a combination of three things. Build **one of each** — not
seven of one:

| Archetype | Status | What it proves |
|---|---|---|
| **Read unstructured** — `retrieve` (hybrid + rerank + citations) | ✅ Done | Grounded answers over documents |
| **Query structured** — `query_records` (text-to-SQL over Postgres, row-level provenance) + `calculate` (deterministic; **the LLM must never do arithmetic**) | ❌ Build | Agents over real business data |
| **Take an action** — one write tool behind **dry-run → human approval → idempotency key → audit log** | ❌ Build | Agents that *do* things, safely |

That is the generality we want, delivered in the form that actually persuades: *"any problem
you have is some mix of these three, and here's a system where all three work, with proof."*

**Prerequisite:** `app/tools/dispatch.py` is a hardcoded `if name == "retrieve" / elif
"graph_search"`. Replace it with the registry already specified in
`multi-agent-architecture-plan.md` Phase 2.5. Half a week, unblocks everything else.

### 5.3 Cut / park

- **GraphRAG.** Half-finished, unproven with users, impresses engineers and nobody else.
  Leave it wired, don't extend it. (Consistent with the existing `/learn`-first constraint.)
- **The "financial RAG" positioning.** Same engine, wrong story. Reframe as domain-agnostic.
- **BYO-key.** Already planned for removal — `backend-managed-keys-plan.md` stands.
- **Multi-provider abstraction.** Still no.
- **Multi-tenancy, SSO, RLS policies, SOC 2, billing.** All of this was in the deleted
  roadmap as P0. It is **not** P0 for a reference implementation — it's P0 for a *product*,
  and we're not building one. Revisit only when a client's deployment demands it. (When that
  day comes: every table needs `org_id`, `list_books()` currently has no tenant filter, and
  `app/history/store.py` is explicitly global — those are the landmines.)

---

## 6. Phasing

| # | Work | Est. | Why |
|---|---|---|---|
| 0 | Backend-managed keys (existing plan) | 0.5 wk | Already scoped. |
| 1 | Tool registry (kill the `if/elif` in `dispatch.py`) | 0.5 wk | Unblocks 2 and 3. |
| 2 | `query_records` + `calculate` — structured archetype, with row-level provenance | 2 wks | The missing half of every real client problem. |
| 3 | One write tool behind an approval gate | 1 wk | Proves "agents that act, safely." |
| 4 | **Quality dashboard** (grounding / refusal / cost, live) | 1 wk | The proof, made visible. Highest sales leverage in the list. |
| 5 | Publish the two case studies | 0.5 wk | Distribution. |
| 6 | A single joined demo query touching documents **and** records, cited to both | 0.5 wk | The one demo that wins meetings. |

**≈6 weeks.** After that, stop building Atlas and go sell. Further engine work has sharply
diminishing returns against zero clients.

---

## 7. How this fails

- **Building breadth instead of depth.** Seven tools, no numbers. This is the default failure
  and it's seductive because it feels like progress. Guard: every addition must make Atlas
  more *provable*, not more *featured*.
- **"I can build anything" as positioning.** It's the generalist trap and it wins nothing.
  The pitch is never "I'm capable" — it's *"most AI pilots die unproven; mine don't, and
  here's the number."*
- **Polishing Atlas forever instead of selling.** Six weeks. Then stop.
- **Taking an engagement that fails §3.4.** It will fail, and a failed engagement costs more
  than the money it earned.

---

## 8. Where the product comes from (later)

This is a **services business** for now — a consultancy with a flagship proof. It's the right
first move given no distribution and no domain, and it pays while both get built. But be
honest: **it scales with hours, not software.**

The product emerges from **3–4 engagements**, when we notice what gets rebuilt *every single
time*. That repeatable core cannot be designed in advance — attempt it and we'll build a
worse n8n. Get paid to discover it.

Channel: Upwork/freelance is the working channel — clients there are actively describing
these problems. **Distribution is the binding constraint, not product quality and not domain
knowledge.** Use the channel that exists.
