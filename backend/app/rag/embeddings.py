from collections.abc import Callable
from threading import Lock
from typing import Any, Protocol

import numpy as np

from app.core.errors import IndexingError


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_text(self, text: str) -> list[float]: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


def load_model(name: str) -> Any:
    # Import and download only when indexing or searching actually needs the model.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu", trust_remote_code=False)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, batch_size: int = 32,
                 loader: Callable[[str], Any] = load_model) -> None:
        if batch_size < 1:
            raise ValueError("Embedding batch size must be positive")
        self.model_name = model_name
        self.batch_size = batch_size
        self._loader = loader
        self._model: Any = None
        self._lock = Lock()

    def _load(self) -> Any:
        if self._model is None:
            try:
                self._model = self._loader(self.model_name)
            except Exception as exc:
                raise IndexingError("Embedding model could not be loaded. Check its name and local cache/network access.") from exc
        return self._model

    @property
    def dimension(self) -> int:
        with self._lock:
            try:
                dimension = self._load().get_embedding_dimension()
            except IndexingError:
                raise
            except Exception as exc:
                raise IndexingError("Embedding model dimension could not be determined.") from exc
            if not isinstance(dimension, int) or dimension < 1:
                raise IndexingError("Embedding model does not expose a valid vector dimension.")
            return dimension

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Embedding text must not be empty")
        with self._lock:
            model = self._load()
            try:
                vectors = np.asarray(model.encode(texts, batch_size=self.batch_size,
                    normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False))
                dimension = model.get_embedding_dimension()
                if vectors.shape != (len(texts), dimension) or not np.isfinite(vectors).all():
                    raise IndexingError("Embedding output has invalid dimensions or values.")
                return vectors.tolist()
            except IndexingError:
                raise
            except Exception as exc:
                raise IndexingError("Embedding computation failed.") from exc

    def tokenization_config(self) -> tuple[Any, int]:
        with self._lock:
            model = self._load()
            try:
                return model.tokenizer, int(model.max_seq_length)
            except Exception as exc:
                raise IndexingError("Embedding model tokenizer/input limit is unavailable.") from exc
