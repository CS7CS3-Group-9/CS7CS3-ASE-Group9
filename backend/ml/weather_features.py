from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.ml.weather_fetcher import refresh_forecast, should_refresh

_DEFAULT_WEATHER_PATH = "data/historical/weather_forecast.csv"

_CACHE: Optional[List[Tuple[datetime, Dict[str, float]]]] = None
_CACHE_PATH: Optional[Path] = None
_CACHE_MTIME: Optional[float] = None


@dataclass(frozen=True)
class WeatherFeatures:
    values: Dict[str, float]


def load_weather_features(now: datetime) -> Dict[str, float]:
    """
    Load nearest weather features for a timestamp from a cached CSV.
    Expected CSV columns: timestamp,<feature1>,<feature2>,...
    Returns empty dict if no data is available.
    """
    _maybe_refresh_forecast()
    records = _load_cache()
    if not records:
        return {}

    closest = _nearest_record(records, now)
    return closest[1] if closest else {}


def _load_cache() -> Optional[List[Tuple[datetime, Dict[str, float]]]]:
    global _CACHE, _CACHE_PATH, _CACHE_MTIME

    path = _resolve_weather_path()
    if path is None or not path.exists():
        _CACHE = None
        _CACHE_PATH = path
        _CACHE_MTIME = None
        return None

    mtime = path.stat().st_mtime
    if _CACHE is not None and path == _CACHE_PATH and mtime == _CACHE_MTIME:
        return _CACHE

    records: List[Tuple[datetime, Dict[str, float]]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts = _parse_timestamp(row.get("timestamp") or row.get("time"))
            if ts is None:
                continue
            features: Dict[str, float] = {}
            for k, v in row.items():
                if k in ("timestamp", "time"):
                    continue
                val = _parse_float(v)
                if val is not None:
                    features[f"weather_{k}"] = val
            if features:
                records.append((ts, features))

    _CACHE = records
    _CACHE_PATH = path
    _CACHE_MTIME = mtime
    return records


def _invalidate_cache() -> None:
    global _CACHE, _CACHE_PATH, _CACHE_MTIME
    _CACHE = None
    _CACHE_PATH = None
    _CACHE_MTIME = None


def _maybe_refresh_forecast() -> None:
    if not _auto_refresh_enabled():
        return
    path = _resolve_weather_path()
    if path is None:
        return
    if not should_refresh(path, refresh_hours=_refresh_hours()):
        return
    try:
        if refresh_forecast(path):
            _invalidate_cache()
    except Exception:
        pass


def refresh_weather_if_needed() -> None:
    _maybe_refresh_forecast()


def _auto_refresh_enabled() -> bool:
    raw = os.getenv("WEATHER_AUTO_REFRESH", "true").lower()
    return raw in ("1", "true", "yes", "y")


def _refresh_hours() -> int:
    raw = os.getenv("WEATHER_REFRESH_HOURS", "24").strip()
    try:
        hours = int(raw)
    except ValueError:
        hours = 24
    return max(1, hours)


def _nearest_record(
    records: List[Tuple[datetime, Dict[str, float]]],
    ts: datetime,
) -> Optional[Tuple[datetime, Dict[str, float]]]:
    best = None
    best_delta = None
    for r_ts, data in records:
        delta = abs((r_ts - ts).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = (r_ts, data)
    return best


def _resolve_weather_path() -> Optional[Path]:
    env_path = os.getenv("WEATHER_FORECAST_PATH")
    raw = env_path.strip() if env_path else _DEFAULT_WEATHER_PATH
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / path
    return path


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        ts = datetime.fromisoformat(value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        pass

    try:
        epoch = float(value)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except ValueError:
        return None


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None
