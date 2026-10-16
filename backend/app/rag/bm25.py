from collections import Counter
from collections.abc import Callable
from math import log1p
import re

from app.models.search import SearchResult


def lexical_tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25Retriever:
    """Lazy in-memory lexical index rebuilt from canonical chunk payloads."""
    def __init__(self, load_chunks: Callable[[], list[SearchResult]], k1: float = 1.5,
                 b: float = .75) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Require k1 > 0 and 0 <= b <= 1")
        self.load_chunks, self.k1, self.b = load_chunks, k1, b
        self._documents: list[SearchResult] | None = None
        self._terms: list[Counter[str]] = []
        self._df: Counter[str] = Counter()
        self._lengths: list[int] = []
        self._average_length = 0.0

    def invalidate(self) -> None:
        self._documents = None

    def _ensure_index(self) -> None:
        if self._documents is not None:
            return
        documents = self.load_chunks()
        terms = [Counter(lexical_tokens(doc.text)) for doc in documents]
        df: Counter[str] = Counter()
        for counts in terms:
            df.update(counts.keys())
        lengths = [sum(counts.values()) for counts in terms]
        self._terms, self._df, self._lengths = terms, df, lengths
        self._average_length = sum(lengths) / len(lengths) if lengths else 0.0
        self._documents = documents

    def search(self, query: str, top_k: int, document_id: str | None = None) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        terms = sorted(set(lexical_tokens(query)))
        if not terms:
            return []
        self._ensure_index()
        documents = self._documents or []
        if not documents or not self._average_length:
            return []
        results: list[SearchResult] = []
        for index, doc in enumerate(documents):
            if document_id is not None and doc.document_id != document_id:
                continue
            score = 0.0
            normalization = self.k1 * (1 - self.b + self.b * self._lengths[index] / self._average_length)
            for term in terms:
                tf = self._terms[index][term]
                if tf:
                    idf = log1p((len(documents) - self._df[term] + .5) / (self._df[term] + .5))
                    score += idf * tf * (self.k1 + 1) / (tf + normalization)
            if score > 0:
                results.append(doc.model_copy(update={"score": score}))
        return sorted(results, key=lambda item: (-item.score, item.chunk_id))[:top_k]
