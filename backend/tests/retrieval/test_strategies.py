import asyncio
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.core.errors import IndexingError
from app.evaluation.compare import compare_strategies, comparison_markdown
from app.evaluation.models import EvaluationCase
from app.main import create_app
from app.models.search import SearchRequest
from app.rag.vector_store import QdrantVectorStore
from app.services.indexing import IndexingResources
from app.services.document_service import process_document
from app.services.search_service import search_documents
from tests.conftest import FakeEmbedder
from tests.retrieval.test_token_chunker import FakeTokenizer


class FakeReranker:
    def __init__(self):
        self.calls = 0
    def rerank(self, query, candidates, top_k):
        self.calls += 1
        return sorted(candidates, key=lambda c: ("revenue" not in c.text.lower(), c.chunk_id))[:top_k]


@pytest.fixture
def runtime():
    reranker = FakeReranker()
    resources = IndexingResources(FakeEmbedder(), QdrantVectorStore(QdrantClient(":memory:"), "strategies"), reranker=reranker)
    yield resources
    resources.close()


def seed(resources):
    config = Settings(_env_file=None)
    first = process_document(b"Revenue grew twenty percent.", "finance.txt", "text/plain", config, resources)
    second = process_document(b"Cats are household pets.", "pets.txt", "text/plain", config, resources)
    return first, second


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_strategy_filters(runtime, strategy) -> None:
    first, second = seed(runtime)
    runtime.settings = Settings(_env_file=None, retrieval_strategy=strategy)
    response = search_documents(SearchRequest(query="revenue", top_k=1), runtime)
    assert response.results[0].document_id == first.document_id
    filtered = search_documents(SearchRequest(query="pets", document_id=second.document_id), runtime)
    assert filtered.results
    assert all(item.document_id == second.document_id for item in filtered.results)
    assert runtime.reranker.calls == (2 if strategy == "hybrid_rerank" else 0)


def test_bm25_does_not_call_embedder(runtime, monkeypatch) -> None:
    seed(runtime)
    runtime.settings = Settings(_env_file=None, retrieval_strategy="bm25")
    monkeypatch.setattr(runtime.embedder, "embed_text", Mock(side_effect=AssertionError("must not encode")))
    assert search_documents(SearchRequest(query="revenue"), runtime).results


def test_restart_lexical_payload_source_and_invalidation(runtime) -> None:
    seed(runtime)
    runtime.settings = Settings(_env_file=None, retrieval_strategy="bm25")
    assert not search_documents(SearchRequest(query="inventory"), runtime).results
    process_document(b"Inventory improved.", "stock.txt", "text/plain", Settings(_env_file=None), runtime)
    assert search_documents(SearchRequest(query="inventory"), runtime).results
    replacement = IndexingResources(runtime.embedder, runtime.store, runtime.settings, runtime.reranker)
    assert search_documents(SearchRequest(query="inventory"), replacement).results


def test_token_ingestion(runtime, monkeypatch) -> None:
    monkeypatch.setattr(runtime.embedder, "tokenization_config", lambda: (FakeTokenizer(), 8), raising=False)
    settings = Settings(_env_file=None, chunking_strategy="token", token_chunk_size=5, token_chunk_overlap=2)
    response = process_document(b"zero one two three four five six seven", "a.txt", "text/plain", settings, runtime)
    assert response.chunk_count == 2
    assert all(len(FakeTokenizer()(c.text)["input_ids"]) <= 5 for c in runtime.store.list_chunks())


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_search_ask_citation_compatibility(runtime, strategy) -> None:
    seed(runtime)
    class LLM:
        async def generate(self, system_prompt, user_prompt):
            return "Revenue grew twenty percent [1]."
    config = Settings(_env_file=None, retrieval_strategy=strategy)
    with TestClient(create_app(config, runtime, LLM())) as client:
        search = client.post("/search", json={"query":"revenue", "top_k":1})
        ask = client.post("/ask", json={"question":"revenue", "top_k":1})
        assert search.status_code == ask.status_code == 200
        assert ask.json()["citations"][0]["chunk_id"] == search.json()["results"][0]["chunk_id"]


def test_reranker_error_no_hidden_fallback(runtime, monkeypatch) -> None:
    seed(runtime)
    monkeypatch.setattr(runtime.reranker, "rerank", Mock(side_effect=IndexingError("Reranker unavailable")))
    with TestClient(create_app(Settings(_env_file=None, retrieval_strategy="hybrid_rerank"), runtime)) as client:
        assert client.post("/search", json={"query":"revenue"}).status_code == 503


def test_comparison_uses_all_four_and_stage_timings(runtime) -> None:
    first, _ = seed(runtime)
    expected = next(c.chunk_id for c in runtime.store.list_chunks() if c.document_id == first.document_id)
    cases = [EvaluationCase(id="q", question="revenue", expected_chunk_ids=[expected], reference_answer="Revenue grew.")]
    report = asyncio.run(compare_strategies(cases, Settings(_env_file=None), runtime, "unit", "hash",
                                            warmup=0, execution="injected_test_models"))
    assert set(report["summary"]) == {"dense", "bm25", "hybrid", "hybrid_rerank"}
    assert all(row["errors"] == 0 for row in report["summary"].values())
    assert report["strategies"]["bm25"]["latency_ms"]["embedding"]["count"] == 0
    assert report["strategies"]["hybrid_rerank"]["latency_ms"]["reranking"]["count"] == 1
    assert "injected_test_models" in comparison_markdown(report)
