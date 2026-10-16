# Interview notes

Answers describe the current implementation; scale, multi-user, and OCR proposals are explicitly future work.

## Explain DeepDocs AI end to end.

A PDF or TXT upload is validated, parsed into pages, chunked, embedded locally, and indexed in Qdrant with source metadata. A question runs the configured retriever, then the ask service builds bounded context for an external LLM. The response validates citation markers and returns source records for the React interface. Separate evaluation tools measure retrieval before we attribute failures to generation.

## Why did you build RAG without LangChain?

I wanted the boundaries between retrieval, prompt building, generation, and citation validation to be visible in code. Small modules make it easier to inject test doubles and explain failure handling. This is a learning and inspectability choice, not a claim that orchestration frameworks are inherently unsuitable.

## Why FastAPI?

FastAPI provides typed request validation, dependency injection, and generated API documentation for the existing upload, search, and ask endpoints. The async provider adapter can await network I/O, while document processing runs in a thread pool. CPU inference still consumes resources; async endpoints do not make that work free.

## Why Qdrant?

Qdrant keeps dense vectors together with the text and metadata needed for citations and document filtering. The project supports both isolated embedded stores for local evaluation and an external server for deployment. Dimension checks prevent silently mixing incompatible embeddings in one collection.

## What are embeddings?

Embeddings represent text as vectors so related passages can be found by similarity rather than exact wording. DeepDocs embeds document chunks and questions with the same local SentenceTransformer. They provide candidates, not factual answers or a guarantee that numbers match.

## Why MiniLM?

The configured all-MiniLM-L6-v2 model provides compact 384-dimensional embeddings that are practical for a CPU portfolio application. Local embedding avoids sending document text to an embedding API. The benchmark evaluates this concrete configuration; it does not establish MiniLM as the best model for every corpus.

## Why cosine similarity?

The collection uses cosine similarity and the embedder returns normalized vectors. This gives the application a consistent comparison between question and chunk representations. Collection dimension validation guards against an incompatible model change, though changing models still requires deliberate reindexing.

## What is BM25?

BM25 is the lexical path: it ranks stored chunks using query-term matches, term frequency, rarity, and document length. In DeepDocs its index is cached within the application process and invalidated after ingestion. It helps with report vocabulary and exact textual evidence that semantic similarity can miss.

## Why hybrid retrieval?

Dense and lexical retrieval make different mistakes on annual reports. Hybrid keeps candidates from both rankings, which can improve coverage before final selection. The measured hybrid Recall@5 was 0.5891, slightly below BM25 alone, so fusion is not automatically better on every metric.

## Why RRF?

RRF combines the positions assigned by each retriever rather than their raw scores. That suits the project because BM25 and cosine scores have different scales. Its constant and candidate limits are explicit settings, making the fusion easy to inspect and benchmark.

## Why not add dense and BM25 scores directly?

A BM25 score and a cosine similarity are not calibrated to mean the same thing. Adding them can let one score scale dominate regardless of evidence quality. DeepDocs uses rank fusion to avoid that assumption, while accepting that rank fusion discards score magnitude.

## What is a cross encoder?

The cross encoder reads a question and passage together and assigns a relevance score. DeepDocs applies it to the fused candidates instead of storing its outputs as document embeddings. Joint scoring improved early evidence placement here but costs more CPU than vector lookup.

## Why not rerank every chunk?

Scoring every query against all 11,769 chunks would add substantial work per request. DeepDocs instead reranks a bounded candidate set, default 20, produced by retrieval. The tradeoff is that evidence missing from those candidates cannot be recovered by reranking.

## Why did dense perform poorly on exact identifiers?

That premise needs qualification: dense did not universally fail exact identifiers in this benchmark, and some exact-keyword cases had first-relevant rank one. Dense can favor semantic context over exact strings, but the observed rare-identifier regression also involved reranking. I would inspect each candidate pool rather than infer a blanket failure from the aggregate Recall@5.

## Why did BM25 outperform dense overall on this corpus?

Annual reports contain specific names, numerical disclosures, and repeated domain vocabulary that make lexical matching useful. BM25 achieved Recall@5 of 0.6010 compared with dense at 0.3369 on these reviewed questions. That is evidence about this corpus and question set, not a general ranking of lexical and semantic methods.

## Why did reranking improve Recall@5?

Reranking promoted relevant evidence already present in the fused candidate set into the first five positions. Hybrid + rerank reached 0.7174 Recall@5, compared with hybrid at 0.5891. Its P50 latency increased to 483.71 ms, so the recommendation explicitly prioritizes quality over speed.

## Why did reranking hurt some rare-identifier/cross-document cases?

A pairwise relevance score does not directly enforce exact identifier retention or coverage across multiple documents. In reviewed failures, generic login instructions could displace identifier evidence, and one company could dominate a comparison question. The existing system records those failures; it does not implement an additional diversity or identifier algorithm.

## What is Recall@K?

Recall@K is the fraction of labeled relevant chunks found in the first K results for an answerable question. It helps diagnose evidence omitted before generation. Here the labels can contain partial or overlapping evidence, so Recall@5 does not equal the probability of a complete correct answer.

## What is MRR?

MRR averages the reciprocal rank of the first relevant result within the cutoff. A relevant result at rank one contributes one, while rank two contributes one half. DeepDocs reports MRR@10 because early evidence is useful, but this metric does not measure whether all parts of a compound question are covered.

## What is NDCG?

NDCG rewards relevant chunks more when they appear earlier, then normalizes against an ideal ranking. Unlike MRR, it can account for multiple relevant results in the returned list. DeepDocs reports NDCG@5 alongside recall so evidence ordering and coverage are both visible.

## Why evaluate retrieval separately from generation?

An LLM cannot reliably answer from evidence that the retriever never supplied. Separate retrieval evaluation identifies candidate and ranking failures without introducing provider variability or generation cost. Deterministic answer checks and an optional judge then assess a different stage rather than masking retrieval problems.

## What is prompt injection in RAG?

A source document can contain instructions that try to redirect the model away from the user question. DeepDocs treats retrieved text as untrusted source data and separates it from system instructions in the prompt. Those mitigations and citation checks reduce particular risks but do not prove resistance to every attack.

## How do citations work?

The context builder associates supplied sources with markers and application-owned metadata. The ask service validates returned markers and maps them back to chunk ID, document ID, filename, page, and chunk index. The frontend highlights source cards without inventing links to PDFs that the backend does not persist.

## Why do citations not prove factual entailment?

A valid marker establishes that the answer referenced a source supplied by the application. It does not establish that the cited text supports the exact claim, currency, date, or comparison. DeepDocs therefore distinguishes citation provenance from answer correctness in its documentation and evaluation.

## What causes embedding/model cold start?

The first real operation may need to download model files and load model weights into CPU memory. Both the embedder and reranker are lazy resources, so a successful liveness check does not imply warmed inference. Persistent model caches avoid repeated downloads, but loading and first inference still take time.

## Why one FastAPI worker?

BM25 is cached in process memory, and local ingestion invalidates that process’s cache. Multiple workers could keep stale lexical views after another worker writes data, and would duplicate model memory. The documented deployment uses one worker until cross-process index coordination is designed and tested.

## What would you change for 10 million chunks?

That is future work, not a tested scale claim. I would first measure storage, memory, query latency, and ingestion throughput, then design distributed lexical indexing and asynchronous ingestion with backpressure. Qdrant capacity and partitioning would need load testing, while model serving and cache coordination would become explicit services.

## How would you make it multi-user?

The current document filter is not authorization. A future design needs authenticated identity, tenant ownership stored with documents, and mandatory authorization filters on ingestion and every search/ask path. I would add isolation tests before exposing the application to mutually untrusted users.

## How would you add OCR?

The current parser rejects PDFs with no extractable text rather than pretending they are processed successfully. A future OCR stage should detect image-only pages and preserve original page numbers in its output. I would evaluate extraction quality and resource limits before mixing OCR text into the same ingestion pipeline.

## How would you reduce reranking latency?

I would profile cold and warm requests separately, then benchmark smaller candidate counts and batching settings against the same evidence labels. Fewer candidates may lose recall, so a faster timing alone is insufficient. GPU serving or another deployment layout could be investigated later; neither is an implemented performance claim here.

## How would you improve this system next?

I would begin with independent human review and a held-out evaluation set to check whether the current recommendation generalizes. The documented coverage, identifier, and table failures would guide focused experiments rather than adding algorithms indiscriminately. Authentication, OCR, and verified deployment remain separate future scope decisions, not completed features.
