"""Compare retrieval strategies on one corpus/dataset, without LLM calls."""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys

from app.core.config import Settings
from app.evaluation.backend import ServiceBackend
from app.evaluation.dataset import load_dataset
from app.evaluation.models import EvaluationCase
from app.evaluation.runner import evaluate
from app.rag.retrieval import STRATEGIES
from app.services.indexing import IndexingResources, create_resources


async def compare_strategies(cases: list[EvaluationCase], settings: Settings,
                            resources: IndexingResources, dataset: str, dataset_hash: str,
                            warmup: int = 1, execution: str = "production_services",
                            ks: tuple[int, ...] = (1, 3, 5)) -> dict:
    if not 0 <= warmup <= 10:
        raise ValueError("Warmup count must be between 0 and 10")
    reports = {}
    summary = {}
    warmup_errors = {}
    warm_case = next((case for case in cases if case.expected_chunk_ids), cases[0])
    for strategy in STRATEGIES:
        config = settings.model_copy(update={"retrieval_strategy": strategy})
        backend = ServiceBackend(config, resources)
        for _ in range(warmup):
            try:
                await backend.retrieve(warm_case, max(ks))
            except Exception:
                warmup_errors[strategy] = "Warmup failed; inspect measured case errors"
                break
        report = await evaluate(cases, backend, config, dataset, dataset_hash,
                                retrieval_only=True, execution=execution, ks=ks)
        reports[strategy] = report.model_dump(mode="json")
        summary[strategy] = {"recall_at_5": report.retrieval["recall_at_5"],
            "mrr": report.retrieval["mrr"], "ndcg_at_5": report.retrieval["ndcg_at_5"],
            "retrieval_p50_ms": report.latency_ms["retrieval"]["p50"],
            "reranking_p50_ms": report.latency_ms["reranking"]["p50"],
            "errors": report.num_errors}
    return {"schema_version": "1.0", "dataset": dataset, "dataset_sha256": dataset_hash,
        "execution": execution, "warmup_queries_per_strategy": warmup,
        "warmup_errors": warmup_errors, "summary": summary, "strategies": reports}


def comparison_markdown(report: dict) -> str:
    lines = ["# Retrieval comparison", "", f"Dataset: {report['dataset']}; execution: {report['execution']}.",
        f"Warmup queries per strategy (excluded): {report['warmup_queries_per_strategy']}.", "",
        "A small demonstration dataset does not establish general model quality.", "",
        "| Retriever | Recall@5 | MRR | NDCG@5 | P50 retrieval ms | P50 reranking ms | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    def fmt(value: object) -> str:
        return "not measured" if value is None else f"{value:.4f}"
    for strategy, values in report["summary"].items():
        lines.append(f"| {strategy} | " + " | ".join(fmt(values[key]) for key in
            ("recall_at_5", "mrr", "ndcg_at_5", "retrieval_p50_ms", "reranking_p50_ms")) + f" | {values['errors']} |")
    return "\n".join(lines) + "\n"


async def run(args: argparse.Namespace) -> int:
    if args.output.suffix != ".json":
        raise ValueError("Comparison output must have a .json suffix")
    if args.dataset.resolve() in {args.output.resolve(), args.output.with_suffix(".md").resolve()}:
        raise ValueError("Output cannot overwrite the dataset")
    settings = Settings()
    cases = load_dataset(args.dataset)
    resources = create_resources(settings)
    try:
        report = await compare_strategies(cases, settings, resources, args.dataset.name,
            sha256(args.dataset.read_bytes()).hexdigest(), args.warmup)
    finally:
        resources.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".md").write_text(comparison_markdown(report))
    print(json.dumps(report["summary"], indent=2))
    return int(any(row["errors"] for row in report["summary"].values()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args))
    except Exception:
        print("Comparison could not complete; check inputs, configuration and model availability", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
