export const BUSINESS_POINTS = [
  {
    title: "Autonomous document reasoning",
    body: "Atlas doesn't just retrieve — it reasons. The agentic loop plans, retrieves, reflects, and iterates until it has enough context to answer with confidence.",
  },
  {
    title: "Live web search for current trends",
    body: "When documents aren't enough, Atlas reaches out to the web in real time — pulling in the latest market news, analyst sentiment, and macro trends to enrich its answers.",
  },
  {
    title: "Multi-step financial research",
    body: "Ask compound questions across multiple filings. Atlas breaks them down, runs sub-queries in parallel, and synthesises a single coherent answer.",
  },
  {
    title: "Self-correcting retrieval",
    body: "Using CRAG, Atlas evaluates its own retrieved context and re-queries when evidence is weak — cutting hallucinations before they reach you.",
  },
  {
    title: "Knowledge graph exploration",
    body: "GraphRAG surfaces entity relationships hidden in unstructured text — connecting companies, people, events, and financials across documents.",
  },
  {
    title: "Grounded, cited responses",
    body: "Every claim is grounded in source passages. Atlas won't invent facts — if it isn't in the document, it says so.",
  },
  {
    title: "Continuous quality evaluation",
    body: "An LLM-as-a-Judge pipeline scores every response for faithfulness, relevance, and completeness, keeping answer quality measurable and improvable.",
  },
  
];

export const STACK = [
  {
    layer: "Frontend",
    items: [
      { name: "Next.js 16", note: "App Router, SSR" },
      { name: "React 19", note: "Server & Client components" },
      { name: "TypeScript", note: "End-to-end type safety" },
      { name: "Tailwind CSS 4", note: "Utility-first styling" },
    ],
  },
  {
    layer: "Backend",
    items: [
      { name: "FastAPI", note: "Python async API" },
      { name: "pgvector", note: "Postgres vector store" },
      { name: "Gemini", note: "LLM inference & generation" },
      { name: "ReAct Agent", note: "Custom-built reasoning loop" },
      { name: "Langfuse", note: "LLM observability & tracing" },
      { name: "SSE streaming", note: "Real-time token delivery" },
    ],
  },
];

export const AI_TECHNIQUES = [
  {
    title: "GraphRAG",
    body: "Builds a knowledge graph from documents to surface entity relationships and answer questions that flat vector search misses.",
  },
  {
    title: "Agentic RAG",
    body: "A ReAct-based reasoning loop that plans, retrieves, reflects, and re-queries until the answer is sufficiently grounded.",
  },
  {
    title: "Hybrid Search",
    body: "Combines dense vector similarity with BM25 keyword search, then fuses scores — maximising recall for both semantic and exact-match queries.",
  },
  // {
  //   title: "Reranking",
  //   body: "A cross-encoder reranker re-scores retrieved chunks for query relevance before they reach the LLM, cutting noise from the context window.",
  // },
  // {
  //   title: "Grounding",
  //   body: "Every generated claim is anchored to a source passage. Responses that lack evidence are withheld rather than fabricated.",
  // },
  // {
  //   title: "CRAG",
  //   body: "Corrective RAG evaluates retrieval quality mid-loop and triggers corrective re-retrieval when confidence in the evidence is low.",
  // },
  {
    title: "LLM-as-a-Judge",
    body: "A secondary LLM scores each response for faithfulness, relevance, and completeness — making evaluation systematic and reproducible.",
  },
];
