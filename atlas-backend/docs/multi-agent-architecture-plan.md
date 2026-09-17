# Plan: Multi-Agent Orchestration for Atlas (Manual, No Framework)

**Date:** 2026-07-11
**Scope:** `atlas-backend` — extending the existing streaming ReAct agent
(`app/agent/agent.py`) into a hierarchical multi-agent system, built by hand.
**Status:** Draft for review — no code changes yet.

---

## 1. Why this approach

Atlas is being built as a **commercial product sold to clients**, not a portfolio
project. That changes the calculus on how to scale it:

- **Control over behavior.** Client work means per-client customization (different
  tool sets, guardrails, system prompts). Owning the orchestration loop makes that
  a config change; wrapping a framework (LangGraph, Google ADK, CrewAI) means
  fighting its abstractions every time a client wants something non-standard.
- **No framework churn risk.** These frameworks move fast and break APIs. A
  paying client's deployment shouldn't break on someone else's release schedule.
- **Smaller, auditable dependency surface.** Atlas handles financial documents —
  fewer third-party layers between client data and the code is a real selling
  point and an easier security review.
- **The hard part is already built.** Streaming SSE, `CancellationRegistry`,
  retry/tenacity wrapping, Langfuse tracing, native Gemini function calling —
  that's what frameworks exist to give you for free, and it already exists and
  is understood line-by-line in this repo. A framework migration would be net
  negative progress.

The tradeoff we're accepting: building multi-agent state/handoff/tracing
ourselves takes more engineering time than adopting a mature framework's
primitives. We mitigate that by shipping **one sub-agent at a time**, each
independently useful, instead of designing the whole system upfront.

**Chosen pattern: hierarchical agent-as-tool.** An orchestrator runs the
existing plan → ReAct loop, but some of its "tools" are themselves full agent
runs (a nested `run_agent` call) scoped to a narrower system prompt and tool
set. This nests cleanly inside the current architecture — a new tool is
registered once (Phase 2.5) rather than requiring a new execution model.

---

## 2. Current architecture (what we're extending, not replacing)

| Piece | File | Role |
|---|---|---|
| Agent loop | `app/agent/agent.py` — `run_agent()` | plan turn → ReAct loop (retrieve/graph_search) → forced-answer fallback on last hop |
| Event schema | `app/schema/agent.py` | `PlanEvent`, `ThoughtEvent`, `TextEvent`, `ToolCallEvent`, `ToolResultEvent`, `UsageEvent` — discriminated union streamed as SSE |
| Tool dispatch | `app/tools/dispatch.py` — `run_tool()` / `execute_tool_call()` | validates args, runs `retrieve`/`graph_search` (currently via an `if name == ...` chain — replaced by a registry in Phase 2.5), builds the two Gemini turns (function-call echo + function-response) |
| Tool definitions | `app/tools/retrieve.py`, `app/tools/graph_search.py` | one module per tool, each exports its `Tool` schema + implementation |
| Cancellation | `app/agent/cancellation.py` — `CancellationRegistry` | in-process `session_id → cancelled` set, polled at two gates in the loop |
| Observability | `app/observability/langfuse.py` + spans inline in `agent.py` | one `agent.run` span per call, one `agent.turn-N` generation per hop, tool spans nest via `@observe` |
| Route | `app/routes/chat.py` — `stream_chat()` | owns the trace id, SSE framing, persistence, error → coded-message mapping |

Key constraints this plan must respect:

- `run_agent` is an `AsyncIterator[AgentEvent]` — any new agent must speak the
  same event contract so the route layer doesn't change.
- `CancellationRegistry` is single-process, keyed by `session_id` — a nested
  agent call must reuse the *same* `session_id`, not invent its own.
- Langfuse spans nest by Python context manager scope — a nested `run_agent`
  call naturally nests its spans *if* it's invoked inside the parent's `with`
  block, so no new plumbing is needed there, only naming.
- `execute_tool_call` builds the `(model function-call echo, user
  function-response)` turn pair — a sub-agent tool must return a single
  string result through this same contract like any other tool.

---

## 3. Target shape

```
User message
   │
   ▼
Orchestrator run_agent()  (existing loop, existing prompt style)
   │  plan turn (unchanged)
   │  ReAct loop, tools = [retrieve, graph_search, ask_<specialist>, ...]
   │
   ├── tool_call: retrieve / graph_search  → unchanged, dispatch.py
   │
   └── tool_call: ask_<specialist>(query)
          │
          ▼
       nested run_agent(query, session_id=<same>, tools=<scoped subset>,
                         system=<specialist prompt>)
          │  runs its own plan → ReAct loop → forced-answer fallback
          │  emits AgentEvents tagged agent_id="<specialist>"
          ▼
       collapsed to one string result, returned like any tool result
```

The orchestrator doesn't know or care that a "tool" is actually another full
agent run — from its point of view it called a function and got a string
back. This is what keeps the change additive rather than a rewrite.

---

## 4. Phased plan

### Phase 0 — Decisions to lock in before writing code

These are cheap to decide now and expensive to change after Phase 2+ is built.
Flagged questions are called out in §6.

- Which sub-agent ships first as the proof of concept (recommend:
  `graph_search`-only "graph specialist" — narrowest scope, already has a
  fallback-gracefully story if no graph exists for the book).
  - Update: this and other tools may be expanded / replaced entirely once
    real client use cases are scoped — treat the current `retrieve` /
    `graph_search` pair as the *starting* toolset, not the ceiling.
- Naming convention for sub-agent identity (`agent_id` string) — used in the
  event schema, Langfuse span names, and any future per-client config.
- Hop budget policy: does the orchestrator's `agent_max_hops` count a
  sub-agent call as one hop (regardless of how many hops the sub-agent burns
  internally), or does it need a separate global ceiling? (Recommend: one
  hop from the orchestrator's perspective; the sub-agent has its own
  independent `max_hops`.)
- Registry adoption timing: land Phase 2.5 (tool/specialist registry) before
  Phase 3, not after — writing `ask_graph_specialist` against an `if/elif`
  chain only to migrate it to a registry a week later is wasted motion.

### Phase 1 — Event schema: tag events with which agent emitted them

**File:** `app/schema/agent.py`

Add an optional `agent_id: str | None = None` field to every event variant
(or a shared base class the union members inherit from — cleaner given
they're all separate `BaseModel`s right now). `None` means "the top-level/
orchestrator agent," preserving current behavior for existing single-agent
runs with zero payload change on the wire. A nested agent stamps its own
`agent_id` on everything it yields.

This is the one change every later phase depends on — get it in first, even
before there's a second agent to tag.

### Phase 2 — Extract a reusable "agent core" from `run_agent`

**File:** `app/agent/agent.py`

`run_agent` currently hardcodes `[RETRIEVE_TOOL, GRAPH_SEARCH_TOOL]` (line
403) and loads `react_prompt.txt` unconditionally (`_load_prompt()`). Before
adding a second agent, parameterize what's currently implicit:

- `tools: list[Tool]` — defaults to the current pair, but overridable.
- `system_prompt: str` — defaults to `_load_prompt()`, but overridable so a
  sub-agent can load its own prompt file (e.g.
  `app/prompts/graph_specialist_prompt.txt`).
- `agent_id: str | None` — stamped onto every yielded event (Phase 1).
- Keep `max_hops` sourced from `profile.agent_max_hops` as today, but allow a
  sub-agent to pass its own `retrieval_profile`-equivalent override so a
  narrow specialist can run a tighter hop budget than the orchestrator.

This is a refactor, not new behavior — a call to `run_agent(...)` with no new
args must produce byte-identical output to today. Verify with the existing
eval harness (`eval/`) before moving on.

### Phase 2.5 — Tool/specialist registry (replaces the `if/elif` dispatch)

**New file:** `app/tools/registry.py`. **Changes:** `app/tools/dispatch.py`,
`app/agent/agent.py`, plus a one-line addition to each tool module.

Today, adding a tool means touching two places by hand: the hardcoded
`[RETRIEVE_TOOL, GRAPH_SEARCH_TOOL]` list in `agent.py` (line 403) and the
`if name == "retrieve": ... elif name == "graph_search": ...` chain in
`run_tool()` (`dispatch.py`). That's fine at 2 tools; it stops being fine once
`ask_graph_specialist` (Phase 3) and future specialists join — every new tool
becomes a two-file, easy-to-forget-a-branch edit, and it's exactly the kind of
central chokepoint that fights per-client tool enablement (Phase 8). Fix it
with a **flat registry**, not a class hierarchy — this is plug-and-play
without adopting LangChain's `BaseTool` abstraction:

```python
# app/tools/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from google.genai import types
from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    """Everything one tool needs to be advertised to Gemini and dispatched.

    ``run`` takes the validated ``args_schema`` instance plus keyword-only
    context (``api_key``, ``book_id``, ``session_id``, and any retrieval-
    profile knobs) and returns the result string. It must accept ``**kwargs``
    so profile knobs a given tool doesn't use don't blow up the call — every
    tool is called with the same kwargs, not a hand-tailored subset.
    ``is_async`` is True for sub-agent tools (Phase 3+), which internally
    await a nested ``run_agent`` call rather than doing blocking I/O.
    """

    name: str
    declaration: types.Tool
    args_schema: type[BaseModel]
    run: Callable[..., str] | Callable[..., Awaitable[str]]
    is_async: bool = False


_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    _REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def declarations(names: list[str] | None = None) -> list[types.Tool]:
    """Gemini tool declarations for the given names (default: every registered
    tool). ``names`` is how per-client tool enablement (Phase 8) plugs in —
    filter the list, no code branch needed."""
    keys = names if names is not None else list(_REGISTRY)
    return [_REGISTRY[n].declaration for n in keys if n in _REGISTRY]
```

Each tool module registers itself at import time — the existing `retrieve()`
and `graph_search()` functions don't change, they just gain a thin `run=`
wrapper and a `register(ToolSpec(...))` call at the bottom of
`retrieve.py`/`graph_search.py`:

```python
# bottom of app/tools/retrieve.py
def _run(args: RetrieveArgs, *, api_key=None, book_id=None,
         final_top_k=None, fused_top_k=None, passage_max_chars=None,
         **_ignored) -> str:
    return retrieve(args.query, top_k=final_top_k, api_key=api_key,
                     book_id=book_id, fused_top_k=fused_top_k,
                     passage_max_chars=passage_max_chars)

register(ToolSpec(name="retrieve", declaration=RETRIEVE_TOOL,
                   args_schema=RetrieveArgs, run=_run))
```

`dispatch.py`'s `run_tool()` collapses from an `if/elif` chain to one lookup:

```python
def run_tool(name, args, api_key=None, book_id=None, **profile_kwargs) -> str:
    spec = registry.get(name)
    if spec is None:
        return f"Unknown tool '{name}'. Available: {', '.join(_REGISTRY)}."
    try:
        parsed = spec.args_schema.model_validate(args)
    except ValidationError as e:
        return f"Invalid arguments for '{name}' ({e})."
    return spec.run(parsed, api_key=api_key, book_id=book_id, **profile_kwargs)
```

`execute_tool_call` branches once on `spec.is_async` to decide `await
spec.run(...)` directly vs. `await asyncio.to_thread(spec.run, ...)` — this is
also where the sync/async split for Phase 3's sub-agent tools belongs, since a
specialist's `run` awaits a nested `run_agent`, while `retrieve`/`graph_search`
stay blocking DB/embedding calls threaded off the event loop exactly as today.

`agent.py`'s hardcoded tool list becomes `registry.declarations(enabled_names)`
where `enabled_names` defaults to every registered tool today, and later
becomes the per-client allow-list from Phase 8 — no code change needed when a
client's tool set changes, only config.

This phase is pure refactor (no behavior change) and should land **before**
Phase 3, since Phase 3's `ask_graph_specialist` is written directly against
the registry rather than against another `if/elif` branch.

### Phase 3 — First sub-agent as a tool: `ask_graph_specialist`

**New file:** `app/tools/graph_specialist.py` (mirrors `retrieve.py` /
`graph_search.py`'s shape — a `Tool` schema + an implementation function).

- Tool schema: single `query: str` argument, like `graph_search` today.
- Implementation: calls the Phase-2 agent core with `tools=[GRAPH_SEARCH_TOOL]`
  only, a new narrower system prompt, and a fresh `agent_id="graph_specialist"`,
  collects the full `AsyncIterator[AgentEvent]` into a final answer string
  (same collapse `stream_chat()` already does for `pieces` — reuse that
  logic rather than duplicating it), and returns that string.
- Register it via `ToolSpec(..., is_async=True)` (Phase 2.5's registry) instead
  of adding another branch anywhere — the whole point of Phase 2.5 is that
  this is the only change this phase needs to make to wire the tool in.
- **This alone is the whole proof of concept.** Ship it, run it against real
  queries, confirm event tagging shows up correctly in the SSE stream and in
  Langfuse before building anything else on top.

### Phase 4 — Cancellation propagation

**File:** `app/agent/cancellation.py` (no change) + call sites.

Nested `run_agent` calls must be invoked with the *same* `session_id` as the
orchestrator. Because `CancellationRegistry.is_cancelled` is a pure lookup by
that id, this falls out for free — no new registry logic needed. The only
risk is a call site that forgets to thread `session_id` through; add this to
the code-review checklist for every new sub-agent tool.

### Phase 5 — Observability nesting

**File:** `app/observability/langfuse.py` (no change) + `agent.py` span
names.

A nested `run_agent` call opens its own `agent.run` span (line 306-309 of
`agent.py` today) — if invoked from inside the orchestrator's active
Langfuse context (which it will be, since `execute_tool_call` runs inside the
turn's `with ... as turn_obs:` block), it nests automatically as a child span.
The only change needed: name the span by `agent_id` (e.g.
`f"agent.run[{agent_id}]"`) so a trace visually distinguishes orchestrator
turns from specialist turns instead of showing two identically-named
`agent.run` spans at different depths.

### Phase 6 — Orchestrator prompt updates

**File:** `app/prompts/react_prompt.txt`

Add guidance for when to delegate to a specialist tool vs. call `retrieve`/
`graph_search` directly — e.g. "use `ask_graph_specialist` for multi-hop
relationship questions across entities; use `retrieve` for direct passage
lookup." This is prompt-engineering work, tune against the eval harness
(`eval/run_eval.py`, per the existing prompt-eval memory) rather than guessing.

### Phase 7 — Parallel sub-agents (only once Phase 3 is proven)

If/when a query benefits from two independent specialists running at once
(e.g. a graph specialist and a numeric-retrieval specialist both looking at
different aspects of the same question), add an orchestrator tool that fires
multiple nested `run_agent` calls via `asyncio.gather` and merges their
answers before returning a single tool result. Do not build this speculatively
— only once a real query pattern in Phase 3 usage demonstrably needs it.

### Phase 8 — Product-layer concerns (parallel track, not blocking)

Since this is a sellable product, these need attention alongside the agent
work but aren't part of the orchestration logic itself:

- **Per-client configuration** — which specialists/tools are enabled, prompt
  overrides, hop/cost ceilings — probably a row in a `clients` table read
  into `Settings`-like config at request time, keyed off `book_id` or a new
  `client_id`.
- **Cost ceilings** — nested agent calls multiply token spend (each sub-agent
  runs its own plan + ReAct loop). Add a per-request token budget check using
  the existing `UsageEvent` totals so one query can't runaway-spend across
  N nested agents.
- **Support/debuggability** — the `agent_id`-tagged events (Phase 1) plus
  Langfuse's nested spans (Phase 5) should be enough to answer "what did the
  agent do" for a client support ticket without reading logs by hand — worth
  validating with a real trace before calling this done.

### Phase 9 — Testing & rollout

- Extend the `eval/` harness to run a fixed set of queries through both the
  pre- and post-change agent and diff grounded-answer quality + token cost
  (same methodology as the token-optimization case study in this `docs/`
  folder).
- Ship Phase 3 (single specialist) behind no flag initially — it's additive
  (a new tool the model may or may not call) so it's safe to ship directly,
  but watch Langfuse traces for a week before adding a second specialist.

---

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Nested agent calls multiply token cost per query | Phase 8 cost ceiling; keep specialists narrow-scoped so they resolve in fewer hops |
| Orchestrator over-delegates (calls a specialist when `retrieve` would've done) | Prompt tuning in Phase 6, measured against eval harness — this is a prompt-engineering problem, not an architecture one |
| Sub-agent forgets `session_id` → cancel doesn't propagate | Code-review checklist item (Phase 4); could add an assertion in the Phase-2 core that raises if `session_id` is `None` when called from a tool context |
| Event schema change breaks the frontend's SSE handling | `agent_id` is additive/optional — old frontend code that ignores unknown fields keeps working; confirm frontend `model_dump()` consumers don't do strict schema validation |
| Scope creep — building parallel execution or generic multi-agent framework before there's a proven need | Explicit "do not build Phase 7 speculatively" gate above |

---

## 6. Open questions for Tarun

1. Confirm first specialist to build (recommended: graph specialist — Phase 3).
2. Naming convention for `agent_id` values (plain strings vs. an enum in
   `app/schema/agent.py`)?
3. Should hop budget for a sub-agent call count as 1 hop against the
   orchestrator's `max_hops`, or should there be a separate global ceiling
   across the whole call tree (recommended: 1 hop from orchestrator's view,
   independent budget inside the sub-agent)?
4. Any specific specialist domains beyond graph search already in mind for
   this product (e.g. a numeric/table-extraction specialist, a cross-book
   comparison specialist)? Would help sequence Phase 3+ concretely instead of
   guessing at the second specialist.
