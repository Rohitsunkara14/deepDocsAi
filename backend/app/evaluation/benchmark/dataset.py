
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.evaluation.models import EvaluationCase

CATEGORIES = (
    "semantic_paraphrase", "exact_keyword", "rare_identifier", "numerical",
    "multi_chunk", "multi_page", "cross_document", "distractor_heavy",
    "unanswerable", "prompt_injection", "table_or_structured_fact", "temporal_comparison",
)
MAX_BYTES = 10 * 1024 * 1024
MAX_CASES = 5000


class BenchmarkCase(EvaluationCase):
    expected_document_ids: list[UUID] = Field(max_length=1000)
    expected_chunk_ids: list[UUID] = Field(max_length=1000)
    expected_document_id: None = None  # Benchmark uses the plural label exclusively.
    category: str
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=10000)
    expects_no_answer: bool = Field(strict=True)
    # Optional, explicit filter test only; never derived from expected labels.
    filter_document_id: UUID | None = None

    @model_validator(mode="after")
    def benchmark_labels(self) -> "BenchmarkCase":
        if "template" in self.tags:
            raise ValueError("Template rows must be manually completed before validation")
        if self.category not in CATEGORIES:
            raise ValueError("Unknown benchmark category")
        if len(set(self.expected_document_ids)) != len(self.expected_document_ids):
            raise ValueError("Duplicate document labels")
        if self.expects_no_answer:
            if self.expected_chunk_ids or self.expected_document_ids:
                raise ValueError("Unanswerable cases cannot have relevant labels")
        elif not self.expected_document_ids:
            raise ValueError("Answerable cases require document labels")
        if self.category == "unanswerable" and not self.expects_no_answer:
            raise ValueError("Unanswerable category requires expects_no_answer=true")
        if self.filter_document_id is not None and "explicit_filter" not in self.tags:
            raise ValueError("Filter tests require the explicit_filter tag")
        return self


def load_cases(path: Path) -> list[BenchmarkCase]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Dataset exceeds 10 MiB")
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        if len(cases) >= MAX_CASES:
            raise ValueError("Dataset exceeds 5000 cases")
        try:
            cases.append(BenchmarkCase.model_validate(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid benchmark line {line_number}: {exc}") from exc
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Require nonempty dataset and unique question IDs")
    return cases


def validate_inventory(cases: list[BenchmarkCase], inventory: dict) -> None:
    chunks = {item["chunk_id"]: item for item in inventory["chunks"]}
    documents = {item["document_id"] for item in inventory["documents"]}
    for case in cases:
        expected_docs = {str(value) for value in case.expected_document_ids}
        if not expected_docs <= documents:
            raise ValueError(f"{case.id}: document label not in inventory")
        label_docs = set()
        for chunk_id in case.expected_chunk_ids:
            item = chunks.get(str(chunk_id))
            if item is None or item["document_id"] not in expected_docs:
                raise ValueError(f"{case.id}: chunk label missing or belongs to another document")
            label_docs.add(item["document_id"])
            if case.filter_document_id and item["document_id"] != str(case.filter_document_id):
                raise ValueError(f"{case.id}: relevant chunk excluded by explicit filter")
        if label_docs != expected_docs:
            raise ValueError(f"{case.id}: every relevant document needs a relevant chunk label")
        if case.filter_document_id and str(case.filter_document_id) not in documents:
            raise ValueError(f"{case.id}: explicit filter document not in inventory")
