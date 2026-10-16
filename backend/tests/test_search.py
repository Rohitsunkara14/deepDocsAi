from uuid import UUID, uuid4
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import IndexingError
from app.main import create_app
from app.services.document_service import process_document


@pytest.fixture
def client(resources):
    with TestClient(create_app(Settings(_env_file=None, embedding_batch_size=2), resources)) as client:
        yield client


def upload(client: TestClient, name: str, text: str) -> dict:
    response = client.post("/documents/upload", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()


def test_index_search_and_filter(client: TestClient, resources) -> None:
    revenue = upload(client, "finance.txt", "Revenue grew by twenty percent.")
    pets = upload(client, "pets.txt", "Cats are popular household pets.")
    assert revenue["chunk_count"] == revenue["indexed_chunk_count"] == 1
    result = client.post("/search", json={"query": "sales growth", "top_k": 1}).json()
    assert result["results"][0]["document_id"] == revenue["document_id"]
    assert result["results"][0]["source_filename"] == "finance.txt"
    assert result["results"][0]["score"] > .9
    filtered = client.post("/search", json={"query": "sales", "document_id": pets["document_id"]}).json()
    assert all(hit["document_id"] == pets["document_id"] for hit in filtered["results"])
    assert filtered["results"]
    assert client.post("/search", json={"query": "sales", "document_id": str(uuid4())}).json()["results"] == []
    again = upload(client, "finance.txt", "Revenue grew by twenty percent.")
    assert again["document_id"] == revenue["document_id"]
    assert resources.store.client.count("test_chunks").count == 2
    UUID(result["results"][0]["chunk_id"])


@pytest.mark.parametrize("body", [
    {"query": ""}, {"query": " \n"}, {}, {"query": "x", "top_k": 0},
    {"query": "x", "top_k": 21}, {"query": "x", "top_k": 1.5},
    {"query": "x", "top_k": True}, {"query": "x", "document_id": "bad"},
])
def test_validation(client: TestClient, body: dict) -> None:
    assert client.post("/search", json=body).status_code == 422


def test_empty_collection(client: TestClient) -> None:
    response = client.post("/search", json={"query": "revenue"})
    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.parametrize("endpoint", ["upload", "search"])
def test_qdrant_unavailable(client: TestClient, resources, endpoint: str, monkeypatch) -> None:
    monkeypatch.setattr(resources.store.client, "collection_exists", Mock(side_effect=OSError("private")))
    response = (client.post("/documents/upload", files={"file": ("a.txt", b"Revenue", "text/plain")})
                if endpoint == "upload" else client.post("/search", json={"query": "revenue"}))
    assert response.status_code == 503
    assert "Qdrant" in response.json()["detail"]
    assert "private" not in response.text


@pytest.mark.parametrize("operation", ["upsert", "query_points"])
def test_write_search_failures(client: TestClient, resources, monkeypatch, operation: str) -> None:
    resources.store.ensure_collection(3)
    monkeypatch.setattr(resources.store.client, operation, Mock(side_effect=OSError("private")))
    response = (client.post("/documents/upload", files={"file": ("a.txt", b"Revenue", "text/plain")})
                if operation == "upsert" else client.post("/search", json={"query": "revenue"}))
    assert response.status_code == 503
    assert "private" not in response.text


def test_model_failure(client: TestClient, resources, monkeypatch) -> None:
    monkeypatch.setattr(resources.embedder, "embed_text", Mock(side_effect=IndexingError("Embedding computation failed.")))
    response = client.post("/search", json={"query": "revenue"})
    assert response.status_code == 503


def test_api_dimension_mismatch(client: TestClient, resources) -> None:
    resources.store.ensure_collection(4)
    response = client.post("/search", json={"query": "revenue"})
    assert response.status_code == 409


def test_batching_and_shorter_reingestion(resources) -> None:
    data = b"Revenue improved considerably. " * 10 + b"Cats live at home. " * 10
    small = Settings(_env_file=None, chunk_size=50, chunk_overlap=10, embedding_batch_size=2)
    first = process_document(data, "a.txt", "text/plain", small, resources)
    assert len(resources.embedder.batches) > 1
    assert max(resources.embedder.batches) <= 2
    large = Settings(_env_file=None, chunk_size=1000, chunk_overlap=10)
    second = process_document(data, "a.txt", "text/plain", large, resources)
    assert first.document_id == second.document_id
    assert second.chunk_count < first.chunk_count
    assert resources.store.client.count("test_chunks").count == second.chunk_count
