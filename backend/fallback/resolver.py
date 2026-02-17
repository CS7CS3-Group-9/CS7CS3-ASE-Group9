from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from fallback.cache import AdapterCache
from fallback.predictor import PredictionResult, predict_snapshot


@dataclass(frozen=True)
class ResolveResult:
    """
    Final decision for an adapter fetch:
    - snapshot: the chosen snapshot (if any)
    - status: "live", "cached", "predicted", or "failed"
    - detail: optional extra info (e.g., confidence)
    """

    snapshot: Optional[Any]
    status: str
    detail: Optional[dict]


def choose_snapshot(
    live: Optional[Any],
    cached: Optional[Any],
    predicted: Optional[Any],
) -> Tuple[Optional[Any], str]:
    """
    Priority order: live > cached > predicted.
    """
    if live is not None:
        return live, "live"
    if cached is not None:
        return cached, "cached"
    if predicted is not None:
        return predicted, "predicted"
    return None, "failed"


def resolve_with_cache(
    adapter: Any,
    cache: AdapterCache,
    predictor: Optional[Callable[[Any], Optional[PredictionResult]]] = None,
    **kwargs,
) -> ResolveResult:
    """
    Resolve an adapter call using cache and optional prediction.
    """
    snapshot, status = cache.fetch_with_fallback(adapter, **kwargs)
    if status in ("live", "cached"):
        return ResolveResult(snapshot=snapshot, status=status, detail=None)

    # No live or cached data; attempt prediction from cached snapshot if provided
    cached_snapshot = cache.get_cached(adapter.source_name())
    predictor_fn = predictor or predict_snapshot
    prediction = predictor_fn(cached_snapshot) if cached_snapshot is not None else None

    if prediction is not None:
        return ResolveResult(
            snapshot=prediction.snapshot,
            status="predicted",
            detail={"confidence": prediction.confidence, "reason": prediction.reason},
        )

    return ResolveResult(snapshot=None, status="failed", detail=None)
