from time import perf_counter
from app.core.observability import record_metrics

from app.models.search import SearchRequest, SearchResponse
from app.services.indexing import IndexingResources


def search_documents(request: SearchRequest, resources: IndexingResources) -> SearchResponse:
    started = perf_counter()
    try:
        with resources.lock:
            outcome = resources.retriever.retrieve(request.query, request.top_k,
                str(request.document_id) if request.document_id else None,
                strategy=resources.settings.retrieval_strategy)
            record_metrics(retrieved_chunk_count=len(outcome.results))
            return SearchResponse(query=request.query, results=outcome.results)
    finally:
        record_metrics(retrieval_latency_ms=round((perf_counter() - started) * 1000, 3))
