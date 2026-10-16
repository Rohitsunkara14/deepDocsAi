# Real-document retrieval benchmark workspace

This area is infrastructure awaiting real documents and reviewed labels. **No real benchmark has been run and no quality results are claimed.** The original three-document demo remains in `evaluation/examples/` for examples and smoke tests. Its ceiling scores cannot distinguish retrieval strategies or establish real-world quality.

## Files and workflow

```text
benchmark/
├── corpus/
│   └── manifest.example.json
├── datasets/
│   ├── case.schema.json
│   └── questions.template.jsonl
├── results/
│   └── .gitkeep
└── README.md
```

Run commands from `backend/` in the existing virtual environment. Dependencies are unchanged. The benchmark CLI uses the existing production ingestion and Step 6 comparison services, with an isolated local Qdrant collection. It does not introduce a production endpoint or retrieval feature.

1. Supply legally usable real PDF/TXT files under `corpus/`. Copy `manifest.example.json` to `manifest.json` and list every intended file. Manifest IDs are human aliases, **not** generated document UUIDs. Filenames must be unique plain filenames. The CLI reports missing, empty, or oversized files before model initialization; it never downloads documents.
2. Ingest into a **new empty** storage directory. Choose and record chunking settings before ingestion. Changing chunking or document bytes requires a new inventory and reviewed labels.
3. Inspect the complete inventory, which contains actual generated UUIDs, source pages, full extracted chunk text, source file hashes and ingestion settings. Annotation search is an aid, not ground truth.
4. Copy the starter questions, replace all placeholders, review the originals and extracted chunks, then fill UUID labels and reference answers.
5. Validate, then compare the four strategies with repeated warm runs.

```bash
# From backend/, after activating the existing environment:
python -m app.evaluation.benchmark ingest \
  --manifest evaluation/benchmark/corpus/manifest.json \
  --storage evaluation/benchmark/local-store-v1 \
  --inventory evaluation/benchmark/datasets/inventory-v1.json

python -m app.evaluation.annotate \
  --inventory evaluation/benchmark/datasets/inventory-v1.json \
  --question "Replace with your actual benchmark question" \
  --strategy dense --top-k 20

# Repeat annotation with bm25, hybrid and hybrid_rerank to reduce pooling bias.
python -m app.evaluation.benchmark validate \
  --dataset evaluation/benchmark/datasets/questions-v1.jsonl \
  --inventory evaluation/benchmark/datasets/inventory-v1.json

python -m app.evaluation.benchmark compare \
  --dataset evaluation/benchmark/datasets/questions-v1.jsonl \
  --inventory evaluation/benchmark/datasets/inventory-v1.json \
  --runs 5 --warmup 2 \
  --output evaluation/benchmark/results/run-v1
```

The inventory selects storage; `EMBEDDING_MODEL_NAME` must match ingestion. The live chunk payloads must match the inventory exactly before annotation/comparison. Model caches can use existing `HF_HOME`; real embedding/reranker execution needs cached models or explicit network access. Normal tests do not load real models. No LLM or judge calls occur in these comparisons.

Outputs are `comparison.json`, `comparison.md`, `failures.json`, and `failures.md`. Existing output directories are rejected to preserve prior runs. Validation exits 2 on invalid data/setup; comparison exits 1 if measured cases have errors. Partial ingestion failures can leave a partial store: inspect the error and use a fresh store path to retry. Do not run the API against this benchmark store concurrently.

## Authoring and manual review

Select a diverse corpus large enough to place relevant chunks outside top 10: multiple organizations, periods, topics, document lengths and writing styles. Include similar-looking but incorrect entities, years and near-duplicate passages as distractors. Keep source provenance/licensing notes separately; avoid sensitive material in version control. Scanned PDFs without extractable text require a separately prepared text source; this step adds no OCR.

Draft natural questions without copying the exact source sentence for every category. Avoid selecting only questions that the default retriever already answers. Pool candidates from all strategies, read the full originals and inventory beyond top 20, and label **all** relevant chunks, including alternative sufficient evidence. Have a second reviewer check relevance, source page, completeness and reference answers; record rationale/adjudication in notes. Freeze a held-out set before tuning candidate counts or models. Do not tune on the held-out answers.

Expected document UUIDs and expected chunk UUIDs are relevance labels only. They are never passed as implicit search filters. An intentional filter test may include `filter_document_id`, but must also carry the `explicit_filter` tag; every relevant label must remain eligible under that filter. Multi-document cases support any number of relevant documents, each with at least one relevant chunk.

Unanswerable questions should be plausible but verified absent across the full corpus. Set `expects_no_answer=true`, use empty relevance lists and write a reference answer explaining that the corpus does not support the answer. Retrieved candidates alone are **not** evidence of a failed abstention policy: this is retrieval-only evaluation, without an answer generator or relevance threshold.

The prompt-injection category is for manual relevance/corpus review of instruction-bearing distractors. It does not claim to measure LLM instruction compliance or generation safety.

## Question schema and starter templates

The generated `datasets/case.schema.json` documents the structural schema. The CLI additionally checks taxonomy, unique IDs, cross-field rules and inventory membership. JSONL supports:

- `id`, nonblank `question`, `expected_document_ids` and `expected_chunk_ids` UUID lists.
- Nonblank `reference_answer`, explicit boolean `expects_no_answer`.
- Required `category` and `difficulty` (easy, medium, hard), optional `tags` and `notes`.
- Optional explicit `filter_document_id` with its required tag.

Unknown fields, duplicate question/chunk/document labels, malformed UUIDs, missing answers and inconsistent no-answer labels are rejected. Limits: 10 MiB dataset, 5,000 questions, 2,000 question characters, 1,000 labels of each kind per case. Answerable cases need labels; every labeled chunk must belong to a labeled document in the inventory.

The **12 starter rows intentionally fail validation**: their IDs identify templates only, UUID arrays are empty and reference answers are null. No fabricated UUID or answer is supplied. Replace bracketed question phrases and remove the template tag before creating your reviewed dataset.

| Category | Starter question focus |
|---|---|
| semantic_paraphrase | Explain a business change using wording different from the source |
| exact_keyword | Locate an exact domain term |
| rare_identifier | Explain a rare code or identifier |
| numerical | Retrieve a value with its period and unit |
| multi_chunk | Combine evidence from separate sections |
| multi_page | Identify risks across pages |
| cross_document | Compare two organizations on a specific policy |
| distractor_heavy | Resolve the correct entity/year among similar statements |
| unanswerable | Ask a plausible fact verified absent from the corpus |
| prompt_injection | Find supported factual evidence despite instruction distractors |
| table_or_structured_fact | Locate a specific table row/column value |
| temporal_comparison | Compare a metric or policy across periods |

Per-category reporting helps reveal when aggregate scores hide exact-term failures or weak paraphrase retrieval. Categories are mutually exclusive per row; use tags for secondary characteristics.

## Measurement and failure analysis

Each run reuses Step 6 comparison on identical questions and a fixed corpus. It requests top 10, with Recall@1/3/5/10, Precision@5/10, MRR (truncated at 10), binary-relevance NDCG@5/10, error count and scored query count. Recall measures recovered relevant labels; precision divides by K even when fewer results return; MRR measures the first relevant rank; NDCG rewards relevant items appearing early.

No-answer cases are excluded from positive retrieval metrics. Failed retrieval cases have no score and are counted separately: compare error counts before interpreting successful-case averages. Incomplete human labels can incorrectly penalize genuinely relevant results.

Use 1–20 runs and 0–10 warmup queries per strategy per run. Warmup repeats the first labeled question; it exercises that path but cannot guarantee every runtime path is warm. Warmup calls are excluded from metrics and recorded failures remain visible in raw runs. Strategies run sequentially in a fixed order and share model caches. For rigorous performance work, also control machine load, repeat separate sessions and assess order effects.

Latency is pooled across measured query executions and reports mean/P50/P95 for total retrieval and its stages. Warmup/model loading is generally excluded, except initialization that warmup failed to exercise. Hybrid includes its branches and fusion; reranking is a separate stage. Nested timings must not be added twice.

Quality is reported per run plus aggregate distributions; identical rankings should yield identical quality. Repeated executions are **not additional independent labeled questions**. Report fields distinguish unique questions from scored executions; category counts also count executions. Ranking identity is checked across runs. Quality-variation summaries are dimensionless, while latency variation is in milliseconds. These summaries are descriptive, not confidence intervals or significance tests.

Failure artifacts show question/category, expected IDs, retrieved IDs, document/page, rank and score for every weak/error/review case. They distinguish missing from **top 10**, below top 5, and non-labeled documents in top 5. They flag category-specific weak exact-term/paraphrase cases without claiming to know the cause. Near-duplicate distractors are only review candidates based on character-sequence similarity >= 0.85 against a relevant chunk. Missing from top 10 does not mean absent from the entire candidate pool or corpus. Non-labeled documents may reveal incomplete annotation rather than an actual wrong answer.

Do not promote hybrid or reranking because it sounds advanced. Compare meaningful quality differences, per-category failures and latency under reviewed labels before changing the production default. Until documents and labels are supplied, no real benchmark comparison can be made.

## Real annual-report ingestion

The ingestion CLI accepts an explicit collection, saved in the inventory and reused by
annotation/comparison. For this corpus use storage evaluation/.qdrant-benchmark and
collection deepdocs_real_benchmark. Use --collection deepdocs_real_benchmark when ingesting.
This run uses MAX_UPLOAD_SIZE_MB=64 only in its process environment to accommodate the
uploaded reports; production defaults and chunking/embedding settings remain unchanged.

Successful documents include page/chunk/indexed counts in the inventory and console output.
Document processing errors are reported individually and remaining files are attempted.
The inventory includes a failures list and manifest aliases on chunks. If indexing failed
partway, the complete inventory can include partially indexed chunks from that failed document;
review failures before treating the corpus as complete. No relevance labels are generated.
