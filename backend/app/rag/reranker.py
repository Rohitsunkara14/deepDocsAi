from collections.abc import Callable
from threading import Lock
from typing import Any, Protocol

import numpy as np

from app.core.errors import IndexingError
from app.models.search import SearchResult


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]: ...


def load_cross_encoder(name: str) -> Any:
    from sentence_transformers import CrossEncoder
    import torch

    model = CrossEncoder(name, device="cpu", trust_remote_code=False)
    # Own CPU storage avoids native linear-layer faults observed with mmap-backed
    # safetensors on macOS. Values and model scoring remain unchanged.
    with torch.no_grad():
        for parameter in model.model.parameters():
            parameter.data = parameter.data.clone()
    return model


class CrossEncoderReranker:
    def __init__(self, model_name: str, batch_size: int = 16,
                 loader: Callable[[str], Any] = load_cross_encoder) -> None:
        self.model_name, self.batch_size, self.loader = model_name, batch_size, loader
        self._model: Any = None
        self._lock = Lock()

    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
        if not candidates or not query.strip():
            return []
        with self._lock:
            try:
                if self._model is None:
                    self._model = self.loader(self.model_name)
                scores = np.asarray(self._model.predict([(query, item.text) for item in candidates],
                    batch_size=self.batch_size, show_progress_bar=False))
                if scores.shape not in {(len(candidates),), (len(candidates), 1)} or not np.isfinite(scores).all():
                    raise ValueError("Invalid relevance score output")
                scored = [item.model_copy(update={"score": float(score)})
                          for item, score in zip(candidates, scores.reshape(-1), strict=True)]
                return sorted(scored, key=lambda item: (-item.score, item.chunk_id))[:top_k]
            except Exception as exc:
                raise IndexingError("Cross-encoder reranking failed. Check the model and its local cache; no fallback was substituted.") from exc
