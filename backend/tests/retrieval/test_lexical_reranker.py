from unittest.mock import Mock

import numpy as np
import pytest

from app.core.errors import IndexingError
from app.models.search import SearchResult
from app.rag.bm25 import BM25Retriever
from app.rag.reranker import CrossEncoderReranker
from app.rag.retrieval import reciprocal_rank_fusion


def chunk(id: str, text: str, document: str = "doc") -> SearchResult:
    return SearchResult(chunk_id=id, document_id=document, text=text, source_filename=id+".txt",
                        page_number=None, chunk_index=0, score=.5)


def test_bm25_rank_filter_and_exact_words() -> None:
    documents = [chunk("a", "quasar error code ZX91", "first"),
                 chunk("b", "other unrelated data", "second"),
                 chunk("c", "quasars are plural", "second")]
    retriever = BM25Retriever(lambda: documents)
    assert [r.chunk_id for r in retriever.search("QUASAR ZX91", 5)] == ["a"]
    assert retriever.search("quasar", 5, "second") == []
    assert retriever.search("quas", 5) == []


def test_bm25_tf_and_length_normalization() -> None:
    retriever = BM25Retriever(lambda: [chunk("a", "risk risk risk"),
        chunk("b", "risk " + "noise " * 100), chunk("c", "no match")])
    results = retriever.search("risk", 5)
    assert [r.chunk_id for r in results] == ["a", "b"]
    assert results[0].score > results[1].score > 0


def test_empty_query_and_index_rebuild() -> None:
    loader = Mock(return_value=[chunk("a", "risk")])
    retriever = BM25Retriever(loader)
    assert retriever.search("!?", 5) == []
    loader.assert_not_called()
    retriever.search("risk", 5)
    retriever.search("risk", 5)
    assert loader.call_count == 1
    loader.return_value = [chunk("b", "risk")]
    retriever.invalidate()
    assert retriever.search("risk", 5)[0].chunk_id == "b"


def test_rrf_no_raw_score_mixing_or_duplicate_credit() -> None:
    a, b, c = chunk("a", "a"), chunk("b", "b"), chunk("c", "c")
    a.score = -1000
    b.score = 99999
    fused = reciprocal_rank_fusion([[a, a, b], [b, c, a]])
    scores = {item.chunk_id: item.score for item in fused}
    assert len(fused) == 3
    assert scores["a"] == pytest.approx(1/61 + 1/63)
    assert scores["b"] == pytest.approx(1/63 + 1/61)
    assert scores["c"] == pytest.approx(1/62)
    assert fused[0].chunk_id == "a"


def test_rrf_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == []


def test_rerank_lazy_load_batch_and_metadata() -> None:
    model = Mock()
    model.predict.return_value = np.array([.2, .9])
    loader = Mock(return_value=model)
    reranker = CrossEncoderReranker("fake", batch_size=2, loader=loader)
    assert reranker.rerank("q", [], 5) == []
    loader.assert_not_called()
    candidates = [chunk("a", "irrelevant"), chunk("b", "relevant")]
    results = reranker.rerank("q", candidates, 1)
    assert results[0].chunk_id == "b"
    assert results[0].source_filename == "b.txt"
    assert results[0].score == .9
    assert candidates[1].score == .5
    reranker.rerank("q", candidates, 1)
    loader.assert_called_once_with("fake")
    assert model.predict.call_args.kwargs["batch_size"] == 2
    assert model.predict.call_args.args[0] == [("q", "irrelevant"), ("q", "relevant")]


@pytest.mark.parametrize("scores", [np.array([np.nan]), np.array([[1, 2]]), np.array([])])
def test_bad_reranker_output(scores) -> None:
    model = Mock()
    model.predict.return_value = scores
    with pytest.raises(IndexingError, match="no fallback"):
        CrossEncoderReranker("fake", loader=lambda _: model).rerank("q", [chunk("a", "a")], 1)


def test_unavailable_reranker() -> None:
    with pytest.raises(IndexingError) as error:
        CrossEncoderReranker("fake", loader=Mock(side_effect=OSError("SECRET"))).rerank("q", [chunk("a", "a")], 1)
    assert "SECRET" not in str(error.value)
