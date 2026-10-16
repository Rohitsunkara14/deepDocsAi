
"""Prepare, validate and compare a manually annotated real-document benchmark."""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path

from app.evaluation.benchmark.corpus import ingest, settings_for, verify_store
from app.evaluation.benchmark.dataset import load_cases, validate_inventory
from app.evaluation.benchmark.report import summarize_runs, markdown, failure_markdown
from app.evaluation.compare import compare_strategies
from app.services.indexing import create_resources


async def repeated(cases, settings, resources, dataset, digest, inventory, runs=5, warmup=2):
    if not 1 <= runs <= 20 or not 0 <= warmup <= 10:
        raise ValueError("Require 1–20 runs and 0–10 warmup queries")
    reports = []
    for _ in range(runs):
        reports.append(await compare_strategies(cases, settings, resources, dataset, digest,
                       warmup=warmup, ks=(1, 3, 5, 10)))
    return summarize_runs(cases, reports, inventory)


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("ingest")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--storage", type=Path, required=True)
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--collection", default="deepdocs_benchmark")
    for name in ("validate", "compare"):
        command = commands.add_parser(name)
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--inventory", type=Path, required=True)
        if name == "compare":
            command.add_argument("--output", type=Path, required=True, help="New directory for reports")
            command.add_argument("--runs", type=int, default=5)
            command.add_argument("--warmup", type=int, default=2)
    args = cli.parse_args(argv)
    try:
        if args.command == "ingest":
            inventory = ingest(args.manifest, args.storage, args.inventory, args.collection)
            print(f"Corpus ingested; review full chunk inventory at {args.inventory}")
            return int(bool(inventory["failures"]))
        cases = load_cases(args.dataset)
        inventory = json.loads(args.inventory.read_text())
        validate_inventory(cases, inventory)
        if args.command == "validate":
            print(f"Validated {len(cases)} cases against the chunk inventory. No retrieval performed.")
            return 0
        if args.output.exists():
            raise ValueError("Use a new report output directory")
        settings = settings_for(Path(inventory["storage"]), inventory.get("collection", "deepdocs_benchmark"))
        if settings.embedding_model_name != inventory["configuration"]["embedding_model_name"]:
            raise ValueError("Embedding model differs from inventory")
        resources = create_resources(settings)
        try:
            verify_store(resources, inventory)
            report = asyncio.run(repeated(cases, settings, resources, args.dataset.name,
                sha256(args.dataset.read_bytes()).hexdigest(), inventory, args.runs, args.warmup))
        finally:
            resources.close()
        report.update(execution="actual_production_retrieval_services",
                      inventory_sha256=sha256(args.inventory.read_bytes()).hexdigest(),
                      corpus_documents=inventory["documents"],
                      ingestion_configuration=inventory["configuration"])
        args.output.mkdir(parents=True)
        (args.output / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        (args.output / "comparison.md").write_text(markdown(report))
        (args.output / "failures.json").write_text(json.dumps(report["failures"], indent=2, allow_nan=False) + "\n")
        (args.output / "failures.md").write_text(failure_markdown(report["failures"]))
        print(f"Reports saved in {args.output}")
        return int(any(row["error_count"] for row in report["strategies"].values()))
    except (ValueError, OSError) as exc:
        print(f"Benchmark validation/setup failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
