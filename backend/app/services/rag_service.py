import asyncio
import json
import logging
import re
from time import perf_counter

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import LLMError
from app.core.observability import record_metrics
from app.models.rag import AskRequest, AskResponse, Citation
from app.models.search import SearchRequest
from app.rag.llm import LLM
from app.rag.prompt_builder import build_prompt, NO_RESULTS_ANSWER, INSUFFICIENT_CONTEXT_ANSWER
from app.services.indexing import IndexingResources
from app.services.search_service import search_documents

logger = logging.getLogger("uvicorn.error.deepdocs.rag")


def map_citations(answer: str, sources: list[Citation]) -> list[Citation]:
    if answer == INSUFFICIENT_CONTEXT_ANSWER:
        return []
    available = {str(source.source_number): source for source in sources}
    markers = re.findall(r"\[([0-9]+)\]", answer)
    # Citation checks validate provenance, not whether each claim is entailed.
    if not markers or any(marker not in available for marker in markers):
        raise LLMError("LLM response did not contain valid source citations.")
    other_numeric_brackets = re.findall(r"\[((?:Source\s+)?[0-9][^\]]*)\]", answer, flags=re.IGNORECASE)
    if any(marker not in available for marker in other_numeric_brackets):
        raise LLMError("LLM response contained unsupported citation markers.")
    return [available[marker] for marker in dict.fromkeys(markers)]


async def ask_question(request: AskRequest, settings: Settings,
                       resources: IndexingResources, llm: LLM) -> AskResponse:
    top_k = request.top_k if request.top_k is not None else settings.rag_top_k_default
    logger.info(json.dumps({"event": "rag_request_received", "top_k": top_k,
                            "document_filter": request.document_id is not None}))
    retrieved = await run_in_threadpool(search_documents,
        SearchRequest(query=request.question, top_k=top_k, document_id=request.document_id), resources)
    logger.info(json.dumps({"event": "rag_retrieved", "chunk_count": len(retrieved.results)}))
    if not retrieved.results:
        return AskResponse(question=request.question, answer=NO_RESULTS_ANSWER, citations=[])
    prompt = build_prompt(request.question, retrieved.results, settings.rag_max_context_chars)
    if not prompt.citations:
        return AskResponse(question=request.question, answer=INSUFFICIENT_CONTEXT_ANSWER, citations=[])
    started = perf_counter()
    success = False
    try:
        # Overall deadline complements the adapter's HTTP phase timeouts.
        async with asyncio.timeout(settings.llm_timeout_seconds):
            answer = await llm.generate(prompt.system_prompt, prompt.user_prompt)
        if not isinstance(answer, str) or not answer.strip():
            raise LLMError("LLM provider returned a malformed response.")
        answer = answer.strip()
        citations = map_citations(answer, prompt.citations)
        success = True
        return AskResponse(question=request.question, answer=answer, citations=citations)
    except LLMError:
        raise
    except TimeoutError as exc:
        raise LLMError("LLM request timed out. Try again later.") from exc
    except Exception as exc:
        raise LLMError("LLM generation failed. Try again later.") from exc
    finally:
        record_metrics(generation_latency_ms=round((perf_counter() - started) * 1000, 3), generation_success=success)
        logger.info(json.dumps({"event": "llm_generation", "provider": settings.llm_provider,
            "model": settings.llm_model, "latency_ms": round((perf_counter() - started) * 1000, 2),
            "success": success}))
