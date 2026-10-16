import asyncio
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.evaluation.annotate import format_candidates
from app.evaluation.benchmark import dataset
from app.evaluation.benchmark.__main__ import repeated, main
from app.evaluation.benchmark.corpus import CorpusManifest, manifest_files, ingest, verify_store
from app.evaluation.benchmark.dataset import BenchmarkCase, load_cases, validate_inventory
from app.evaluation.benchmark.report import failure_cases, markdown, failure_markdown, summarize_runs
from tests.retrieval.test_strategies import runtime, seed


def record():
    return dict(id="q1", question="What grew?", expected_document_ids=[str(uuid4())],
                expected_chunk_ids=[str(uuid4())], reference_answer="Revenue grew.",
                expects_no_answer=False, category="semantic_paraphrase", difficulty="medium",
                tags=[], notes="")


@pytest.mark.parametrize("update", [
    {"category":"made_up"}, {"question":" "}, {"reference_answer":""},
    {"expected_document_ids":["not-a-uuid"]}, {"expected_chunk_ids":["placeholder"]},
    {"unexpected":1}, {"expects_no_answer":True}, {"expects_no_answer":"false"},
    {"category":"unanswerable"}, {"expected_document_ids":[]},
    {"difficulty":"unknown"}, {"reference_answer":None},
    {"filter_document_id":str(uuid4())},
])
def test_bad_cases(update):
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(record() | update)


def test_duplicate_labels_and_unanswerable():
    raw = record()
    for key in ("expected_document_ids", "expected_chunk_ids"):
        with pytest.raises(ValidationError):
            BenchmarkCase.model_validate(raw | {key:raw[key] * 2})
    raw.update(expected_document_ids=[], expected_chunk_ids=[], expects_no_answer=True,
               category="unanswerable", reference_answer="Verified absent from corpus.")
    assert BenchmarkCase.model_validate(raw).expects_no_answer


def test_load_limits_duplicates_and_template(tmp_path, monkeypatch):
    file = tmp_path/"cases.jsonl"
    raw = record()
    file.write_text(json.dumps(raw)+"\n"+json.dumps(raw))
    with pytest.raises(ValueError, match="unique"):
        load_cases(file)
    monkeypatch.setattr(dataset, "MAX_CASES", 1)
    with pytest.raises(ValueError, match="5000"):
        load_cases(file)
    monkeypatch.setattr(dataset, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="MiB"):
        load_cases(file)


def test_inventory_validation():
    raw = record()
    case = BenchmarkCase.model_validate(raw)
    inventory = {"documents":[{"document_id":raw["expected_document_ids"][0]}],
                 "chunks":[{"chunk_id":raw["expected_chunk_ids"][0],
                            "document_id":raw["expected_document_ids"][0]}]}
    validate_inventory([case], inventory)
    wrong = deepcopy(inventory)
    wrong["chunks"][0]["document_id"] = str(uuid4())
    with pytest.raises(ValueError):
        validate_inventory([case], wrong)


def test_manifest_missing_duplicate_and_paths(tmp_path):
    item = {"id":"a","filename":"real.pdf","category":"report"}
    with pytest.raises(ValidationError):
        CorpusManifest(documents=[item,item])
    with pytest.raises(ValidationError):
        CorpusManifest(documents=[item | {"filename":"../real.pdf"}])
    path = tmp_path/"manifest.json"
    path.write_text(json.dumps({"documents":[item]}))
    with pytest.raises(ValueError, match="Missing"):
        manifest_files(path, 5)


def test_annotation(runtime):
    seed(runtime)
    hit = runtime.store.list_chunks()[0]
    text = format_candidates("question", [hit], 10)
    assert all(value in text for value in ["Rank 1",hit.chunk_id, hit.document_id,
                                          hit.source_filename, "page=",hit.text[:10]])
    assert "human" in text


def test_repeated_categories_serialization_and_no_leakage(runtime, monkeypatch):
    first, second = seed(runtime)
    chunks = runtime.store.list_chunks()
    hit = next(c for c in chunks if c.document_id == first.document_id)
    raw = record() | {"expected_document_ids":[first.document_id],"expected_chunk_ids":[hit.chunk_id]}
    cases = [BenchmarkCase.model_validate(raw),
             BenchmarkCase.model_validate(raw | {"id":"q2","category":"exact_keyword"})]
    filters = []
    original = runtime.retriever.retrieve
    def spy(query, top_k, document_id=None, strategy="dense"):
        filters.append(document_id)
        return original(query, top_k, document_id, strategy)
    monkeypatch.setattr(runtime.retriever, "retrieve", spy)
    inventory = {"chunks":[c.model_dump() for c in chunks]}
    report = asyncio.run(repeated(cases, Settings(_env_file=None), runtime, "test", "hash",
                                  inventory, runs=2, warmup=1))
    assert filters and all(value is None for value in filters)
    assert report["run_count"] == 2
    assert len(report["per_category"]) == 2
    assert all(row["query_count"] == 4 for row in report["strategies"].values())
    assert all("recall_at_10" in row["quality"] for row in report["strategies"].values())
    assert all(row["rankings_identical_across_runs"] for row in report["strategies"].values())
    report["execution"] = "injected_test_models_only"
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    assert "P95" in markdown(report)
    assert "Symptoms" in failure_markdown(report["failures"])
    filtered = BenchmarkCase.model_validate(raw | {"filter_document_id":first.document_id,
                                                   "tags":["explicit_filter"]})
    filters.clear()
    asyncio.run(repeated([filtered], Settings(_env_file=None), runtime, "test", "hash", inventory,
                         runs=1, warmup=0))
    assert filters and all(value == first.document_id for value in filters)


def test_failure_symptoms():
    raw = record()
    case = BenchmarkCase.model_validate(raw)
    expected = raw["expected_chunk_ids"][0]
    relevant = {"chunk_id":expected,"text":"Annual revenue increased twenty percent."}
    distractor = dict(chunk_id=str(uuid4()), document_id=str(uuid4()),
                      text=relevant["text"], source_filename="other.txt", page_number=2,
                      score=.9)
    row = {"id":case.id,"retrieved_chunk_ids":[distractor["chunk_id"]],
           "retrieved_chunks":[distractor], "status":"ok","error":None,
           "retrieval":{"mrr":0}}
    failure = failure_cases([case], {"dense":{"cases":[row]}}, {"chunks":[relevant]},1)[0]
    assert expected in failure["missing_from_top_10"]
    assert "possible_near_duplicate_distractor" in failure["flags"]
    assert "semantic_paraphrase_case_weak_ranking" in failure["flags"]
    assert failure["retrieved"][0]["rank"] == 1
    assert "causes" in failure["interpretation"]


def test_ingest_validate_cli_and_changed_inventory(runtime, tmp_path, monkeypatch):
    from app.evaluation.benchmark import corpus
    monkeypatch.setattr(corpus, "create_resources", lambda config: runtime)
    monkeypatch.setattr(runtime, "close", lambda: None)
    (tmp_path/"report.txt").write_text("Revenue grew twenty percent.")
    manifest = tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"documents":[{"id":"finance","filename":"report.txt","category":"report"}]}))
    inventory_path = tmp_path/"inventory.json"
    ingest(manifest, tmp_path/"store", inventory_path)
    inventory = json.loads(inventory_path.read_text())
    verify_store(runtime, inventory)
    raw = record() | {"expected_document_ids":[inventory["documents"][0]["document_id"]],
                      "expected_chunk_ids":[inventory["chunks"][0]["chunk_id"]]}
    path = tmp_path/"cases.jsonl"
    path.write_text(json.dumps(raw))
    assert main(["validate","--dataset",str(path),"--inventory",str(inventory_path)]) == 0
    inventory["chunks"][0]["text"] = "changed"
    with pytest.raises(ValueError, match="differs"):
        verify_store(runtime, inventory)


def test_compare_cli_writes_reports(runtime, tmp_path, monkeypatch):
    from app.evaluation.benchmark import __main__ as cli
    first, _ = seed(runtime)
    chunks = runtime.store.list_chunks()
    hit = next(c for c in chunks if c.document_id == first.document_id)
    inventory = {"storage":str(tmp_path/"store"),
                 "configuration":{"embedding_model_name":Settings(_env_file=None).embedding_model_name},
                 "documents":[{"document_id":c.document_id} for c in chunks],
                 "chunks":[c.model_dump() for c in chunks]}
    inventory_path = tmp_path/"inventory.json"
    inventory_path.write_text(json.dumps(inventory))
    cases = tmp_path/"cases.jsonl"
    cases.write_text(json.dumps(record() | {"expected_document_ids":[first.document_id],
                                          "expected_chunk_ids":[hit.chunk_id]}))
    monkeypatch.setattr(cli, "create_resources", lambda settings: runtime)
    monkeypatch.setattr(runtime, "close", lambda: None)
    output = tmp_path/"report"
    assert main(["compare","--dataset",str(cases),"--inventory",str(inventory_path),
                 "--output",str(output),"--runs","2","--warmup","1"]) == 0
    assert {p.name for p in output.iterdir()} == {
        "comparison.json","comparison.md","failures.json","failures.md"}
    report = json.loads((output/"comparison.json").read_text())
    assert report["run_count"] == 2
    assert all(row["error_count"] == 0 for row in report["strategies"].values())


def test_low_rank_and_bounds(runtime):
    raw = record()
    case = BenchmarkCase.model_validate(raw)
    expected = raw["expected_chunk_ids"][0]
    ranking = [str(uuid4()) for _ in range(5)] + [expected]
    row = {"id":case.id,"retrieved_chunk_ids":ranking, "retrieved_chunks":[],
           "status":"ok","error":None,"retrieval":{"mrr":1/6}}
    failure = failure_cases([case], {"dense":{"cases":[row]}}, {"chunks":[]},1)[0]
    assert failure["low_ranks"] == {expected:6}
    for runs, warmup in [(0,1),(21,1),(1,-1),(1,11)]:
        with pytest.raises(ValueError):
            asyncio.run(repeated([case], Settings(_env_file=None), runtime,
                                 "test","hash",{},runs=runs,warmup=warmup))


def test_ingestion_continues_and_preserves_collection(runtime, tmp_path, monkeypatch):
    from app.evaluation.benchmark import corpus
    from app.services.document_service import DocumentProcessingError
    original = corpus.process_document
    def process(data, filename, mime, settings, resources):
        if filename == "broken.pdf":
            raise DocumentProcessingError(422, "Corrupt PDF")
        return original(data, filename, mime, settings, resources)
    monkeypatch.setattr(corpus, "process_document", process)
    monkeypatch.setattr(corpus, "create_resources", lambda config: runtime)
    monkeypatch.setattr(runtime, "close", lambda: None)
    (tmp_path/"broken.pdf").write_bytes(b"not pdf")
    (tmp_path/"valid.txt").write_text("Revenue increased.")
    manifest = tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"documents":[
        {"id":"bad","filename":"broken.pdf","category":"annual-report"},
        {"id":"good","filename":"valid.txt","category":"annual-report"}]}))
    inventory = ingest(manifest, tmp_path/"store", tmp_path/"inventory.json", "deepdocs_real_benchmark")
    assert inventory["collection"] == "deepdocs_real_benchmark"
    assert len(inventory["documents"]) == len(inventory["failures"]) == 1
    assert inventory["failures"][0]["reason"] == "Corrupt PDF"
    assert inventory["documents"][0]["indexed_chunk_count"] == 1
    assert inventory["chunks"][0]["manifest_document_id"] == "good"
    verify_store(runtime, inventory)
    assert corpus.settings_for(tmp_path, "deepdocs_real_benchmark").qdrant_collection_name == "deepdocs_real_benchmark"
