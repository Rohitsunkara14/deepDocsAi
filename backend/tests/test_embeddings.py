from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import numpy as np
import pytest

from app.core.errors import IndexingError
from app.rag.embeddings import SentenceTransformerEmbedder


class FakeModel:
    def get_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, **kwargs):
        assert kwargs["batch_size"] == 2
        assert kwargs["normalize_embeddings"] is True
        return np.array([[1., 0., 0.] for _ in texts])


def test_shapes_batching_and_single_load() -> None:
    loader = Mock(return_value=FakeModel())
    embedder = SentenceTransformerEmbedder("fake", 2, loader)
    assert embedder.dimension == 3
    assert embedder.embed_text("text") == [1., 0., 0.]
    vectors = embedder.embed_texts(["a", "b", "c"])
    assert np.shape(vectors) == (3, 3)
    assert embedder.embed_texts(["a", "b", "c"]) == vectors
    loader.assert_called_once_with("fake")


def test_concurrent_load_once() -> None:
    loader = Mock(return_value=FakeModel())
    embedder = SentenceTransformerEmbedder("fake", 2, loader)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(embedder.embed_text, ["text"] * 8)) == [[1., 0., 0.]] * 8
    assert loader.call_count == 1


def test_empty_does_not_load() -> None:
    loader = Mock()
    embedder = SentenceTransformerEmbedder("fake", 2, loader)
    assert embedder.embed_texts([]) == []
    with pytest.raises(ValueError):
        embedder.embed_text(" ")
    loader.assert_not_called()


def test_loading_failure() -> None:
    embedder = SentenceTransformerEmbedder("fake", loader=Mock(side_effect=OSError("private detail")))
    with pytest.raises(IndexingError, match="could not be loaded"):
        embedder.embed_text("hello")


@pytest.mark.parametrize("result", [np.zeros((1, 2)), np.array([[float("nan"), 1., 2.]])])
def test_invalid_vectors(result) -> None:
    model = Mock()
    model.get_embedding_dimension.return_value = 3
    model.encode.return_value = result
    embedder = SentenceTransformerEmbedder("fake", loader=Mock(return_value=model))
    with pytest.raises(IndexingError, match="invalid dimensions"):
        embedder.embed_text("hello")


def test_encode_failure() -> None:
    model = Mock()
    model.encode.side_effect = RuntimeError("private")
    embedder = SentenceTransformerEmbedder("fake", loader=Mock(return_value=model))
    with pytest.raises(IndexingError, match="computation failed"):
        embedder.embed_text("hello")
