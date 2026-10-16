import json
from uuid import uuid4

import pytest

from app.evaluation.dataset import EvaluationError, load_dataset


def record() -> dict:
    return {"id": "case", "question": "Revenue?", "expected_chunk_ids": [str(uuid4())],
            "reference_answer": "Revenue grew."}


@pytest.mark.parametrize("extension", ["json", "jsonl"])
def test_dataset_formats(tmp_path, extension) -> None:
    data = record()
    path = tmp_path / ("data." + extension)
    path.write_text(json.dumps([data] if extension == "json" else data))
    cases = load_dataset(path)
    assert cases[0].id == "case"
    assert cases[0].filter_document_id is None


@pytest.mark.parametrize("change", [
    {"question": " "}, {"question": "x"*2001}, {"reference_answer": ""},
    {"expected_chunk_ids": ["bad"]}, {"expected_chunk_ids": []},
    {"expected_document_id": "bad"}, {"unexpected": True},
])
def test_invalid_records(tmp_path, change) -> None:
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{**record(), **change}]))
    with pytest.raises(EvaluationError, match="record 1"):
        load_dataset(path)


@pytest.mark.parametrize("data", ["not json", "[]", "{}", '[{"id": "incomplete"}]'])
def test_invalid_files(tmp_path, data) -> None:
    path = tmp_path / "data.json"
    path.write_text(data)
    with pytest.raises(EvaluationError):
        load_dataset(path)


def test_duplicate_case_and_label_ids(tmp_path) -> None:
    path = tmp_path / "data.json"
    item = record()
    path.write_text(json.dumps([item, item]))
    with pytest.raises(EvaluationError, match="unique"):
        load_dataset(path)
    item["expected_chunk_ids"] *= 2
    path.write_text(json.dumps([item]))
    with pytest.raises(EvaluationError):
        load_dataset(path)


def test_explicit_unanswerable(tmp_path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({**record(), "expected_chunk_ids": [], "expects_no_answer": True}))
    assert load_dataset(path)[0].expects_no_answer
