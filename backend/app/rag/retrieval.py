from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings
from app.models.search import SearchResult
from app.rag.bm25 import BM25Retriever
from app.rag.embeddings import Embedder
from app.rag.reranker import Reranker
from app.rag.vector_store import QdrantVectorStore

STRATEGIES = ("dense", "bm25", "hybrid", "hybrid_rerank")


@dataclass
class RetrievalOutcome:
    results: list[SearchResult]
    latency_ms: dict[str, float]


def reciprocal_rank_fusion(rankings: list[list[SearchResult]], constant: int = 60) -> list[SearchResult]:
    if constant < 1:
        raise ValueError("RRF constant must be positive")
    scores: dict[str, float] = {}
    sources: dict[str, SearchResult] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, item in enumerate(ranking, start=1):
            if item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            sources.setdefault(item.chunk_id, item)
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1 / (constant + rank)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [sources[chunk_id].model_copy(update={"score": scores[chunk_id]}) for chunk_id in ordered]


class Retriever:
    def __init__(self, embedder: Embedder, store: QdrantVectorStore, bm25: BM25Retriever,
                 reranker: Reranker, settings: Settings) -> None:
        self.embedder, self.store, self.bm25 = embedder, store, bm25
        self.reranker, self.settings = reranker, settings

    def retrieve(self, query: str, top_k: int, document_id: str | None = None,
                 strategy: str = "dense") -> RetrievalOutcome:
        if strategy not in STRATEGIES:
            raise ValueError("Unknown retrieval strategy")
        times: dict[str, float] = {}
        hybrid_started = perf_counter()
        def dense(count: int) -> list[SearchResult]:
            started = perf_counter()
            embed_start = perf_counter()
            dimension = self.embedder.dimension
            dimension_ms = (perf_counter() - embed_start) * 1000
            self.store.ensure_collection(dimension)
            embed_start = perf_counter()
            vector = self.embedder.embed_text(query)
            times["embedding"] = dimension_ms + (perf_counter() - embed_start) * 1000
            results = self.store.search(vector, count, document_id, dimension)
            times["dense"] = (perf_counter() - started) * 1000
            return results
        def lexical(count: int) -> list[SearchResult]:
            started = perf_counter()
            results = self.bm25.search(query, count, document_id)
            times["bm25"] = (perf_counter() - started) * 1000
            return results
        if strategy == "dense":
            results = dense(top_k)
        elif strategy == "bm25":
            results = lexical(top_k)
        else:
            count = max(top_k, self.settings.retrieval_candidate_count, self.settings.rerank_candidate_count)
            results = reciprocal_rank_fusion([dense(count), lexical(count)], self.settings.rrf_constant)
            times["hybrid"] = (perf_counter() - hybrid_started) * 1000
            if strategy == "hybrid_rerank":
                candidates = results[:max(top_k, self.settings.rerank_candidate_count)]
                started = perf_counter()
                results = self.reranker.rerank(query, candidates, top_k)
                times["reranking"] = (perf_counter() - started) * 1000
            else:
                results = results[:top_k]
        return RetrievalOutcome(results, times)
