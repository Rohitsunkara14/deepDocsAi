from dataclasses import dataclass, field
from copy import copy
from time import perf_counter
from typing import Protocol

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.evaluation.models import EvaluationCase
from app.models.rag import AskRequest, AskResponse
from app.models.search import SearchRequest, SearchResult
from app.rag.embeddings import Embedder
from app.rag.llm import LLM
from app.rag.retrieval import Retriever, RetrievalOutcome
from app.services.indexing import IndexingResources
from app.services.rag_service import ask_question
from app.services.search_service import search_documents


@dataclass
class Trace:
    retrieved: list[SearchResult] = field(default_factory=list)
    retrieval_ms: float | None = None
    embedding_ms: float | None = None
    generation_ms: float | None = None
    rag_ms: float | None = None
    dense_ms: float | None = None
    bm25_ms: float | None = None
    hybrid_ms: float | None = None
    reranking_ms: float | None = None


class EvaluationBackend(Protocol):
    trace: Trace
    async def retrieve(self, case: EvaluationCase, depth: int) -> list[SearchResult]: ...
    async def ask(self, case: EvaluationCase, depth: int) -> AskResponse: ...


class RecordingRetriever:
    def __init__(self, wrapped: Retriever, trace: Trace) -> None:
        self.wrapped, self.trace = wrapped, trace

    def retrieve(self, query: str, top_k: int, document_id: str | None = None,
                 strategy: str = "dense") -> RetrievalOutcome:
        outcome = self.wrapped.retrieve(query, top_k, document_id, strategy)
        self.trace.retrieved = outcome.results
        for name, value in outcome.latency_ms.items():
            setattr(self.trace, name + "_ms", value)
        return outcome


class MeasuredRetrievalLock:
    """Production search's existing lock delimits its complete synchronous stage."""
    def __init__(self, resources: IndexingResources, trace: Trace) -> None:
        self.lock, self.trace = resources.lock, trace
        self.started = 0.0

    def __enter__(self) -> None:
        self.started = perf_counter()
        self.lock.__enter__()

    def __exit__(self, *args: object) -> None:
        self.lock.__exit__(*args)
        self.trace.retrieval_ms = (perf_counter() - self.started) * 1000


class MeasuredLLM:
    def __init__(self, wrapped: LLM, trace: Trace) -> None:
        self.wrapped, self.trace = wrapped, trace

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        started = perf_counter()
        try:
            return await self.wrapped.generate(system_prompt, user_prompt)
        finally:
            self.trace.generation_ms = (perf_counter() - started) * 1000


class ServiceBackend:
    def __init__(self, settings: Settings, resources: IndexingResources, llm: LLM | None = None) -> None:
        self.settings, self.resources, self.llm = settings, resources, llm
        self.trace = Trace()

    def _instrument(self) -> IndexingResources:
        self.trace = Trace()
        measured = copy(self.resources)
        measured.settings = self.settings
        measured.retriever = RecordingRetriever(self.resources.retriever, self.trace)
        measured.lock = MeasuredRetrievalLock(self.resources, self.trace)
        return measured

    async def retrieve(self, case: EvaluationCase, depth: int) -> list[SearchResult]:
        measured = self._instrument()
        response = await run_in_threadpool(search_documents,
            SearchRequest(query=case.question, top_k=depth, document_id=case.filter_document_id), measured)
        return response.results

    async def ask(self, case: EvaluationCase, depth: int) -> AskResponse:
        if self.llm is None:
            raise ValueError("Generation backend requires an LLM")
        measured = self._instrument()
        started = perf_counter()
        try:
            return await ask_question(AskRequest(question=case.question, top_k=depth,
                document_id=case.filter_document_id), self.settings, measured, MeasuredLLM(self.llm, self.trace))
        finally:
            self.trace.rag_ms = (perf_counter() - started) * 1000
