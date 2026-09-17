# Tools Research

A running ledger of third-party tools and libraries evaluated for Atlas. One section
per tool. The point is to record **what we could take from it**, **what it would cost
us**, and **the decision** — so we never re-litigate the same evaluation from scratch,
and so a deferred "no" can be revisited when the conditions that made it a "no" change.

## How to use this file

Every entry carries a **verdict** and, if the verdict is not "adopt", the **trigger**
that would change it. A "no" here is almost never "this tool is bad" — it's "this tool
does not pay for itself *given what Atlas looks like today*." Write down what would have
to be true for it to pay for itself, so future-us can check that condition cheaply.

Standing constraints that every evaluation is judged against:

- **Atlas is a product we intend to sell**, not a portfolio piece. Favor control and
  no lock-in over framework convenience. A library we call is fine; a framework that
  calls us is a liability.
- **Single provider (Gemini) until a named client need forces otherwise.** Don't adopt a
  tool for its multi-provider abstraction alone.
- **Dependency weight is a real cost.** Prefer taking one idea from a library over taking
  the library, unless we'd use a meaningful fraction of its surface area.

Verdict values: `adopt` · `partial` (take a piece) · `defer` (good, not yet) ·
`reject` (won't use).

---

## Chonkie

- **Repo:** https://github.com/feyninc/chonkie · **PyPI:** `chonkie` 1.7.0
- **License:** MIT (verified from `LICENSE` + PyPI metadata — a secondary source claimed
  Apache 2.0; it is wrong). MIT is compatible with selling Atlas.
- **Python:** >=3.10 (we're >=3.12 — fine)
- **Evaluated:** 2026-07-13
- **Verdict:** `partial` — do not adopt as our chunker. Take it only if we want semantic
  or late chunking as a real ingest option (see *What's genuinely ours to gain*).

### What it is

A chunking library for RAG: text in, chunks out. Actively maintained (~4.4k stars,
v1.7.0). It is a *library*, not a framework — chunkers are plain callables returning
plain chunk objects, so lock-in is low. That's in its favor.

### What it offers (full inventory)

**Chunkers**

| Chunker | What it does |
| --- | --- |
| `TokenChunker` | Fixed-size token chunks |
| `FastChunker` | SIMD-accelerated byte-level chunking, 100+ GB/s |
| `SentenceChunker` | Sentence-boundary chunks |
| `RecursiveChunker` | Hierarchical splitting on customizable rules |
| `SemanticChunker` | Splits on embedding-similarity topic shifts |
| `LateChunker` | Embeds first, then splits — better chunk embeddings |
| `CodeChunker` | Structure-aware code splitting |
| `NeuralChunker` | Splits with a trained neural boundary model |
| `SlumberChunker` | Uses an LLM to find semantic boundaries |
| `TableChunker` | Chunks markdown tables by row or char count |
| `TeraflopAIChunker` | Splits via the TeraflopAI segmentation API |

**Refineries** — `OverlapRefinery` (merge overlapping chunks by similarity),
`EmbeddingsRefinery` (attach embeddings from any provider).

**Handshakes (vector-DB writers)** — Chroma, Elasticsearch, MongoDB, **PostgreSQL
pgvector**, Pinecone, Qdrant, Turbopuffer, Weaviate, LanceDB, Milvus.

**Claimed benchmarks** — token chunking 33x faster than the slowest alternative;
sentence chunking ~2x faster than competitors; semantic chunking up to 2.5x faster.
(Unverified by us. Chunking is not on our hot path — this is ingest-time work — so
raw speed is close to irrelevant for Atlas either way.)

**Install weight** — 505KB wheel, ~49MB installed. Base deps are actually light and
mostly things we already carry: `tqdm`, `numpy`, `chonkie-core` (the Rust extension —
this is where the 49MB lives), `tenacity`, `httpx`, `tokie`. Everything else is behind
extras (`semantic`, `pgvector`, `gemini`, `st`, `model2vec`, `neural`, `table`, …).

### Why it can't replace `app/rag/chunking.py`

Our chunking isn't "text → chunks". It's a **retrieval structure**, and the structure is
the load-bearing part:

- `chunk_pages_as_pdf()` (`app/rag/chunking.py:126`) emits a *multimodal page parent*
  (`embed_pdf` set, so charts and tables get embedded **visually** by gemini-embedding)
  **plus** text children sharing the same `parent_id` / `parent_text`. This is how a
  chart-only page stays retrievable at all, and how the retriever collapses page+children
  back to a single parent at generation time.
- Every `Chunk` carries `parent_text`, `book_id`, `title`, and a content-hash `id`
  (`Chunk.make_id`) that makes re-ingestion idempotent via `ON CONFLICT DO NOTHING`.
- Chunks carry precomputed `bm25_tokens` for the lexical index.

Chonkie has **no concept** of parent-document retrieval, multimodal parents, or our ID
scheme. Hand it our pages and we get flat chunks, then rebuild all of the above around
it anyway. Its pgvector handshake is likewise useless to us — it writes *its* schema, and
`HybridStore` owns ours.

So: the chunkers could at most replace the **inner windowing loop**
(`split_sentences` + `_pack`, `app/rag/chunking.py:26-65`), not the module.

### What using it would fix (real weaknesses in our chunker)

1. **`approx_tokens()` is `len(text) // 4`** (line 30). Every chunk boundary is set by a
   guess, so `CHUNK_TOKENS` doesn't mean what it says. Chonkie uses real tokenizers.
   *Severity: low* — HNSW recall is not sensitive to ±10% chunk size.
2. **`_SENT_SPLIT` breaks on financial prose** (line 26). The regex
   `(?<=[.!?])\s+(?=[A-Z0-9])` splits after **any** period followed by a capital, so
   "U.S. Treasury", "Acme Inc. The board…", "Rs. 500 crore" all get cut mid-sentence.
   On financial filings this is not a corner case — it's most pages.
   *Severity: high. This is the one that's actually costing us retrieval quality.*
3. **Our `SemanticChunker` calls the Gemini embedding API on every sentence of every
   page** (line 219) at ingest time — slow and metered. Chonkie's runs on a local
   model2vec model: same idea, near-zero marginal cost.

### Why we're still not taking it

Weakness #2 is ~15 lines of abbreviation handling, or a far smaller dep (`pysbd`,
`blingfire`) that does exactly one thing. Weakness #1 barely matters. Pulling in a
library with 11 chunkers, 2 refineries, 10 vector-DB handshakes, a pipeline framework and
a REST server — to use *one splitter* — is the wrong trade for a product that's
deliberately kept free of framework lock-in.

### What's genuinely ours to gain (the revisit trigger)

The one thing we **cannot cheaply build ourselves** is `LateChunker` (embed-then-split,
which produces materially better chunk embeddings) and a **cheap local** `SemanticChunker`.
Those are capabilities, not conveniences.

**Adopt `chonkie[semantic]` if** we decide chunking strategy is a lever we want to tune —
i.e. we're prototyping late/semantic chunking against `eval/` and want to compare
strategies without writing three of them. It slots cleanly behind our existing
`SemanticChunker` interface in `app/rag/pipeline.py:128`, so the experiment is cheap and
reversible.

**Also worth a second look if** we ever ingest source code (`CodeChunker`) or
table-dense markdown (`TableChunker`) — both are real gaps in our current chunker.

### Actions taken

- [ ] Fix `_SENT_SPLIT` abbreviation handling (independent of Chonkie — do this regardless)
- [ ] *(optional)* Prototype Chonkie's `SemanticChunker` / `LateChunker` behind the
      existing interface and eval both against `eval/`

---

## GraphRAG tools (Microsoft GraphRAG · Graphiti · LightRAG · Cognee · TypeGraph)

- **Source:** https://typegraph.ai/blog/best-open-source-graph-rag-tools
- **Evaluated:** 2026-07-13
- **Verdict:** `reject` as dependencies · `partial` as ideas — **we already have a
  GraphRAG.** The valuable output of this evaluation is not a tool to adopt, it's three
  concrete defects it exposed in our own `app/rag/graph.py`.

> ⚠️ **Read the source skeptically.** The article is written by **Ryan Musser, founder of
> TypeGraph**, and TypeGraph wins both benchmarks it reports (62.65 / 67.68 vs Microsoft
> GraphRAG's 50.93 / 45.16 and LightRAG's 45.09 / 62.59). Self-reported numbers, own
> product on top. Treat the benchmark table as marketing and the *taxonomy* as the useful
> part.

### First, where Atlas actually stands

`app/rag/graph.py` (483 lines) is **already a Microsoft-GraphRAG-lite, and it is fully
wired**: `IngestionPipeline._build_graph()` (`app/rag/pipeline.py:196`) builds and
persists a per-book graph on every ingest, best-effort. We have:

- LLM triple extraction per **parent block** via constrained decoding (`_extract`, gated
  by `graph_min_block_chars`)
- entity merge + provenance back to real passages (`_touch_node` accumulates a `chunks`
  set — that set is the bridge from graph hit → citable passage)
- community detection (`greedy_modularity_communities`) + Gemini community summaries,
  embedded for matching
- `local_search` (entity traversal) and `global_search` (community-summary ranking)
- persistence to a Postgres `graphs` table

> **Note:** CLAUDE.md claims graph *building* "may still be incomplete." **That is stale
> — it is complete and wired.** Fix that line.

So the question is never "which GraphRAG do we adopt." It's "what do these tools do that
ours doesn't."

### The tools, mapped onto Atlas

| Tool | License / Stack | What it is | Verdict for Atlas |
| --- | --- | --- | --- |
| **Microsoft GraphRAG** | MIT, Python | The reference impl: community detection + hierarchical summaries. Expensive indexing, slow on real data. | **We are already this**, minus hierarchical communities. Nothing to adopt. |
| **Graphiti** (Zep) | Apache 2.0, Python **on Neo4j** | Temporal knowledge graph — time-bound facts, fast **incremental** ingestion. | **Best ideas in the list; can't take the library** (Neo4j). Steal temporality + incrementality. |
| **LightRAG** | MIT, Python, 10k+ ★ | Dual-level (entity + concept) retrieval, **no community detection** → much cheaper indexing. | Worth reading for **indexing cost**, our weakest axis. Not a dep. |
| **Cognee** | Apache 2.0, Python | Modular memory engine, swappable graph stores (Kuzu/Neo4j/FalkorDB). | **Irrelevant.** Its selling point is backend flexibility; we are deliberately committed to one Postgres. |
| **TypeGraph** | MIT, **TypeScript** on Postgres+pgvector | TS-native graph RAG with entity resolution + MCP server. | **Non-starter** (TypeScript, Python backend). But it runs on *our exact substrate*, so its **entity-resolution** approach is worth reading. |

### The three real defects this exposed in our graph

Ranked by what they cost us:

1. **Entity resolution is string normalization only.** `_norm(name)` (`graph.py:462`) is
   the entire entity-resolution layer, so **"Apple Inc.", "Apple", and "AAPL" become
   three unconnected nodes.** On financial filings — where the same entity appears as a
   legal name, a ticker, and a short name on the same page — this fragments the graph
   badly, and a fragmented graph makes `local_search` miss. *This is the single biggest
   quality bug in our GraphRAG.* Both TypeGraph and LightRAG treat real entity resolution
   (embedding-based alias merging) as table stakes; we don't have it.

2. **No temporal modeling — and we are a *financial* RAG.** Our triples are timeless, but
   almost every fact in a filing is only true for a fiscal period: "revenue was $X" is
   meaningless without "in Q3 FY2024". Ingest two years of filings for one company and
   our graph will happily assert contradictory revenue triples with no way to tell them
   apart. **Graphiti's time-bound edges (`valid_from`/`valid_to`) are the single most
   relevant idea in this article for Atlas specifically** — not because we want agent
   memory, but because financial facts *are* temporal facts. Adding a fiscal-period
   qualifier to `Triple` is a small change with a large payoff.

3. **Full rebuild on every ingest.** `_build_graph` re-extracts triples from *every*
   parent block in the book each time anything is added (`graph.py:161`). Add one page to
   a 200-page 10-K and we pay ~200 LLM extraction calls again. Mitigated by using
   `gemini-3.1-flash-lite`, but it makes incremental ingestion economically silly. This is
   exactly the "computationally expensive indexing pipeline" weakness the article pins on
   Microsoft GraphRAG — **we inherited it by building the same design.** Graphiti's
   incremental ingestion is the counter-example; LightRAG's cheap indexing is another.

Two lesser gaps, noted but not urgent:

4. **Flat communities.** `greedy_modularity_communities` gives one level; MS GraphRAG uses
   hierarchical Leiden. Only worth fixing if `global_search` measurably underperforms.
5. **Graph persisted as one JSON blob** per book, fully deserialized into memory on every
   query (`save`/`load`). Fine at current book sizes; a scaling cliff later.

### Why no dependency

Every tool here is either the thing we already built (MS GraphRAG), the wrong runtime
(TypeGraph = TypeScript), the wrong infrastructure (Graphiti = Neo4j — adding a second
database to a product we intend to sell as a single-Postgres deploy is a hard no), or
solving a problem we don't have (Cognee = swappable backends). The ideas are portable;
the code isn't.

### Actions taken

> 🚧 **Gated.** Project memory `graphrag-deferred-learn-then-build` says the graph
> pipeline is not to be extended without a `/learn` pass first. Everything below is a
> findings list, **not** a licence to start implementing.

- [ ] Fix the stale "graph building may be incomplete" line in CLAUDE.md
- [ ] **Entity resolution** — embedding-based alias merging to replace bare `_norm()` (highest value)
- [ ] **Temporal triples** — add a fiscal-period qualifier to `Triple`; financial facts are time-bound
- [ ] **Incremental graph build** — only extract from parent blocks new since the last build
- [ ] *(later)* Hierarchical communities; stop storing the graph as a single JSON blob

---

<!--
Template for the next entry — copy this block.

## <Tool name>

- **Repo:** · **PyPI/npm:**
- **License:** (verify from the LICENSE file — secondary sources get this wrong)
- **Evaluated:** YYYY-MM-DD
- **Verdict:** adopt | partial | defer | reject

### What it is
### What it offers (full inventory)
### How it maps onto Atlas today
### What it would fix (real weaknesses it addresses, with severity)
### What it would cost (deps, lock-in, surface area we'd actually use)
### Verdict + revisit trigger — what would have to be true for this to become a yes
### Actions taken
-->
