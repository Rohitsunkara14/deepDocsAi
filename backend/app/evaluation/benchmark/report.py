
from difflib import SequenceMatcher

from app.evaluation.metrics import latency_summary, macro_average

METRICS = ["recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
           "precision_at_5", "precision_at_10", "mrr", "ndcg_at_5", "ndcg_at_10"]


def aggregate(rows: list[dict]) -> dict:
    scored = [row["retrieval"] for row in rows if row["retrieval_scorable"] and row["retrieval"] is not None]
    return {"quality": macro_average(scored, METRICS),
            "scored_query_count": len(scored), "query_count": len(rows),
            "error_count": sum(row["status"] != "ok" for row in rows),
            "latency_ms": {stage: latency_summary([row["latency_ms"][stage] for row in rows
                if row["latency_ms"].get(stage) is not None])
                for stage in ("retrieval", "dense", "bm25", "hybrid", "reranking")}}


def failure_cases(cases: list, reports: dict, inventory: dict, run: int) -> list[dict]:
    labels = {case.id: case for case in cases}
    corpus = {item["chunk_id"]: item for item in inventory["chunks"]}
    failures = []
    for strategy, report in reports.items():
        for row in report["cases"]:
            case = labels[row["id"]]
            expected = {str(value) for value in case.expected_chunk_ids}
            ranking = row["retrieved_chunk_ids"]
            missing = sorted(expected - set(ranking))
            low = {value: ranking.index(value) + 1 for value in expected & set(ranking)
                   if ranking.index(value) >= 5}
            chunks = row["retrieved_chunks"]
            wrong = [item["chunk_id"] for item in chunks[:5]
                     if case.expected_document_ids and item["document_id"] not in
                     {str(value) for value in case.expected_document_ids}]
            near = []
            for hit in chunks[:5]:
                if hit["chunk_id"] in expected:
                    continue
                for label in expected:
                    target = corpus.get(label)
                    if target:
                        ratio = SequenceMatcher(None, hit["text"].lower(), target["text"].lower()).ratio()
                        if ratio >= .85:
                            near.append({"retrieved": hit["chunk_id"], "relevant": label,
                                         "text_similarity": ratio, "status": "candidate_for_human_review"})
            flags = []
            if row["status"] != "ok":
                flags.append("execution_error")
            if missing:
                flags.append("relevant_chunk_missing_from_top_10")
            if low:
                flags.append("relevant_chunk_below_top_5")
            if wrong:
                flags.append("non_labeled_document_in_top_5")
            if near:
                flags.append("possible_near_duplicate_distractor")
            weak = bool(missing or low or (row["retrieval"] and row["retrieval"]["mrr"] < 1))
            if weak and case.category in {"exact_keyword", "rare_identifier"}:
                flags.append("exact_term_case_weak_ranking")
            if weak and case.category == "semantic_paraphrase":
                flags.append("semantic_paraphrase_case_weak_ranking")
            if case.expects_no_answer and chunks:
                flags.append("unanswerable_candidates_require_review")
            if flags or weak:
                failures.append({"run": run, "id": case.id, "question": case.question,
                    "category": case.category, "strategy": strategy,
                    "expected_chunks": sorted(expected), "missing_from_top_10": missing,
                    "low_ranks": low, "non_labeled_document_chunks": wrong, "flags": flags,
                    "near_duplicates": near, "error": row["error"],
                    "retrieved": [{"rank": rank, **item} for rank, item in enumerate(chunks, 1)],
                    "interpretation": "Observed ranking symptoms; causes and unlabeled relevance require human review."})
    return failures


def summarize_runs(cases: list, runs: list[dict], inventory: dict) -> dict:
    categories = sorted({case.category for case in cases})
    by_id = {case.id: case.category for case in cases}
    result = {"run_count": len(runs), "runs": runs, "strategies": {}, "per_category": {},
              "failures": []}
    for strategy in runs[0]["strategies"]:
        reports = [run["strategies"][strategy] for run in runs]
        rows = [row for report in reports for row in report["cases"]]
        quality_runs = [aggregate(report["cases"])["quality"] for report in reports]
        rankings = [[(row["id"], row["status"], row["retrieved_chunk_ids"]) for row in report["cases"]]
                    for report in reports]
        result["strategies"][strategy] = {**aggregate(rows),
            "unique_query_count": len(cases),
            "quality_per_run": quality_runs,
            "quality_variation": {key: latency_summary([q[key] for q in quality_runs if q[key] is not None])
                                  for key in METRICS},
            "rankings_identical_across_runs": all(ranking == rankings[0] for ranking in rankings)}
        for category in categories:
            result["per_category"].setdefault(category, {})[strategy] = aggregate(
                [row for row in rows if by_id[row["id"]] == category])
    for number, run in enumerate(runs, 1):
        result["failures"].extend(failure_cases(cases, run["strategies"], inventory, number))
    return result


def markdown(report: dict) -> str:
    lines = ["# Benchmark comparison", "", "Measured execution: " + report["execution"],
             "Quality is macro-averaged over scored query executions; latency is pooled separately.",
             "MRR is truncated at retrieval depth 10. Errors and unanswerable cases are not scored as relevant retrieval.",
             "", "| Strategy | R@1 | R@3 | R@5 | R@10 | P@5 | P@10 | MRR@10 | NDCG@5 | NDCG@10 | Mean ms | P50 ms | P95 ms | Scored | Errors |",
             "|---|" + "---:|" * 14]
    def fmt(value):
        return "n/a" if value is None else f"{value:.4f}"
    for strategy, row in report["strategies"].items():
        latency = row["latency_ms"]["retrieval"]
        values = [row["quality"][key] for key in METRICS] + [latency[key] for key in ("mean", "p50", "p95")]
        lines.append("| " + strategy + " | " + " | ".join(map(fmt, values)) +
                     f" | {row['scored_query_count']} | {row['error_count']} |")
    lines.extend(["", "## Per-category metrics", ""])
    for category, strategies in report["per_category"].items():
        lines.append(f"- {category}:")
        for strategy, row in strategies.items():
            lines.append(f"  - {strategy}: Recall@5={fmt(row['quality']['recall_at_5'])}; "
                         f"MRR@10={fmt(row['quality']['mrr'])}; scored={row['scored_query_count']}; errors={row['error_count']}")
    return "\n".join(lines) + "\n"


def failure_markdown(failures: list[dict]) -> str:
    lines = ["# Ranking failure review", "", "Symptoms are not automatically diagnosed causes."]
    for item in failures:
        lines += ["", f"## {item['id']} — {item['strategy']} — run {item['run']}",
                  f"Question: {item['question']}", f"Category: {item['category']}",
                  "Expected: " + ", ".join(item["expected_chunks"]),
                  "Flags: " + ", ".join(item["flags"])]
        for hit in item["retrieved"]:
            lines.append(f"- Rank {hit['rank']}: {hit['chunk_id']} | document {hit['document_id']} | "
                         f"{hit['source_filename']} page {hit['page_number']} | score {hit['score']}")
    return "\n".join(lines) + "\n"
