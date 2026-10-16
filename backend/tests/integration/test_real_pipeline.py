"""Opt-in real-model/Qdrant check; excluded unless explicitly enabled."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.main import create_app
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.vector_store import QdrantVectorStore
from app.services.indexing import IndexingResources
from tests.conftest import make_pdf

pytestmark = pytest.mark.skipif(os.getenv("RUN_EXTERNAL_INTEGRATION") != "1",
    reason="Opt-in real model test; normal tests never download a model")


def test_real_pipeline() -> None:
    url = os.getenv("QDRANT_TEST_URL")
    client = QdrantClient(url=url) if url else QdrantClient(":memory:")
    collection = "deepdocs_test_" + uuid4().hex
    settings = Settings(_env_file=None, qdrant_collection_name=collection)
    embedder = SentenceTransformerEmbedder(settings.embedding_model_name)
    resources = IndexingResources(embedder, QdrantVectorStore(client, collection))
    with TestClient(create_app(settings, resources)) as api:
        try:
            assert embedder.dimension == 384
            ids = []
            for filename, data, mime in [
                ("finance.txt", b"Annual revenue grew twenty percent as sales increased.", "text/plain"),
                ("pets.pdf", make_pdf(["Cats are household pets.", "Veterinary care keeps animals healthy."]), "application/pdf"),
            ]:
                response = api.post("/documents/upload", files={"file": (filename, data, mime)})
                assert response.status_code == 200, response.text
                ids.append(response.json()["document_id"])
            response = api.post("/search", json={"query": "How much did revenue grow?", "top_k": 1})
            assert response.status_code == 200
            assert response.json()["results"][0]["document_id"] == ids[0]
            filtered = api.post("/search", json={"query": "animal health", "document_id": ids[1]})
            assert filtered.status_code == 200
            results = filtered.json()["results"]
            assert results and all(hit["document_id"] == ids[1] for hit in results)
            assert results[0]["page_number"] == 2
        finally:
            if client.collection_exists(collection):
                client.delete_collection(collection)
