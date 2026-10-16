# Architecture

See the [root diagram](../README.md#architecture) for the complete flow.

## 1. Ingestion pipeline

FastAPI validates PDF/TXT MIME type and extension, checks size, and reads bounded blocks before sending processing to a thread pool. The production service parses pages, chunks text, embeds batches, and writes Qdrant payloads. It returns document ID, page count, and chunk counts; original files are not retained. Document IDs derive from filename plus a content hash, with deterministic per-document chunk IDs. Failed batched ingestion is not a transactional rollback of all previous writes.

## 2. Chunking

Character chunking defaults to 1,000 characters with 150 overlap and prefers paragraph, newline, then word boundaries before hard splitting. The optional tokenizer-aware mode uses 200 tokens with 32 overlap and checks the model token limit. Both keep chunks within source pages, preserving filename, page number, and chunk index. This favors citations over joining context across page boundaries; changing chunk configuration requires controlled reingestion and benchmark revalidation.

## 3. Embedding lifecycle

The application owns a lazily loaded CPU SentenceTransformer, defaulting to all-MiniLM-L6-v2. Batches default to 32 texts, embeddings are normalized, and dimensions and finite values are validated. Lazy loading keeps liveness inexpensive but moves model load cost into the first operation. The model cache persists separately from Qdrant; an offline deployment must prefetch all required models.

## 4. Qdrant design

Qdrant stores cosine vectors alongside source text and citation metadata. Collection dimensions are checked rather than silently deleting incompatible data. Ingestion upserts deterministic chunk IDs and removes stale chunks after successful batches. Server mode supports external Qdrant and an optional HTTPS API key; embedded local storage is for isolated single-process use.

## 5. Dense retrieval

The query uses the same embedder as documents, then searches Qdrant with an optional document filter. Dense captures semantic similarity and had the lowest measured P50 retrieval latency, 19.23 ms. It is still the configuration default. Similar meaning alone does not guarantee exact numerical or lexical evidence coverage.

## 6. BM25

A process-local lexical index is built from stored chunk text and cached for subsequent queries. Ingestion invalidates this cache; an application-owned lock coordinates local indexing and retrieval. BM25 complements semantic retrieval for corpus-specific words and numbers. Other processes or external writers cannot automatically invalidate this cache, which motivates the current single-worker deployment.

## 7. RRF fusion

Hybrid retrieval merges dense and BM25 rankings using reciprocal rank contributions with a configurable constant, default 60. It does not add raw similarity and lexical scores. The candidate count controls the recall/cost tradeoff before selecting final results. A good fused rank does not guarantee complete evidence across multiple documents.

## 8. Cross encoder

The configured ms-marco-MiniLM-L6-v2 cross encoder scores query-passage pairs from the fused candidate pool, default 20 candidates. It can move useful candidates earlier but cannot retrieve missing candidates. It improved Recall@5 to 0.7174 in the development benchmark while increasing P50 to 483.71 ms. Rare identifier and cross-document regressions remain documented rather than hidden by the aggregate improvement.

## 9. RAG generation

The ask service reuses retrieval, assembles a bounded context, and invokes an async OpenAI-compatible HTTP adapter. System instructions are separate from JSON question/source data; source instructions are explicitly untrusted. Context defaults to 12,000 characters and output to 800 tokens, so not all retrieved text necessarily reaches the model. Safe errors cover missing configuration and provider failures without exposing upstream bodies or secrets.

## 10. Citation mapping

Source markers map to application-owned chunk records, including document ID, chunk ID, filename, page, and chunk index. Unknown markers are rejected instead of becoming invented source references. The React view maps valid markers to source cards without manufacturing PDF URLs. Marker validity proves which supplied source was referenced, not that its text entails the answer.

## 11. Evaluation

Retrieval metrics and generation checks are separate from request handling. The real benchmark uses an isolated Qdrant store and manually reviewed labels rather than treating retrieved hits as truth. Recall, precision, MRR, NDCG, and latency expose different failure modes; optional generation judging requires explicit configuration. The 30-question assistant-reviewed development set is not independent, and partial/overlapping evidence labels do not prove answer completeness.

## 12. Frontend/backend boundary

React owns session-only uploaded-document state, optional document selection, upload/ask loading states, citations, and search debugging. FastAPI owns validation, ingestion, retrieval, prompt construction, provider calls, and source metadata. The frontend uses VITE_API_BASE_URL and does not receive provider secrets or change retrieval strategy. Cancellation and friendly errors prevent stale responses from replacing the current request state.

## 13. Deployment

The topology is a static frontend, one FastAPI worker, Qdrant storage, and an external LLM provider. The non-root backend container has a CPU dependency lock and configurable PORT; Compose defines persistent model and Qdrant volumes. Health checks are cheap liveness checks, while readiness checks collection availability without inference or provider calls. Exact-origin CORS, request IDs, and structured logs improve operations; neither Docker runtime nor a cloud deployment has been verified locally.

## 14. Tradeoffs

Explicit modules keep behavior inspectable without orchestration frameworks. CPU inference and bounded reranking simplify deployment but impose latency and cold-start costs. Page-local chunks improve citation precision while fragmenting some compound evidence, and process-local lexical state limits scaling. Authentication, OCR, distributed cache coordination, and large-scale indexing are future design topics, not implemented capabilities.
