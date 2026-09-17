# Graph Report - .  (2026-07-14)

## Corpus Check
- 81 files · ~109,233 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 760 nodes · 1532 edges · 52 communities (45 shown, 7 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 139 edges (avg confidence: 0.67)
- Token cost: 275,241 input · 0 output

## Community Hubs (Navigation)
- Embedding & Chunking
- Hybrid Store & BM25 Index
- Attachments & Cancellation
- Prompt Eval Findings
- ReAct Agent Loop & Tests
- LLM Reranker
- Document Loaders & Schema
- Gemini Client & GraphRAG Index
- App Composition & Observability
- Tool Dispatch & Tool Modules
- Eval Harness & Scoring
- Agent Event Schema
- Chat Transcript Import
- Chat History Persistence
- Base-vs-Atlas Comparison Chart
- Retrieve Tool Tests
- Answer Cleaning & Base Comparison
- Ingestion Architecture Concepts
- Multimodal Embedding Methods
- ReAct System Prompt Rules
- Planning Prompt & Scope Rules
- JPMorgan Chase Entities
- Jio IPO Corporate Structure
- Token Cost Optimization Levers
- GraphRAG Tool Research
- Chunking Library Research
- Backend-Managed Keys
- Tool Selection Prompt Rules
- Tool Registry Architecture
- Positioning & Business Model
- Deployment & Dependencies
- Graph Serialization
- Planning Documents
- Model Retrieval Profiles
- Multi-Agent Orchestration
- Project Root & Runtime
- Vercel Configuration
- Test Fixtures
- RAG Package Init
- Cancellation Propagation
- Consulting Engagement Model
- MCP Configuration
- Planning Turn Tuning
- Atlas Backend Root

## God Nodes (most connected - your core abstractions)
1. `Settings` - 47 edges
2. `get_settings()` - 40 edges
3. `HybridStore` - 38 edges
4. `run_agent()` - 36 edges
5. `Chunk` - 36 edges
6. `GraphIndex` - 31 edges
7. `GeminiEmbedding` - 30 edges
8. `Gemini` - 25 edges
9. `ModelSettings` - 24 edges
10. `Reranker` - 23 edges

## Surprising Connections (you probably didn't know these)
- `HybridStore over pgvector` --conceptually_related_to--> `rank-bm25 (in-memory lexical index)`  [AMBIGUOUS]
  README.md → requirements.txt
- `Securities and Exchange Board of India (SEBI)` --conceptually_related_to--> `SCOPE — Strict Financial Boundaries`  [INFERRED]
  data/overviews/jio-ipo.txt → app/prompts/react_prompt.txt
- `Book Overviews (one plain-text file per book)` --conceptually_related_to--> `Meta / Capability Questions Are In Scope`  [INFERRED]
  data/overviews/README.md → app/prompts/react_prompt.txt
- `RunResult` --uses--> `TextEvent`  [INFERRED]
  eval/run_eval.py → app/schema/agent.py
- `RunResult` --uses--> `PlanEvent`  [INFERRED]
  eval/run_eval.py → app/schema/agent.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Atlas Three-Stage Prompt Pipeline (plan -> ReAct loop -> forced final answer)** — app_prompts_plan_prompt_planning_step, app_prompts_react_prompt_atlas_persona, app_prompts_force_answer_prompt_final_hop_fallback, app_prompts_react_prompt_your_plan_section [EXTRACTED 1.00]
- **Prompt-Injection & Scope Defense Layer** — app_prompts_react_prompt_immutable_instructions, app_prompts_react_prompt_untrusted_data_rule, app_prompts_react_prompt_silent_injection_handling, app_prompts_react_prompt_scope_boundary, app_prompts_react_prompt_refusal_text, app_prompts_react_prompt_grounding_and_citations [EXTRACTED 1.00]
- **Jio Corporate Structure and IPO Filing Chain** — data_overviews_jio_ipo_jio, data_overviews_jio_ipo_reliance_jio_infocomm, data_overviews_jio_ipo_jio_platforms_limited, data_overviews_jio_ipo_reliance_industries_limited, data_overviews_jio_ipo_drhp, data_overviews_jio_ipo_sebi [EXTRACTED 1.00]
- **Hierarchical Multi-Agent Orchestration (Phases 1–5 acting together)** — docs_multi_agent_architecture_plan_agent_id_event_tagging, docs_multi_agent_architecture_plan_agent_core_extraction, docs_multi_agent_architecture_plan_tool_registry, docs_multi_agent_architecture_plan_ask_graph_specialist, docs_multi_agent_architecture_plan_cancellation_propagation, docs_multi_agent_architecture_plan_observability_nesting [EXTRACTED 1.00]
- **The Six Levers Producing the ~70% Token Reduction** — docs_token_optimization_case_study_system_prompt_trim, docs_token_optimization_case_study_passage_cap, docs_token_optimization_case_study_narrowed_retrieval_breadth, docs_token_optimization_case_study_cheaper_planning_turn, docs_token_optimization_case_study_implicit_caching, docs_token_optimization_case_study_tool_result_eviction [EXTRACTED 1.00]
- **The Three Real Defects Exposed in Atlas's GraphRAG** — docs_tools_research_entity_resolution_defect, docs_tools_research_temporal_triples, docs_tools_research_incremental_graph_build, docs_tools_research_atlas_graphindex [EXTRACTED 1.00]
- **Scratchpad-Leak Fix Bundle (prompt rule + plan reframe + deterministic guard)** — eval_findings_scratchpad_leak, eval_findings_forbidden_openers_rule, eval_findings_plan_as_private_scratch, eval_findings_clean_answer_guard, eval_findings_prompt_intent_plus_backstop_pattern [EXTRACTED 1.00]
- **Eval Run Progression (smoke -> baseline -> baseline2 -> fixcheck -> optimized)** — eval_results_smoke_run, eval_results_baseline_run, eval_results_baseline2_run, eval_results_fixcheck_run, eval_results_optimized_run, eval_findings_prompt_optimization_report [INFERRED 0.85]
- **Adversarial Vulnerability Categories Stress-Testing Atlas** — eval_questions_for_llm_semantic_scope_blurring, eval_questions_for_llm_json_hijacking_injection, eval_questions_for_llm_meta_capability_boundaries, eval_questions_for_llm_no_tool_deadlock, eval_questions_for_llm_clarification_traps, eval_questions_for_llm_unit_conversion_math_injection, eval_questions_for_llm_stress_test_generator [EXTRACTED 1.00]

## Communities (52 total, 7 thin omitted)

### Community 0 - "Embedding & Chunking"
Cohesion: 0.05
Nodes (53): GeminiEmbedding, get_embedder(), Gemini embedding wrapper.  Why a wrapper at all? Three reasons:   1. One place t, Embedding client. With ``api_key`` (a visitor's own key) a fresh, uncached     c, approx_tokens(), chunk_documents(), chunk_pages_as_pdf(), _make_children() (+45 more)

### Community 1 - "Hybrid Store & BM25 Index"
Cohesion: 0.06
Nodes (39): BM25Index, In-memory BM25 lexical index (``rank_bm25``) over cached chunk tokens.  The lexi, A frozen BM25 index over a fixed corpus of ``(id, tokens)`` documents.      Chea, Top-``top_k`` ``(chunk_id, score)`` for the tokenized query, best first., HybridStore, Any, ndarray, Embed chunks into one shared space: PDF-page chunks go through the         multi (+31 more)

### Community 2 - "Attachments & Cancellation"
Cohesion: 0.06
Nodes (47): AttachmentError, build_attachment_parts(), _build_part(), _decode(), _docx_to_text(), Part, Turn user-uploaded files into Gemini input parts.  The chat stream lets the user, Paragraphs + table rows from a .docx. Embedded images are dropped (Gemini     ca (+39 more)

### Community 3 - "Prompt Eval Findings"
Cohesion: 0.06
Nodes (46): Anti-Loop Guards Hold (0 timeouts / 0 loop-forced in 60 runs), Base LLM vs Atlas-Powered Comparison (63% -> 85% overall pass), _clean_answer() Deterministic Output Guard, Empty Answer Defect (blank first ReAct turn handed to user), Empty-Terminal-Turn Retry + Never-Return-Blank Fallback, Eval Method (fixed question set x 3 models x 3 axes), Forbidden-Openers Prompt Rule, gemini-3.1-flash-lite (eval model) (+38 more)

### Community 4 - "ReAct Agent Loop & Tests"
Cohesion: 0.10
Nodes (38): _compact_old_tool_results(), _load_force_prompt(), _load_plan_prompt(), _load_prompt(), AgentEvent, Any, Content, Part (+30 more)

### Community 5 - "LLM Reranker"
Cohesion: 0.14
Nodes (26): _CandidateScore, BaseModel, One batched structured call → ``{candidate_index: score}``., A relevance judgement for one candidate, keyed by its list index., The judge's scores for every candidate shown., Rerank fused candidates by answer-usefulness via a single Gemini call., Reorder ``candidates`` by relevance and keep the top ``top_k``.          Falls b, Reranker (+18 more)

### Community 6 - "Document Loaders & Schema"
Cohesion: 0.11
Nodes (25): _extract_page_text(), _load_docx(), load_file(), load_path(), _load_pdf(), load_text(), _page_pdf_bytes(), Path (+17 more)

### Community 7 - "Gemini Client & GraphRAG Index"
Cohesion: 0.14
Nodes (17): Postgres-backed chat history.  Persists the global conversation (not user-scoped, Gemini, get_gemini(), Constrained decoding into a Pydantic model., Gemini client. With ``api_key`` (a visitor's own key) a fresh, uncached     clie, Async version — yields chunks without blocking the event loop., Logfire observability — wiring + the project logger.  Configures Pydantic Logfir, Entities (+9 more)

### Community 8 - "App Composition & Observability"
Cohesion: 0.11
Nodes (21): health(), root(), get_langfuse_client(), langfuse_lifespan(), FastAPI, Langfuse observability — wiring only.  Two jobs:  1. Hand out a single, process-, Return the shared Langfuse client, creating it once on first use.      No args:, Startup: verify the keys. Shutdown: flush the outbox, then stop cleanly.      Ev (+13 more)

### Community 9 - "Tool Dispatch & Tool Modules"
Cohesion: 0.13
Nodes (21): execute_tool_call(), Content, Tool round-trip: dispatch a native function call and feed the result back.  When, Dispatch a native function call from the agent.      ``args`` is validated again, Run a tool the model requested; return its result and the history turns.      Re, run_tool(), graph_search(), GraphSearchArgs (+13 more)

### Community 10 - "Eval Harness & Scoring"
Cohesion: 0.18
Nodes (19): The result of a tool the model called, surfaced back to the client.      The sam, ToolResultEvent, _corpus_floats(), _extract_numbers(), _grounded(), _leaked(), main(), _norm_num() (+11 more)

### Community 11 - "Agent Event Schema"
Cohesion: 0.16
Nodes (16): AgentEvent, Content, Tool, Stream one agent turn with native function calling.          Yields typed events, PlanEvent, BaseModel, Agent streaming-event schema.  ``Gemini.stream_agent_turn_async`` emits one even, A streamed text chunk — part of the model's final answer. (+8 more)

### Community 12 - "Chat Transcript Import"
Cohesion: 0.18
Nodes (16): datetime, _col_type(), _load_messages(), main(), _pair_into_turns(), Any, Path, Import one client-side (localStorage) chat transcript into the Postgres history. (+8 more)

### Community 13 - "Chat History Persistence"
Cohesion: 0.18
Nodes (11): ChatHistoryStore, coalesce_steps(), _col_type(), AgentEvent, Any, Persist one full turn: the user prompt, the assistant answer, and the         co, Prior turns of a conversation as plain ``{role, content}`` messages,         old, Conversations for the history list, most-recently-active first.          One row (+3 more)

### Community 14 - "Base-vs-Atlas Comparison Chart"
Cohesion: 0.18
Nodes (17): Metric: Answered in-scope — base 100% vs Atlas 100% (parity), Series: Atlas-powered (green bars, RAG agent over the documents), Series: Base model (red bars, no retrieval/agent), Panel 1: Capability comparison (all models), grouped bar chart, Score %, Base LLM vs Atlas-powered — financial-document QA (comparison chart), Metric: Clean output — base ~100% vs Atlas 98% (base label partly hidden by legend), Metric: Correct refusals — base 0% vs Atlas 67%, Data source: Atlas eval/ harness results over the financial-document QA suite (+9 more)

### Community 15 - "Retrieve Tool Tests"
Cohesion: 0.21
Nodes (11): _FakeEmbedder, _FakeReranker, _FakeStore, _patch(), Unit tests for the ``retrieve`` tool's output formatting (app/tools/retrieve.py), Identity reranker: keeps the fed order, truncated to ``top_k``., _scored(), test_empty_query_short_circuits() (+3 more)

### Community 16 - "Answer Cleaning & Base Comparison"
Cohesion: 0.22
Nodes (12): _accumulate(), _clean_answer(), _opens_leaky(), Strip a leaked reasoning preamble from the final answer, conservatively.      Tw, Fold one turn's token counts into the running ``scope="total"`` tally., _base_answer(), _dims(), main() (+4 more)

### Community 17 - "Ingestion Architecture Concepts"
Cohesion: 0.19
Nodes (13): book_id Derived From Title (titles must match exactly), Book Overviews (one plain-text file per book), metadata.kind = "overview" Chunk Tag, Column-Aware PDF Extraction, Dry-Run Ingest Default (persist=false), HybridStore over pgvector, Ingestion Half (load -> chunk -> embed -> store), Page-as-Parent Chunking Strategy (+5 more)

### Community 18 - "Multimodal Embedding Methods"
Cohesion: 0.24
Nodes (5): ndarray, Embed single-page PDFs -> (n, dim) float32 array, L2-normalized.          Multim, Embed ONE text. ``embed_content`` returns a single embedding per call         fo, Embed one single-page PDF as a multimodal unit (text + images +         charts o, Embed texts -> (n, dim) float32 array, L2-normalized.          One request per t

### Community 19 - "ReAct System Prompt Rules"
Cohesion: 0.22
Nodes (11): Force-Answer Chart Block Spec (condensed), Force-Answer Prompt (final-hop, tools withheld), Force-Answer Forbidden Openers, Partial-Answer-Is-Complete Rule, Atlas — Financial Intelligence Assistant (ReAct System Prompt), Fenced ```chart Block Spec, Grounding & Citations (bracket-numbered passages), Immutable Instructions — Highest Precedence (+3 more)

### Community 20 - "Planning Prompt & Scope Rules"
Cohesion: 0.22
Nodes (11): No Numbered Plan Formatting (prevents step-spill into the answer), Planning Step Prompt (tool-less first turn), Plan-Time Scope Check (one-sentence decline plan), Attached Files Answered Without Tools, Forbidden Openers List, Meta / Capability Questions Are In Scope, Verbatim Refusal Text, SCOPE — Strict Financial Boundaries (+3 more)

### Community 21 - "JPMorgan Chase Entities"
Cohesion: 0.24
Nodes (11): JPMorgan Chase Annual Report 2025, Asset & Wealth Management, Chase (consumer & small business banking brand), Commercial & Investment Bank, Consumer & Community Banking, Fortress Balance Sheet, Jamie Dimon (CEO Letter), J.P. Morgan (investment & commercial banking brand) (+3 more)

### Community 22 - "Jio IPO Corporate Structure"
Cohesion: 0.20
Nodes (10): Jio Digital Ecosystem Segment, Draft Red Herring Prospectus (DRHP), Jio Enterprise Business Segment, Jio IPO Status (as of 28 June 2026 — not yet listed), Jio (India's largest digital connectivity company), Jio Platforms Limited, Reliance Industries Limited, Reliance Jio Infocomm Limited (+2 more)

### Community 23 - "Token Cost Optimization Levers"
Cohesion: 0.22
Nodes (10): Per-Request Token Cost Ceiling, Parallel Sub-Agents via asyncio.gather (Phase 7, do not build speculatively), Gemini Implicit Prefix Caching (cached_tokens / Langfuse cache_read), Context-Starvation Infinite Re-Search Loop, Narrowed Retrieval Breadth (FINAL_TOP_K 6→4, FUSED_TOP_K 12→8), PASSAGE_MAX_CHARS Passage Cap with Child-Span Fallback, ReAct Loop Cost Compounding (whole conversation re-sent per hop), Repeat-Search Breaker (_query_key) (+2 more)

### Community 24 - "GraphRAG Tool Research"
Cohesion: 0.24
Nodes (10): Cut / Park List (GraphRAG, financial framing, BYO-key, multi-provider, multi-tenancy), Atlas GraphIndex (app/rag/graph.py) — a MS-GraphRAG-lite, fully wired, Entity Resolution Is String Normalization Only (_norm) — biggest graph quality bug, Graphiti (Zep) — temporal knowledge graph on Neo4j, Full Rebuild on Every Ingest / Incremental Graph Build, /learn-First Gate on the Graph Pipeline, LightRAG — dual-level retrieval, cheap indexing, Microsoft GraphRAG (+2 more)

### Community 25 - "Chunking Library Research"
Cohesion: 0.20
Nodes (10): Depth + Measurement, Never Breadth, Tools Research Ledger, approx_tokens() len//4 Estimate (low severity), Chonkie (chunking library) — verdict: partial, Cognee — modular memory engine (irrelevant to Atlas), LateChunker (embed-then-split), Page-as-Parent Retrieval Structure (why Chonkie can't replace chunking.py), _SENT_SPLIT Abbreviation Defect (high severity) (+2 more)

### Community 26 - "Backend-Managed Keys"
Cohesion: 0.25
Nodes (8): Backend-Managed Gemini Keys, Deletion, Not Rewrite (server key was always the base case), Innermost-Out Deletion Sequencing, Key/Model Fallback Pool, Settings (app/schema/llm_settings.py), agent_id Event Tagging (Phase 1), Langfuse Span Nesting by agent_id (Phase 5), gemini-3.5-flash Carve-Out (relaxed retrieval profile)

### Community 27 - "Tool Selection Prompt Rules"
Cohesion: 0.32
Nodes (8): Tool Selection Heuristic (retrieve vs graph_search local/global), graph_search(query, mode) Tool Declaration, Know When To Stop — Do Not Loop, retrieve(query) Tool Declaration, Tool-First Rule (never answer document questions from memory), GraphRAG Intentionally Deferred, Stale Status: No Tools Wired Yet, networkx (graph index backing)

### Community 28 - "Tool Registry Architecture"
Cohesion: 0.29
Nodes (8): Hardcoded if/elif Tool Dispatch (app/tools/dispatch.py), Per-Client Tool Enablement / Configuration (Phase 8), Flat Tool/Specialist Registry (Phase 2.5), ToolSpec dataclass, calculate (deterministic arithmetic; LLM must never do math), query_records (text-to-SQL with row-level provenance), The Three Tool Archetypes, Write Tool Behind Dry-Run → Approval → Idempotency → Audit Log

### Community 29 - "Positioning & Business Model"
Cohesion: 0.25
Nodes (8): Connectors Are a Treadmill, Not a Moat, Document Search Doesn't Convert (Copilot 3.3% / 6% pilot-scale), Eval Discipline as the Domain-Agnostic Differentiator, The Product Emerges From 3–4 Engagements, Public Quality Dashboard (grounding / refusal / cost), Atlas as Reference Implementation, Not Product, The Four ROI Currencies, Langfuse Eval Dataset from Real Traces (next step)

### Community 30 - "Deployment & Dependencies"
Cohesion: 0.25
Nodes (8): LLM Layer Singletons (get_gemini / get_embedder), Serverless SSE / maxDuration Constraint, Task-Typed L2-Normalized Embeddings, Vercel Python Runtime Deployment, google-genai (Gemini SDK), openai (undeclared-purpose direct dependency), tenacity (retry wrapper for LLM clients), requirements.txt Autogenerated from uv.lock

### Community 31 - "Graph Serialization"
Cohesion: 0.29
Nodes (6): _deserialize(), Upsert the serialized graph + community summaries into ``graphs``., networkx -> JSON-safe dict. Node ``chunks`` sets become sorted lists., JSON dict -> networkx. Node ``chunks`` lists become sets again., _serialize(), MultiDiGraph

### Community 32 - "Planning Documents"
Cohesion: 0.29
Nodes (7): Plan: Remove BYO-Key, Backend-Managed Gemini Keys Only, BYO-Key (visitor-supplied Gemini key), Frontend Deploy-Order Coordination (atlas-frontend), X-Gemini-Api-Key header, Plan: Multi-Agent Orchestration for Atlas (Manual, No Framework), Atlas: What It Is, What It Proves, What It Sells, Case Study: Cutting Atlas's Per-Query Token Cost by ~70%

### Community 33 - "Model Retrieval Profiles"
Cohesion: 0.33
Nodes (4): The model-dependent retrieval/eviction/hop knobs for one agent run.      Resolve, True only for the weak flash model the loop-guards target.          Matched by s, Resolve the retrieval/eviction/hop knobs for the active generation model., RetrievalProfile

### Community 34 - "Multi-Agent Orchestration"
Cohesion: 0.40
Nodes (6): Reusable Agent Core Extraction (Phase 2), ask_graph_specialist (first sub-agent as a tool, Phase 3), Hierarchical Agent-as-Tool Pattern, Hop Budget Policy (sub-agent = 1 orchestrator hop), No-Framework Decision (own the orchestration loop), run_agent() (existing plan → ReAct loop)

### Community 35 - "Project Root & Runtime"
Cohesion: 0.50
Nodes (5): Atlas Backend, Env-Driven Cached Settings, uvicorn Must Be Invoked via python -m, fastapi, langfuse (observability)

### Community 36 - "Vercel Configuration"
Cohesion: 0.40
Nodes (4): maxDuration, functions, api/index.py, rewrites

## Ambiguous Edges - Review These
- `HybridStore over pgvector` → `rank-bm25 (in-memory lexical index)`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `GraphRAG Intentionally Deferred` → `graph_search(query, mode) Tool Declaration`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `Stale Status: No Tools Wired Yet` → `retrieve(query) Tool Declaration`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `Anti-Loop Guards Hold (0 timeouts / 0 loop-forced in 60 runs)` → `pro-preview 240s Timeout on jpm-risks (must_not_loop violation)`  [AMBIGUOUS]
  eval/results/fixcheck.md · relation: conceptually_related_to
- `Panel 1: Capability comparison (all models), grouped bar chart, Score %` → `Metric: Clean output — base ~100% vs Atlas 98% (base label partly hidden by legend)`  [AMBIGUOUS]
  eval/results/comparison.png · relation: references

## Knowledge Gaps
- **42 isolated node(s):** `supabase`, `Atlas-backend`, `rewrites`, `maxDuration`, `Asset & Wealth Management` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `HybridStore over pgvector` and `rank-bm25 (in-memory lexical index)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `GraphRAG Intentionally Deferred` and `graph_search(query, mode) Tool Declaration`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Stale Status: No Tools Wired Yet` and `retrieve(query) Tool Declaration`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Anti-Loop Guards Hold (0 timeouts / 0 loop-forced in 60 runs)` and `pro-preview 240s Timeout on jpm-risks (must_not_loop violation)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Panel 1: Capability comparison (all models), grouped bar chart, Score %` and `Metric: Clean output — base ~100% vs Atlas 98% (base label partly hidden by legend)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `get_settings()` connect `Embedding & Chunking` to `Attachments & Cancellation`, `Document Loaders & Schema`, `Gemini Client & GraphRAG Index`, `App Composition & Observability`, `Tool Dispatch & Tool Modules`, `Eval Harness & Scoring`, `Chat Transcript Import`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `Settings` connect `Embedding & Chunking` to `Hybrid Store & BM25 Index`, `Model Retrieval Profiles`, `LLM Reranker`, `Gemini Client & GraphRAG Index`, `Chat History Persistence`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._