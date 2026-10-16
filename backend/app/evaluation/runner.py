from time import perf_counter

from app.core.config import Settings
from app.evaluation.answer_eval import GENERATION_KEYS, evaluate_answer
from app.evaluation.backend import EvaluationBackend
from app.evaluation.judge import Judge
from app.evaluation.metrics import latency_summary, macro_average, retrieval_metrics
from app.evaluation.models import CaseResult, EvaluationCase, EvaluationReport, JudgeInput
from app.evaluation.retrieval_eval import score_retrieval
from app.rag.prompt_builder import build_prompt
import json

JUDGE_KEYS = ["faithfulness", "answer_relevance", "correctness"]


async def evaluate(cases: list[EvaluationCase], backend: EvaluationBackend, settings: Settings,
                   dataset: str, dataset_sha256: str, retrieval_only: bool = False,
                   judge: Judge | None = None, ks: tuple[int, ...] = (1, 3, 5),
                   execution: str = "production_services", judge_mode: str = "disabled") -> EvaluationReport:
    if not cases:
        raise ValueError("At least one evaluation case is required")
    metric_keys = list(retrieval_metrics([], set(), ks))
    if retrieval_only and judge is not None:
        raise ValueError("Retrieval-only evaluation cannot use a judge")
    results: list[CaseResult] = []
    for case in cases:
        result = CaseResult(id=case.id, retrieval_scorable=bool(case.expected_chunk_ids))
        try:
            response = None
            if retrieval_only:
                retrieved = await backend.retrieve(case, max(ks))
            else:
                response = await backend.ask(case, max(ks))
                retrieved = backend.trace.retrieved
            result.retrieved_chunks = [chunk.model_dump(mode="json") for chunk in retrieved]
            result.retrieved_chunk_ids = [chunk.chunk_id for chunk in retrieved]
            result.retrieval = score_retrieval(case, retrieved, ks)
            if response is not None:
                prompt = build_prompt(case.question, retrieved, settings.rag_max_context_chars)
                result.generation = evaluate_answer(case, response, prompt)
                if judge is not None:
                    started = perf_counter()
                    try:
                        result.judge = await judge.evaluate(JudgeInput(question=case.question,
                            generated_answer=response.answer, reference_answer=case.reference_answer,
                            retrieved_context=json.loads(prompt.user_prompt)["sources"]))
                    except Exception:
                        result.status, result.error = "judge_error", "Judge evaluation failed"
                    finally:
                        result.latency_ms["judge"] = ((perf_counter() - started) * 1000
                            if judge_mode != "synthetic_fixture_scores" else None)
        except Exception:
            result.status, result.error = "error", "Retrieval or generation evaluation failed"
            # Preserve successful retrieval metrics even if subsequent generation failed.
            if backend.trace.retrieved:
                result.retrieved_chunk_ids = [chunk.chunk_id for chunk in backend.trace.retrieved]
                result.retrieval = score_retrieval(case, backend.trace.retrieved, ks)
        finally:
            trace = backend.trace
            result.latency_ms.update(retrieval=trace.retrieval_ms, embedding=trace.embedding_ms,
                                     generation=trace.generation_ms, rag=trace.rag_ms, dense=trace.dense_ms,
                                     bm25=trace.bm25_ms, hybrid=trace.hybrid_ms, reranking=trace.reranking_ms)
        results.append(result)
    retrieval_rows = [r.retrieval for r in results if r.retrieval_scorable and r.retrieval is not None]
    generation_rows = [r.generation for r in results if r.generation is not None]
    judge_rows = [r.judge.model_dump() for r in results if r.judge is not None]
    return EvaluationReport(dataset=dataset, dataset_sha256=dataset_sha256,
        mode="retrieval_only" if retrieval_only else "rag", execution=execution, judge_mode=judge_mode,
        num_queries=len(cases), num_succeeded=sum(r.status == "ok" for r in results),
        num_errors=sum(r.status != "ok" for r in results), num_retrieval_scored=len(retrieval_rows),
        num_generation_scored=len(generation_rows), num_judge_scored=len(judge_rows),
        configuration={"ks": list(ks), "retrieval_depth": max(ks), "embedding_model": settings.embedding_model_name,
                       "retrieval_strategy": settings.retrieval_strategy,
                       "candidate_count": settings.retrieval_candidate_count,
                       "rerank_candidate_count": settings.rerank_candidate_count,
                       "rrf_constant": settings.rrf_constant,
                       "reranker_model": settings.reranker_model_name,
                       "collection": settings.qdrant_collection_name, "context_chars": settings.rag_max_context_chars,
                       "generation_model": settings.llm_model if not retrieval_only else "not_used"},
        retrieval=macro_average(retrieval_rows, metric_keys),
        generation=macro_average(generation_rows, GENERATION_KEYS), judge=macro_average(judge_rows, JUDGE_KEYS),
        latency_ms={name: latency_summary([r.latency_ms[name] for r in results
                    if r.latency_ms.get(name) is not None]) for name in ("retrieval", "embedding", "dense", "bm25", "hybrid", "reranking", "generation", "rag", "judge")},
        cases=results)
