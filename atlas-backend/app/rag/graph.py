"""GraphRAG — a per-book knowledge graph over the ingested documents.

Two halves, mirroring the rest of the system:

  * **build** (ingestion side): for each parent block, extract ``(subject,
    relation, object)`` triples with Gemini, stitch them into a networkx
    ``MultiDiGraph`` (entities = nodes, relations = directed edges), detect
    communities, summarize each with Gemini and embed the summaries. The graph
    is serialized and upserted into the ``graphs`` table, keyed by ``book_id``.
    Built once per (re)ingestion — never rebuilt at query time.

  * **search** (query side): ``GraphIndex.load(book_id)`` pulls the graph back
    and the agent's ``graph_search`` tool traverses it. ``local_search`` matches
    the question's entities to nodes and walks a few hops out to gather the
    backing passages plus the relations connecting them; ``global_search``
    embeds the question and returns the best-matching community summaries for
    "across the whole book" questions.

The bridge from graph back to real text is provenance: every node records the
``parent_id``s of the blocks its relations came from, and
``HybridStore.fetch_parents`` swaps those ids for the full ``parent_text`` —
so a graph answer can always be grounded in (and cited from) actual passages.

In-memory networkx persisted as JSON is deliberately simple; a production graph
store (Neo4j/Cypher) would replace the persistence + traversal internals here
without changing the tool-facing ``local_search`` / ``global_search`` surface.
"""

from __future__ import annotations

import json

import logfire
import networkx as nx
import numpy as np
from langfuse import observe
from pydantic import BaseModel, Field

from app.llm.embedding import TASK_DOCUMENT, GeminiEmbedding, get_embedder
from app.llm.gemini import Gemini, get_gemini
from app.rag.store import HybridStore
from app.schema.documents import Chunk
from app.schema.llm_settings import ModelSettings, Settings, get_settings


# --------------------------------------------------------------- LLM schemas
class Triple(BaseModel):
    """A single extracted relation: ``subject -relation-> object``."""

    subject: str = Field(description="The head entity (a company, person, metric, etc.).")
    relation: str = Field(description="The relationship, as a short verb phrase.")
    object: str = Field(description="The tail entity the subject relates to.")


class Extraction(BaseModel):
    """The set of triples found in one parent block."""

    triples: list[Triple] = Field(default_factory=list)


class Entities(BaseModel):
    """The entities a question is about — the entry points for local search."""

    entities: list[str] = Field(default_factory=list)


_EXTRACT_PROMPT = (
    "You are building a knowledge graph from a financial document. From the text "
    "below, extract the factual relationships as (subject, relation, object) "
    "triples. Focus on concrete financial entities and facts: companies, people, "
    "subsidiaries, products, metrics, amounts, dates, regulators, and how they "
    "relate (owns, acquired, reported, increased, is_subsidiary_of, led_by, "
    "filed_with, etc.). Use short canonical entity names (no trailing punctuation) "
    "and lowercase snake_case relations. Skip vague or speculative statements. "
    "If there are no clear relationships, return an empty list.\n\nTEXT:\n{text}"
)

_ENTITY_PROMPT = (
    "Extract the key entities (companies, people, products, metrics, places) that "
    "this question is asking about. Return only the entity names, canonicalized.\n\n"
    "QUESTION: {query}"
)

_SUMMARY_PROMPT = (
    "Below are the relationships in one cluster of a financial knowledge graph. "
    "Write a concise 2-4 sentence summary of what this cluster is about — the main "
    "entities and the theme connecting them. This summary will be used to answer "
    "high-level questions about the document.\n\nRELATIONSHIPS:\n{relations}"
)


class GraphIndex:
    """Build, persist, load, and search a per-book knowledge graph."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        store: HybridStore | None = None,
        gemini: Gemini | None = None,
        embedder: GeminiEmbedding | None = None,
        book_id: str = "",
        title: str = "",
    ) -> None:
        self.s = settings or get_settings()
        self._store = store
        self._gemini = gemini
        self._embedder = embedder
        self.book_id = book_id
        self.title = title
        self.g: nx.MultiDiGraph = nx.MultiDiGraph()
        # Detected communities: each {"summary": str, "embedding": list[float]}.
        self.communities: list[dict] = []

    # --------------------------------------------------------- lazy singletons
    @property
    def store(self) -> HybridStore:
        if self._store is None:
            self._store = HybridStore(self.s)
        return self._store

    @property
    def gemini(self) -> Gemini:
        if self._gemini is None:
            self._gemini = get_gemini()
        return self._gemini

    @property
    def embedder(self) -> GeminiEmbedding:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    # ====================================================== BUILD (ingestion)
    @observe(name="graph.build")
    def build(self, chunks: list[Chunk]) -> "GraphIndex":
        """Build the graph from a book's chunks, then detect communities.

        Triples are extracted **once per parent block** (not per child chunk):
        cheaper, and each block has the full context a child window lacks. The
        ``book_id``/``title`` are taken from the chunks if not already set.
        """
        if not chunks:
            return self

        if not self.book_id:
            self.book_id = chunks[0].book_id
        if not self.title:
            self.title = chunks[0].title

        # Dedupe to one block per parent — many child chunks share a parent.
        parents: dict[str, str] = {}
        for c in chunks:
            text = (c.parent_text or c.text).strip()
            if text and c.parent_id not in parents:
                parents[c.parent_id] = text

        with logfire.span(
            "graph.build", book_id=self.book_id, n_parents=len(parents)
        ) as span:
            for parent_id, text in parents.items():
                if len(text) < self.s.graph_min_block_chars:
                    continue
                for t in self._extract(text):
                    self._add_triple(t, parent_id)
            span.set_attribute("n_nodes", self.g.number_of_nodes())
            span.set_attribute("n_edges", self.g.number_of_edges())
            logfire.info(
                "graph built: {n} nodes, {e} edges",
                n=self.g.number_of_nodes(),
                e=self.g.number_of_edges(),
            )
            self._detect_communities()
        return self

    def _extract(self, text: str) -> list[Triple]:
        """Pull triples from one parent block via constrained decoding."""
        try:
            result = self.gemini.generate_structured(
                _EXTRACT_PROMPT.format(text=text),
                Extraction,
                ModelSettings(model=self.s.graph_model, temperature=0.0),
            )
        except Exception as exc:  # noqa: BLE001 - one bad block must not sink the build
            logfire.warn("triple extraction failed for a block: {err}", err=str(exc))
            return []
        return result.triples

    def _add_triple(self, t: Triple, parent_id: str) -> None:
        """Stitch one triple into the graph, accumulating provenance.

        ``add_node`` *overwrites* a node's attribute dict, so we merge by hand:
        the ``chunks`` set must accumulate every parent block an entity appears
        in (that set is the provenance bridge back to real passages). Nodes are
        keyed by a normalized name so the same entity from different blocks
        collapses to one node.
        """
        subj = _norm(t.subject)
        obj = _norm(t.object)
        rel = t.relation.strip()
        if not subj or not obj or not rel:
            return
        self._touch_node(subj, t.subject, parent_id)
        self._touch_node(obj, t.object, parent_id)
        # MultiDiGraph: keep direction (subj->obj) and allow several relations
        # between the same pair of entities.
        self.g.add_edge(subj, obj, relation=rel, parent_id=parent_id)

    def _touch_node(self, key: str, label: str, parent_id: str) -> None:
        if self.g.has_node(key):
            self.g.nodes[key]["chunks"].add(parent_id)
        else:
            self.g.add_node(key, label=label, chunks={parent_id})

    @observe(name="graph.detect_communities")
    def _detect_communities(self) -> None:
        """Cluster the (undirected) graph and summarize each cluster.

        Community detection needs an undirected view — modularity is about how
        densely groups connect, not edge direction. Each big-enough community is
        summarized by Gemini and the summary embedded, so ``global_search`` can
        match a question to whole themes rather than single entities.
        """
        self.communities = []
        if self.g.number_of_edges() == 0:
            return
        undirected = self.g.to_undirected()
        try:
            groups = nx.community.greedy_modularity_communities(undirected)
        except Exception as exc:  # noqa: BLE001 - graph may be too sparse to cluster
            logfire.warn("community detection failed: {err}", err=str(exc))
            return

        summaries: list[str] = []
        for group in groups:
            if len(group) < self.s.graph_min_community:
                continue
            relations = self._relations_within(set(group))
            if not relations:
                continue
            summary = self._summarize(relations)
            if summary:
                summaries.append(summary)

        if not summaries:
            return
        # Embed all summaries in one batch (document-side task type — they are
        # the "documents" global search matches a query against).
        vecs = self.embedder.embed(summaries, task_type=TASK_DOCUMENT)
        self.communities = [
            {"summary": s, "embedding": vecs[i].tolist()}
            for i, s in enumerate(summaries)
        ]
        logfire.info("detected {n} community summaries", n=len(self.communities))

    def _relations_within(self, nodes: set[str]) -> list[str]:
        """Human-readable ``subject relation object`` lines inside a node set."""
        lines: list[str] = []
        for u, v, data in self.g.edges(data=True):
            if u in nodes and v in nodes:
                su = self.g.nodes[u].get("label", u)
                ov = self.g.nodes[v].get("label", v)
                lines.append(f"{su} {data.get('relation', 'related_to')} {ov}")
        return lines

    def _summarize(self, relations: list[str]) -> str:
        try:
            class _Summary(BaseModel):
                summary: str

            result = self.gemini.generate_structured(
                _SUMMARY_PROMPT.format(relations="\n".join(relations[:60])),
                _Summary,
                ModelSettings(model=self.s.graph_model, temperature=0.2),
            )
            return result.summary.strip()
        except Exception as exc:  # noqa: BLE001
            logfire.warn("community summary failed: {err}", err=str(exc))
            return ""

    # ============================================================ PERSISTENCE
    def save(self) -> None:
        """Upsert the serialized graph + community summaries into ``graphs``."""
        payload = _serialize(self.g)
        conn = self.store._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.s.graph_table}
                    (book_id, title, graph, communities, n_nodes, n_edges, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (book_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    graph = EXCLUDED.graph,
                    communities = EXCLUDED.communities,
                    n_nodes = EXCLUDED.n_nodes,
                    n_edges = EXCLUDED.n_edges,
                    updated_at = now()
                """,
                (
                    self.book_id,
                    self.title,
                    json.dumps(payload),
                    json.dumps(self.communities),
                    self.g.number_of_nodes(),
                    self.g.number_of_edges(),
                ),
            )
        conn.commit()
        logfire.info("saved graph for book {book_id}", book_id=self.book_id)

    @classmethod
    def load(
        cls, book_id: str, *, settings: Settings | None = None, **kwargs
    ) -> "GraphIndex | None":
        """Load a book's graph from the DB, or ``None`` if it has no graph yet."""
        s = settings or get_settings()
        idx = cls(s, book_id=book_id, **kwargs)
        conn = idx.store._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT title, graph, communities FROM {s.graph_table} WHERE book_id = %s",
                (book_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        idx.title = row[0] or ""
        idx.g = _deserialize(row[1] if isinstance(row[1], dict) else json.loads(row[1]))
        idx.communities = row[2] if isinstance(row[2], list) else json.loads(row[2])
        return idx

    # ================================================================ SEARCH
    @observe(name="graph.local_search", as_type="retriever")
    def local_search(self, query: str) -> str:
        """Answer an entity-centric question by walking the graph.

        Match the question's entities to nodes, walk ``graph_local_hops`` out to
        collect the surrounding subgraph, then return both the relations in that
        neighbourhood (so the agent sees the structure, not just text) and the
        full backing passages, ranked by graph distance from the matched entities.
        """
        if self.g.number_of_nodes() == 0:
            return "This book has no knowledge graph to search."

        seeds = self._match_nodes(query)
        if not seeds:
            return (
                "No matching entities were found in the knowledge graph for that "
                "query. Try the `retrieve` tool, or rephrase with specific names."
            )

        undirected = self.g.to_undirected()
        # parent_id -> best (smallest) graph distance to any seed entity.
        best_dist: dict[str, int] = {}
        reached: set[str] = set()
        for seed in seeds:
            lengths = nx.single_source_shortest_path_length(
                undirected, seed, cutoff=self.s.graph_local_hops
            )
            for node, dist in lengths.items():
                reached.add(node)
                for pid in self.g.nodes[node].get("chunks", ()):  # parent ids
                    if pid not in best_dist or dist < best_dist[pid]:
                        best_dist[pid] = dist

        relations = self._relations_within(reached)
        ordered_parents = [
            pid for pid, _ in sorted(best_dist.items(), key=lambda kv: kv[1])
        ][: self.s.graph_max_parents]

        passages = self._fetch_passages(ordered_parents)
        return self._format_local(seeds, relations, passages)

    @observe(name="graph.global_search", as_type="retriever")
    def global_search(self, query: str) -> str:
        """Answer a whole-document / thematic question via community summaries.

        Embed the question and rank the pre-computed community summaries by cosine
        similarity (every vector is L2-normalized, so dot product == cosine),
        returning the top few. These are book-wide themes, not single passages —
        the right tool for "what are the main risks across the filing?".
        """
        if not self.communities:
            return (
                "This book has no community summaries to search. Use `local_search` "
                "for specific entities or the `retrieve` tool for passages."
            )
        q = self.embedder.embed_query(query)
        mat = np.asarray([c["embedding"] for c in self.communities], dtype=np.float32)
        scores = mat @ q  # cosine, both sides normalized
        order = np.argsort(-scores)[: self.s.graph_global_top]
        blocks = [
            f"[Theme {rank + 1}] {self.communities[i]['summary']}"
            for rank, i in enumerate(order)
        ]
        return (
            "High-level themes from across this book most relevant to the query:\n\n"
            + "\n\n".join(blocks)
        )

    # ---------------------------------------------------------------- helpers
    def _match_nodes(self, query: str) -> list[str]:
        """Find graph nodes the query is about: exact name match, else substring."""
        try:
            extracted = self.gemini.generate_structured(
                _ENTITY_PROMPT.format(query=query),
                Entities,
                ModelSettings(model=self.s.graph_model, temperature=0.0),
            ).entities
        except Exception:  # noqa: BLE001 - fall back to the raw query words
            extracted = []
        wanted = [_norm(e) for e in extracted if e.strip()] or [_norm(query)]

        nodes = list(self.g.nodes)
        node_set = set(nodes)
        matched: list[str] = []
        seen: set[str] = set()
        for w in wanted:
            if not w:
                continue
            if w in node_set and w not in seen:  # exact
                matched.append(w)
                seen.add(w)
                continue
            for n in nodes:  # substring either direction
                if n in seen:
                    continue
                if w in n or n in w:
                    matched.append(n)
                    seen.add(n)
        return matched

    def _fetch_passages(self, parent_ids: list[str]) -> list[Chunk]:
        if not parent_ids:
            return []
        by_id = self.store.fetch_parents(parent_ids)
        return [by_id[pid] for pid in parent_ids if pid in by_id]

    def _format_local(
        self, seeds: list[str], relations: list[str], passages: list[Chunk]
    ) -> str:
        seed_labels = ", ".join(self.g.nodes[s].get("label", s) for s in seeds)
        parts = [f"Matched entities: {seed_labels}"]
        if relations:
            rels = "\n".join(f"- {r}" for r in relations[:40])
            parts.append(f"Relationships in the neighbourhood:\n{rels}")
        if passages:
            blocks = []
            for c in passages:
                text = (c.parent_text or c.text).strip()
                if not text:
                    continue
                loc = c.metadata.get("loc")
                cite = c.source + (f"#{loc}" if loc else "")
                blocks.append(f"[Source: {cite}]\n{text}")
            if blocks:
                parts.append("Supporting passages:\n\n" + "\n\n---\n\n".join(blocks))
        return "\n\n".join(parts)


def _norm(name: str) -> str:
    """Canonical node key: trimmed, lowercased, inner whitespace collapsed."""
    return " ".join(name.strip().lower().split())


def _serialize(g: nx.MultiDiGraph) -> dict:
    """networkx -> JSON-safe dict. Node ``chunks`` sets become sorted lists."""
    h = g.copy()
    for _, data in h.nodes(data=True):
        if isinstance(data.get("chunks"), set):
            data["chunks"] = sorted(data["chunks"])
    return nx.node_link_data(h, edges="edges")


def _deserialize(payload: dict) -> nx.MultiDiGraph:
    """JSON dict -> networkx. Node ``chunks`` lists become sets again."""
    g = nx.node_link_graph(
        payload, directed=True, multigraph=True, edges="edges"
    )
    for _, data in g.nodes(data=True):
        data["chunks"] = set(data.get("chunks", []))
    return g
