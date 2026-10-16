from math import log2

import pytest

from app.evaluation.metrics import retrieval_metrics, latency_summary, percentile


def test_manual_multiple_relevant() -> None:
    values = retrieval_metrics(["noise", "a", "b"], {"a", "b"})
    assert values["recall_at_1"] == 0
    assert values["recall_at_3"] == 1
    assert values["precision_at_3"] == pytest.approx(2/3)
    assert values["precision_at_5"] == .4
    assert values["mrr"] == .5
    assert values["ndcg_at_3"] == pytest.approx((1/log2(3) + 1/log2(4)) / (1 + 1/log2(3)))


def test_short_result_denominator() -> None:
    result = retrieval_metrics(["a"], {"a", "b"})
    assert result["recall_at_5"] == .5
    assert result["precision_at_5"] == .2
    assert result["mrr"] == 1


def test_duplicate_results_do_not_inflate() -> None:
    result = retrieval_metrics(["a", "a", "b"], {"a", "b"})
    assert result["precision_at_3"] == pytest.approx(2/3)
    assert result["recall_at_3"] == 1
    assert result["ndcg_at_3"] < 1


@pytest.mark.parametrize("returned, expected", [([], {"a"}), (["b"], {"a"}), (["a"], set()), ([], set())])
def test_zero_relevance(returned, expected) -> None:
    assert all(value == 0 for value in retrieval_metrics(returned, expected).values())


def test_mrr_at_third_rank_and_cutoff() -> None:
    assert retrieval_metrics(["x", "y", "a"], {"a"})["mrr"] == pytest.approx(1/3)
    assert retrieval_metrics(["x"] * 5 + ["a"], {"a"})["mrr"] == 0


def test_perfect_ranking() -> None:
    metrics = retrieval_metrics(["a", "b", "c", "d", "e"], {"a", "b", "c", "d", "e"})
    assert metrics["ndcg_at_5"] == 1
    assert metrics["precision_at_5"] == 1
    assert metrics["recall_at_1"] == .2


@pytest.mark.parametrize("ks", [(), (0,), (21,)])
def test_invalid_k(ks) -> None:
    with pytest.raises(ValueError):
        retrieval_metrics([], set(), ks)


def test_latency_interpolation() -> None:
    values = latency_summary([10., 20., 30., 40.])
    assert values == {"count": 4, "mean": 25., "p50": 25., "p95": 38.5}
    assert latency_summary([]) == {"count": 0, "mean": None, "p50": None, "p95": None}
    assert percentile([9.], .95) == 9.
