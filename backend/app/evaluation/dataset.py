import json
from pathlib import Path

from pydantic import ValidationError

from app.evaluation.models import EvaluationCase


class EvaluationError(ValueError):
    """Safe evaluation validation or execution failure."""


def load_dataset(path: Path) -> list[EvaluationCase]:
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            raise EvaluationError("Evaluation dataset exceeds the 10 MiB limit")
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".jsonl":
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        elif path.suffix.lower() == ".json":
            records = json.loads(text)
        else:
            raise EvaluationError("Dataset must be JSON or JSONL")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError("Dataset cannot be read as valid UTF-8 JSON/JSONL") from exc
    if not isinstance(records, list) or not records:
        raise EvaluationError("Dataset must contain a nonempty list of records")
    cases: list[EvaluationCase] = []
    for number, record in enumerate(records, start=1):
        try:
            cases.append(EvaluationCase.model_validate(record))
        except ValidationError as exc:
            raise EvaluationError(f"Invalid dataset record {number}; check required fields, UUIDs and relevance labels") from exc
    if len({case.id for case in cases}) != len(cases):
        raise EvaluationError("Dataset case IDs must be unique")
    return cases
