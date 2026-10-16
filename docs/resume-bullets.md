# Resume and interview material

## Three resume bullets

- Built a production-style RAG document assistant with FastAPI, React, Sentence Transformers, Qdrant, BM25, RRF, and cross-encoder reranking, evaluated over 11,769 chunks from seven annual reports.
- Compared four retrieval strategies on a 30-question assistant-reviewed development benchmark; hybrid + rerank improved Recall@5 from 0.3369 to 0.7174 (+38.05 percentage points) versus dense, with P50 retrieval latency of 483.71 ms versus 19.23 ms.
- Implemented page-level citation mapping, separate retrieval and generation evaluation, request IDs, readiness checks, and deployment configuration; verified 265 backend and 35 frontend tests passing and a successful production frontend build.

## Compact project description

DeepDocs AI: a FastAPI/React RAG research assistant with local embeddings, hybrid retrieval, cross-encoder reranking, page-level citations, and a reproducible development evaluation workflow.

## LinkedIn project description

Built DeepDocs AI from explicit ingestion, retrieval, and generation modules without LangChain or LlamaIndex. The React interface supports document upload, scoped questions, citations, and a retrieval explorer. A 30-question assistant-reviewed development benchmark over 11,769 chunks from seven annual reports compared dense, BM25, hybrid RRF, and hybrid reranking; the latter achieved 0.7174 Recall@5 with 483.71 ms median retrieval latency. The portfolio includes failure analysis, automated tests, observability, and deployment configuration; it does not claim production traffic, independent benchmark validation, or a verified cloud deployment.

## 30-second interview pitch

DeepDocs AI is a document research assistant I built with FastAPI and React without LangChain. It ingests PDFs and text, retrieves evidence using semantic and lexical search, and generates answers with page-level citations. On a 30-question assistant-reviewed benchmark over seven annual reports, hybrid reranking raised Recall@5 from 0.3369 to 0.7174, with a clear latency cost. I also documented retrieval failures and deployment limitations rather than treating fluent answers as proof of correctness.

## 2-minute interview pitch

I built DeepDocs AI to understand where document question answering succeeds and fails beyond simply calling an LLM. It is a FastAPI backend with a React interface, built without LangChain or LlamaIndex so the ingestion, retrieval, context, and citation boundaries remain visible.

Uploads are validated and parsed page by page, then chunked with overlap, embedded locally with Sentence Transformers, and stored in Qdrant with source metadata. Queries can use dense retrieval, BM25, hybrid RRF, or hybrid with cross-encoder reranking. The ask service sends bounded evidence to an external LLM and validates returned citation markers against application-owned source records. A valid citation establishes provenance, but I do not claim it proves factual entailment.

I compared the four strategies on 30 assistant-reviewed development questions over 11,769 chunks from seven annual reports. Hybrid reranking reached Recall@5 of 0.7174 versus 0.3369 for dense, an improvement of 38.05 percentage points. The median retrieval latency rose from 19.23 to 483.71 milliseconds, so I recommend it when quality matters most rather than calling it universally better. Dense remains the configuration default.

Failure analysis was just as useful as the aggregate scores: missing first-stage candidates cannot be recovered by reranking, comparison questions can lose coverage of one document, and exact identifiers or table values can be displaced. I kept retrieval evaluation separate from generation to identify those causes.

The project also includes request IDs, structured logs, readiness checks, Docker configuration, and passing backend and frontend suites. It is portfolio-complete, with explicit limitations: no authentication, no OCR, a single-process lexical cache, and no locally verified Docker runtime or cloud deployment. The next evidence step would be independent review and held-out evaluation, not an unsupported claim of production scale.
