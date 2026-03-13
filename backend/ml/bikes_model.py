from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from backend.ml.weather_features import load_weather_features

_DEFAULT_MODEL_PATH = "backend/ml/artifacts/bikes_model.joblib"

_MODEL: Optional["BikesModelBundle"] = None
_MODEL_PATH: Optional[Path] = None
_MODEL_MTIME: Optional[float] = None


@dataclass
class BikesModelBundle:
    model: Any
    feature_columns: List[str]
    stations: List[Dict[str, Any]]
    weather_feature_columns: List[str]
    trained_at: Optional[str] = None


def load_model() -> Optional[BikesModelBundle]:
    global _MODEL, _MODEL_PATH, _MODEL_MTIME

    path = _resolve_model_path()
    if path is None or not path.exists():
        _MODEL = None
        _MODEL_PATH = path
        _MODEL_MTIME = None
        return None

    mtime = path.stat().st_mtime
    if _MODEL is not None and path == _MODEL_PATH and mtime == _MODEL_MTIME:
        return _MODEL

    bundle = joblib.load(path)
    if not isinstance(bundle, BikesModelBundle):
        # Backwards compatibility: allow dict bundles
        bundle = BikesModelBundle(
            model=bundle["model"],
            feature_columns=bundle["feature_columns"],
            stations=bundle["stations"],
            weather_feature_columns=bundle.get("weather_feature_columns", []),
            trained_at=bundle.get("trained_at"),
        )

    _MODEL = bundle
    _MODEL_PATH = path
    _MODEL_MTIME = mtime
    return bundle


def predict_stations(now: Optional[datetime] = None) -> Optional[List[dict]]:
    bundle = load_model()
    if bundle is None:
        return None

    now_ts = now or datetime.now(timezone.utc)
    weather = load_weather_features(now_ts)
    feature_rows = []

    for station in bundle.stations:
        row = _build_feature_row(now_ts, station, weather, bundle.weather_feature_columns)
        feature_rows.append([row.get(col, 0.0) for col in bundle.feature_columns])

    if not feature_rows:
        return None

    X = np.asarray(feature_rows, dtype=float)
    preds = bundle.model.predict(X)

    adjust = _weather_adjustment_enabled()
    output: List[dict] = []
    for station, pred in zip(bundle.stations, preds):
        capacity = station.get("capacity")
        bikes = max(0, int(round(float(pred))))
        if capacity is not None:
            bikes = min(bikes, int(capacity))

        adjustment_factor = None
        adjustment_reason = None
        if adjust and weather:
            bikes, adjustment_factor, adjustment_reason = _apply_weather_adjustment(bikes, capacity, weather)

        docks = max(0, int((capacity or 0) - bikes)) if capacity is not None else 0

        output.append(
            {
                "station_id": station.get("station_id"),
                "name": station.get("name") or f"Station {station.get('station_id')}",
                "lat": station.get("lat"),
                "lon": station.get("lon"),
                "free_bikes": bikes,
                "empty_slots": docks,
                "total": int(capacity) if capacity is not None else bikes + docks,
                "prediction_reason": "ml_model",
                "adjustment_factor": adjustment_factor,
                "adjustment_reason": adjustment_reason,
            }
        )

    return output


def _build_feature_row(
    now: datetime,
    station: Dict[str, Any],
    weather: Dict[str, float],
    weather_columns: List[str],
) -> Dict[str, float]:
    hour = float(now.hour)
    weekday = float(now.weekday())
    month = float(now.month)
    day_of_year = float(now.timetuple().tm_yday)
    is_weekend = 1.0 if weekday >= 5 else 0.0

    row = {
        "hour": hour,
        "weekday": weekday,
        "month": month,
        "day_of_year": day_of_year,
        "is_weekend": is_weekend,
        "lat": float(station.get("lat") or 0.0),
        "lon": float(station.get("lon") or 0.0),
        "capacity": float(station.get("capacity") or 0.0),
    }

    for key in weather_columns:
        row[key] = float(weather.get(key, 0.0))

    return row


def _weather_adjustment_enabled() -> bool:
    raw = os.getenv("BIKES_WEATHER_ADJUSTMENT", "true").lower()
    return raw in ("1", "true", "yes", "y")


def _apply_weather_adjustment(
    bikes: int,
    capacity: Optional[float],
    weather: Dict[str, float],
) -> tuple[int, Optional[float], Optional[str]]:
    rain = weather.get("weather_rain")
    if rain is None:
        rain = weather.get("weather_precipitation")
    if rain is None:
        rain = 0.0

    factor = 1.0
    reason = None
    if rain >= 5.0:
        factor = 0.7
        reason = "heavy_rain"
    elif rain >= 2.0:
        factor = 0.8
        reason = "moderate_rain"
    elif rain > 0.0:
        factor = 0.9
        reason = "light_rain"

    if factor != 1.0:
        bikes = int(round(bikes * factor))
        bikes = max(0, bikes)
        if capacity is not None:
            bikes = min(bikes, int(capacity))

    return bikes, (factor if factor != 1.0 else None), reason


def _resolve_model_path() -> Optional[Path]:
    env_path = os.getenv("BIKES_MODEL_PATH")
    raw = env_path.strip() if env_path else _DEFAULT_MODEL_PATH
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / path
    return path
