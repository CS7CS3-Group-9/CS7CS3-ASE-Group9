from __future__ import annotations

from typing import Optional, Any

from backend.fallback.predictor import PredictionResult, predict_snapshot
from backend.fallback.bikes_predictor import predict_bikes_snapshot
from backend.fallback.bikes_station_predictor import predict_bike_stations


def default_predictor(adapter: Any, cached_snapshot: Optional[Any]) -> Optional[PredictionResult]:
    """
    Default predictor strategy:
      - Bikes: attempt historical prediction (works without cache)
      - All others: fall back to cached-based predictor
    """
    try:
        if adapter is not None and getattr(adapter, "source_name", None):
            source = adapter.source_name()
            if source == "bikes":
                predicted = predict_bikes_snapshot(cached_snapshot)
                if predicted is not None:
                    return predicted
            if source == "bikes_stations":
                predicted = predict_bike_stations()
                if predicted is not None:
                    return predicted
    except Exception:
        # Fall back to cached snapshot prediction
        pass

    return predict_snapshot(cached_snapshot)
