# Project status

**Portfolio-complete.** This describes implemented and tested portfolio scope, not a deployed production service.

## Completed phases

1. Modular FastAPI backend, settings, health endpoint, tests, and Docker foundation.
2. Validated PDF/TXT upload, page-preserving parsing, cleaning, and overlapping chunking.
3. Local SentenceTransformer embeddings and Qdrant ingestion/search.
4. Grounded generation through an external provider, bounded context, and citation validation.
5. Separate retrieval and generation evaluation with deterministic checks and optional judging.
6. BM25, RRF fusion, optional token chunking, cross-encoder reranking, and retrieval comparison.
7. Real annual-report benchmark ingestion, inventory, reviewed labels, comparisons, and failure analysis.
8. React portfolio interface with upload, session scoping, answers, citations, and retrieval exploration.
9. Observability and deployment readiness: request IDs, safe logs, readiness, CORS, Qdrant API keys, and container startup configuration.
10. Portfolio documentation, interview material, resume copy, and repository ignore review.

These are completed work areas, not a claim that additional production features were added during polish.

## Measured benchmark

Thirty assistant-reviewed development questions cover seven annual reports and 11,769 chunks; 26 questions are answerable and four are unanswerable. Hybrid + rerank achieved Recall@5 0.7174, MRR@10 0.6936, NDCG@5 0.6022, and P50 retrieval latency 483.71 ms. Dense achieved Recall@5 0.3369 and P50 19.23 ms. See the [complete comparison](../README.md#real-benchmark) for all four strategies.

The quality-first recommendation is hybrid_rerank, while the setting default remains dense. The labels are not an independent holdout, and retrieval metrics do not establish generated-answer correctness or abstention quality.

## Deployment readiness

Static frontend configuration, a single-worker non-root backend container, CPU dependency lock, external Qdrant support, provider configuration, and operational documentation are implemented. The production frontend build succeeds with an explicit API base URL. Docker is unavailable locally, so container execution and cloud deployment remain unverified; see the [deployment checklist](deployment-checklist.md).

## Verification

- Backend: 265 passed, 3 skipped.
- Frontend: 35 passed, 1 skipped.
- Production frontend build: passed with an explicit example API origin.
- Skipped optional integration checks do not validate external services.
- Only documentation and ignore rules changed during portfolio polish.
- Offline verification on 2026-09-12 used Python 3.13; backend emitted two dependency deprecation warnings, and the frontend build emitted non-blocking Zod comment-annotation warnings.
- Obvious-secret pattern scan inspected 136 text files: six candidates were reviewed as two documentation placeholders, three invalid-URL test fixtures, and one variable reference; no obvious live credentials were found. Binary files, generated dependencies, model caches, and benchmark corpus/results were excluded. This is not a comprehensive secret audit.
- All checked local documentation links resolved. Twelve generated/private path ignore checks and seven publishable-file exceptions passed in a disposable Git repository; no Git repository was initialized here.

## Limitations and intentional exclusions

There is no authentication, multi-user authorization, persisted original PDF store, OCR, distributed lexical cache, or verified production traffic. CPU inference and lazy model loading affect latency; the lexical cache requires one application worker and controlled writers. Benchmark review is assistant-led, and citation provenance does not prove entailment.

Agents, conversation memory, Redis, PostgreSQL, new retrieval algorithms, and additional models are intentionally outside this polish scope. Scaling and multi-user proposals in interview notes are future designs only.

## Repository hygiene

Local environments, Qdrant data, model caches, dependencies, generated output, and OS/tool artifacts are ignored. Benchmark result files remain on disk; ignoring them does not delete them. This checkout has no Git metadata, so ignore rules and working files can be checked, but committed files and history cannot be audited. No license was added because ownership and licensing terms have not been selected by the owner.
