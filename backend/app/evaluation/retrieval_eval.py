from app.evaluation.metrics import retrieval_metrics
from app.evaluation.models import EvaluationCase
from app.models.search import SearchResult


def score_retrieval(case: EvaluationCase, results: list[SearchResult],
                    ks: tuple[int, ...]) -> dict[str, float]:
    # Expected document is a judgment, never an implicit search filter (no label leakage).
    ids = [result.chunk_id if case.expected_document_id is None or
           result.document_id == str(case.expected_document_id) else "" for result in results]
    return retrieval_metrics(ids, {str(chunk) for chunk in case.expected_chunk_ids}, ks)
