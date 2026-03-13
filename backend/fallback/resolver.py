from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from backend.fallback.cache import AdapterCache
from backend.fallback.predictor import PredictionResult, predict_snapshot


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
    predictor: Optional[Callable[[Any, Optional[Any]], Optional[PredictionResult]]] = None,
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
    predictor_fn = predictor or _default_predictor
    prediction = _call_predictor(predictor_fn, adapter, cached_snapshot)

    if prediction is not None:
        return ResolveResult(
            snapshot=prediction.snapshot,
            status="predicted",
            detail={"confidence": prediction.confidence, "reason": prediction.reason},
        )

    return ResolveResult(snapshot=None, status="failed", detail=None)


def _default_predictor(adapter: Any, cached_snapshot: Optional[Any]) -> Optional[PredictionResult]:
    return predict_snapshot(cached_snapshot)


def _call_predictor(
    predictor_fn: Callable[..., Optional[PredictionResult]],
    adapter: Any,
    cached_snapshot: Optional[Any],
) -> Optional[PredictionResult]:
    try:
        return predictor_fn(adapter, cached_snapshot)
    except TypeError:
        # Backwards-compatible path: predictor expects only cached_snapshot
        return predictor_fn(cached_snapshot)
    except Exception:
        return None
