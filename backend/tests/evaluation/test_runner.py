import asyncio
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.evaluation.backend import ServiceBackend
from app.evaluation.dataset import load_dataset
from app.evaluation.models import EvaluationReport, EvaluationCase
from app.evaluation.replay import ReplayBackend, ReplayJudge, load_replay
from app.evaluation.run import main
from app.evaluation.runner import evaluate
from app.services.document_service import process_document

EXAMPLES = Path(__file__).resolve().parents[2] / "evaluation/examples"


def test_replay_serialization_and_fake_judge() -> None:
    cases = load_dataset(EXAMPLES / "demo.jsonl")
    records = load_replay(EXAMPLES / "replay.json")
    report = asyncio.run(evaluate(cases, ReplayBackend(records), Settings(_env_file=None), "demo.jsonl", "hash",
        judge=ReplayJudge(records), execution="synthetic_replay_not_model_quality", judge_mode="synthetic_fixture_scores"))
    assert report.num_queries == 5
    assert report.num_retrieval_scored == 4
    assert report.num_judge_scored == 5
    assert report.judge["faithfulness"] == .9
    assert report.latency_ms["embedding"]["mean"] is None
    assert EvaluationReport.model_validate_json(report.model_dump_json()) == report


def test_retrieval_only_never_asks() -> None:
    cases = load_dataset(EXAMPLES / "demo.jsonl")
    backend = ReplayBackend(load_replay(EXAMPLES / "replay.json"))
    backend.ask = Mock(side_effect=AssertionError("must not call LLM"))
    report = asyncio.run(evaluate(cases, backend, Settings(_env_file=None), "demo", "hash", retrieval_only=True))
    assert report.num_generation_scored == report.num_judge_scored == 0
    assert all(value is None for value in report.judge.values())
    assert report.cases[2].retrieval["mrr"] == .5
    backend.ask.assert_not_called()


def test_failure_counts_not_silently_dropped() -> None:
    cases = load_dataset(EXAMPLES / "demo.jsonl")
    records = load_replay(EXAMPLES / "replay.json")
    del records[cases[0].id]
    report = asyncio.run(evaluate(cases, ReplayBackend(records), Settings(_env_file=None), "demo", "hash", retrieval_only=True))
    assert report.num_errors == 1
    assert report.cases[0].retrieval is None
    assert report.num_retrieval_scored == 3


def test_cli_replay(tmp_path) -> None:
    output = tmp_path / "results.json"
    code = main(["--dataset", str(EXAMPLES/"demo.jsonl"), "--replay", str(EXAMPLES/"replay.json"),
                 "--retrieval-only", "--output", str(output)])
    assert code == 0
    report = json.loads(output.read_text())
    assert report["dataset_sha256"] == sha256((EXAMPLES/"demo.jsonl").read_bytes()).hexdigest()
    assert report["execution"] == "synthetic_replay_not_model_quality"


@pytest.mark.parametrize("flags", [["--retrieval-only", "--judge"], ["--fake-judge"], ["--ks", "0"], ["--ks", "1", "1"]])
def test_cli_invalid_modes(tmp_path, flags) -> None:
    assert main(["--dataset", str(EXAMPLES/"demo.jsonl"), "--output", str(tmp_path/"out.json"), *flags]) == 2


def test_service_backend_reuses_real_services(resources) -> None:
    config = Settings(_env_file=None)
    ingestion = process_document(b"Revenue grew.", "a.txt", "text/plain", config, resources)
    chunks, _ = resources.store.client.scroll("test_chunks")
    case = EvaluationCase(id="q", question="Revenue?", expected_chunk_ids=[str(chunks[0].id)], reference_answer="Revenue grew.")
    class LLM:
        async def generate(self, system_prompt, user_prompt):
            return "Revenue grew [1]."
    backend = ServiceBackend(config, resources, LLM())
    report = asyncio.run(evaluate([case], backend, config, "unit", "hash"))
    assert report.num_errors == 0
    assert report.cases[0].retrieved_chunk_ids == [str(chunks[0].id)]
    assert report.retrieval["recall_at_1"] == 1
    assert report.generation["citation_validity"] == 1
    assert report.latency_ms["retrieval"]["count"] == 1
    assert report.latency_ms["embedding"]["mean"] >= 0
    assert report.latency_ms["generation"]["mean"] >= 0
    assert report.latency_ms["rag"]["mean"] >= report.latency_ms["generation"]["mean"]


def test_judge_failure_retains_deterministic_metrics() -> None:
    class BrokenJudge:
        async def evaluate(self, sample):
            raise RuntimeError("SECRET")
    cases = load_dataset(EXAMPLES / "demo.jsonl")[:1]
    backend = ReplayBackend(load_replay(EXAMPLES / "replay.json"))
    report = asyncio.run(evaluate(cases, backend, Settings(_env_file=None), "demo", "hash", judge=BrokenJudge()))
    assert report.cases[0].status == "judge_error"
    assert report.cases[0].generation is not None
    assert report.num_judge_scored == 0
    assert "SECRET" not in report.model_dump_json()
