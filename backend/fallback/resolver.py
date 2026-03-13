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


def _cache_get_cached(cache: Any, adapter: Any, kwargs: dict) -> Optional[Any]:
    if hasattr(cache, "get_cached_for"):
        return cache.get_cached_for(adapter, **kwargs)
    return cache.get_cached(adapter.source_name())


def _cache_age_seconds(cache: Any, adapter: Any, kwargs: dict) -> Optional[float]:
    if hasattr(cache, "cached_age_seconds_for"):
        return cache.cached_age_seconds_for(adapter, **kwargs)
    if hasattr(cache, "cached_age_seconds"):
        return cache.cached_age_seconds(adapter.source_name())
    return None


def resolve_with_cache(
    adapter: Any,
    cache: AdapterCache,
    predictor: Optional[Callable[..., Optional[PredictionResult]]] = None,
    max_age_seconds: Optional[float] = None,
    **kwargs,
) -> ResolveResult:
    """
    Resolve an adapter call using cache and optional prediction.
    """
    if max_age_seconds is not None:
        age = _cache_age_seconds(cache, adapter, kwargs)
        if age is not None and age <= max_age_seconds:
            cached = _cache_get_cached(cache, adapter, kwargs)
            if cached is not None:
                return ResolveResult(
                    snapshot=cached,
                    status="cached",
                    detail={"cache_age_seconds": age, "max_age_seconds": max_age_seconds},
                )

    snapshot, status = cache.fetch_with_fallback(adapter, **kwargs)
    if status in ("live", "cached"):
        return ResolveResult(snapshot=snapshot, status=status, detail=None)

    # No live or cached data; attempt prediction from cached snapshot if provided
    cached_snapshot = _cache_get_cached(cache, adapter, kwargs)
    predictor_fn = predictor or _default_predictor
    prediction = _call_predictor(predictor_fn, adapter, cached_snapshot, max_age_seconds)

    if prediction is not None:
        return ResolveResult(
            snapshot=prediction.snapshot,
            status="predicted",
            detail={"confidence": prediction.confidence, "reason": prediction.reason},
        )

    return ResolveResult(snapshot=None, status="failed", detail=None)


def _default_predictor(
    adapter: Any,
    cached_snapshot: Optional[Any],
    max_age_seconds: Optional[float] = None,
) -> Optional[PredictionResult]:
    if max_age_seconds is None:
        return predict_snapshot(cached_snapshot)
    return predict_snapshot(cached_snapshot, max_age_seconds=max_age_seconds)


def _call_predictor(
    predictor_fn: Callable[..., Optional[PredictionResult]],
    adapter: Any,
    cached_snapshot: Optional[Any],
    max_age_seconds: Optional[float],
) -> Optional[PredictionResult]:
    try:
        return predictor_fn(adapter, cached_snapshot, max_age_seconds)
    except TypeError:
        pass
    except Exception:
        return None

    try:
        return predictor_fn(adapter, cached_snapshot)
    except TypeError:
        pass
    except Exception:
        return None

    try:
        if max_age_seconds is not None:
            return predictor_fn(cached_snapshot, max_age_seconds)
        return predictor_fn(cached_snapshot)
    except TypeError:
        try:
            return predictor_fn(cached_snapshot)
        except Exception:
            return None
    except Exception:
        return None
