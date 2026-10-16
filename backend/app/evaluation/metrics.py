from math import log2
from statistics import mean


def retrieval_metrics(retrieved_ids: list[str], relevant_ids: set[str],
                      ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
    if not ks or any(k < 1 or k > 20 for k in ks):
        raise ValueError("K must be between 1 and 20")
    seen: set[str] = set()
    gains: list[int] = []
    for chunk_id in retrieved_ids[:max(ks)]:
        gains.append(int(chunk_id in relevant_ids and chunk_id not in seen))
        seen.add(chunk_id)
    metrics: dict[str, float] = {}
    for k in ks:
        hits = sum(gains[:k])
        metrics[f"recall_at_{k}"] = hits / len(relevant_ids) if relevant_ids else 0.0
        metrics[f"precision_at_{k}"] = hits / k
        dcg = sum(gain / log2(rank + 1) for rank, gain in enumerate(gains[:k], start=1))
        ideal = sum(1 / log2(rank + 1) for rank in range(1, min(k, len(relevant_ids)) + 1))
        metrics[f"ndcg_at_{k}"] = dcg / ideal if ideal else 0.0
    metrics["mrr"] = next((1 / rank for rank, gain in enumerate(gains, start=1) if gain), 0.0)
    return metrics


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    return {"count": len(values), "mean": mean(values) if values else None,
            "p50": percentile(values, .5), "p95": percentile(values, .95)}


def macro_average(rows: list[dict[str, float | bool | None]],
                  keys: list[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in keys:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        result[key] = mean(values) if values else None
    return result
