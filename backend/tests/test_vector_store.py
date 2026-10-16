from uuid import uuid4
from unittest.mock import Mock

import pytest
from qdrant_client import models

from app.core.errors import IndexingError
from app.models.document import DocumentChunk
from app.rag.vector_store import QdrantVectorStore


def test_collection_setup_idempotent(resources) -> None:
    resources.store.ensure_collection(3)
    resources.store.ensure_collection(3)
    config = resources.store.client.get_collection("test_chunks").config.params.vectors
    assert config.size == 3
    assert config.distance == models.Distance.COSINE


def test_dimension_mismatch_preserves_collection(resources) -> None:
    resources.store.ensure_collection(3)
    with pytest.raises(IndexingError, match="dimension or distance") as error:
        resources.store.ensure_collection(4)
    assert error.value.status_code == 409
    assert resources.store.client.get_collection("test_chunks").config.params.vectors.size == 3


def test_insert_search_filter(resources) -> None:
    store = resources.store
    store.ensure_collection(3)
    documents = [str(uuid4()), str(uuid4())]
    for index, doc in enumerate(documents):
        chunk = DocumentChunk(chunk_id=str(uuid4()), text="Revenue" if index == 0 else "Cats",
            source_filename=f"{index}.txt", page_number=None, chunk_index=0)
        store.upsert([chunk], [[1., 0., .1] if index == 0 else [0., 1., .1]], doc, 3)
    hits = store.search([1., 0., .1], 5, None, 3)
    assert hits[0].document_id == documents[0]
    assert hits[0].score > hits[1].score
    assert [hit.document_id for hit in store.search([1., 0., .1], 5, documents[1], 3)] == [documents[1]]
    assert store.search([1., 0., .1], 5, str(uuid4()), 3) == []


@pytest.mark.parametrize("vectors, count", [([[1., 2.]], 1), ([], 1), ([[float("nan"), 0., 0.]], 1)])
def test_vector_validation(vectors, count) -> None:
    with pytest.raises(IndexingError):
        QdrantVectorStore.validate_vectors(vectors, count, 3)


@pytest.mark.parametrize("operation", ["collection_exists", "upsert", "query_points", "delete"])
def test_dependency_errors(operation: str) -> None:
    client = Mock()
    getattr(client, operation).side_effect = RuntimeError("secret server detail")
    store = QdrantVectorStore(client, "test")
    with pytest.raises(IndexingError) as error:
        if operation == "collection_exists":
            store.ensure_collection(3)
        elif operation == "upsert":
            store.upsert([], [], str(uuid4()), 3)
        elif operation == "delete":
            store.remove_stale_chunks(str(uuid4()), 1)
        else:
            store.search([1., 0., 0.], 5, None, 3)
    assert error.value.status_code == 503
    assert "secret" not in str(error.value)
