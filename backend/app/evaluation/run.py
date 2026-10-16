import argparse
import asyncio
from hashlib import sha256
from pathlib import Path
import sys

import httpx

from app.core.config import Settings
from app.evaluation.backend import ServiceBackend
from app.evaluation.dataset import EvaluationError, load_dataset
from app.evaluation.judge import JudgeSettings, LLMJudge
from app.evaluation.replay import ReplayBackend, ReplayJudge, load_replay
from app.evaluation.runner import evaluate
from app.rag.llm import OpenAICompatibleLLM
from app.services.indexing import create_resources


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Evaluate retrieval and optional RAG generation")
    cli.add_argument("--dataset", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--retrieval-only", action="store_true")
    cli.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5])
    cli.add_argument("--judge", action="store_true", help="Opt in to a real judge; may incur provider charges")
    cli.add_argument("--replay", type=Path, help="Use synthetic outputs from a JSON fixture; no real retrieval or generation")
    cli.add_argument("--fake-judge", action="store_true", help="Use fixture judge scores; requires --replay")
    return cli


async def run(args: argparse.Namespace) -> int:
    if args.retrieval_only and (args.judge or args.fake_judge):
        raise EvaluationError("Retrieval-only mode cannot call a judge")
    if args.fake_judge and not args.replay or args.judge and (args.fake_judge or args.replay):
        raise EvaluationError("Use a real judge with production services or a fake judge with replay")
    if any(k < 1 or k > 20 for k in args.ks) or len(set(args.ks)) != len(args.ks):
        raise EvaluationError("K values must be unique integers from 1 to 20")
    if args.output.resolve() == args.dataset.resolve() or (args.replay and args.output.resolve() == args.replay.resolve()):
        raise EvaluationError("Output must not overwrite input data")
    cases = load_dataset(args.dataset)
    settings = Settings()
    resources = None
    async with httpx.AsyncClient(follow_redirects=False) as client:
        try:
            judge = None
            judge_mode = "disabled"
            if args.replay:
                records = load_replay(args.replay)
                backend = ReplayBackend(records)
                execution = "synthetic_replay_not_model_quality"
                if args.fake_judge:
                    judge, judge_mode = ReplayJudge(records), "synthetic_fixture_scores"
            else:
                resources = create_resources(settings)
                llm = None if args.retrieval_only else OpenAICompatibleLLM(settings, client)
                backend = ServiceBackend(settings, resources, llm)
                execution = "production_services"
                if args.judge:
                    config = JudgeSettings()
                    judge = LLMJudge(OpenAICompatibleLLM(config.llm_settings(), client), config)
                    judge_mode = "llm_judge"
            report = await evaluate(cases, backend, settings, args.dataset.name,
                sha256(args.dataset.read_bytes()).hexdigest(), args.retrieval_only, judge,
                tuple(sorted(args.ks)), execution, judge_mode)
        finally:
            if resources is not None:
                resources.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"Report written: {report.num_queries} queries, {report.num_errors} errors")
    return 1 if report.num_errors else 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return asyncio.run(run(args))
    except EvaluationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception:
        print("Evaluation could not complete; check configuration, inputs and output permissions", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
