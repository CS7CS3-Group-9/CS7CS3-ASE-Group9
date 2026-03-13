from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from backend.fallback.predictor import PredictionResult
from backend.models.bike_models import BikeMetrics
from backend.models.mobility_snapshot import MobilitySnapshot

_DEFAULT_HISTORY_PATH = "data/historical/bikes_history.csv"

_MODEL: Optional["BikeHistoryModel"] = None
_MODEL_PATH: Optional[Path] = None
_MODEL_MTIME: Optional[float] = None


@dataclass
class HourStats:
    count: int = 0
    bikes_sum: float = 0.0
    docks_sum: float = 0.0
    stations_sum: float = 0.0

    def add(self, bikes: float, docks: float, stations: float) -> None:
        self.count += 1
        self.bikes_sum += bikes
        self.docks_sum += docks
        self.stations_sum += stations

    def averages(self) -> Optional[Tuple[float, float, float]]:
        if self.count <= 0:
            return None
        return (
            self.bikes_sum / self.count,
            self.docks_sum / self.count,
            self.stations_sum / self.count,
        )


class BikeHistoryModel:
    def __init__(self, path: Path):
        self.path = path
        self.by_hour: Dict[int, HourStats] = {}
        self.overall = HourStats()
        self.latest_timestamp: Optional[datetime] = None
        self.total_rows = 0

    def load(self) -> bool:
        if not self.path.exists():
            return False

        self.by_hour.clear()
        self.overall = HourStats()
        self.latest_timestamp = None
        self.total_rows = 0

        with self.path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ts = _parse_timestamp(row.get("timestamp"))
                bikes = _parse_float(row.get("available_bikes"))
                docks = _parse_float(row.get("available_docks"))
                stations = _parse_float(row.get("stations_reporting"))

                if ts is None or bikes is None or docks is None:
                    continue

                if stations is None:
                    stations = 0.0

                hour = ts.hour
                stats = self.by_hour.get(hour)
                if stats is None:
                    stats = HourStats()
                    self.by_hour[hour] = stats

                stats.add(bikes, docks, stations)
                self.overall.add(bikes, docks, stations)
                self.total_rows += 1

                if self.latest_timestamp is None or ts > self.latest_timestamp:
                    self.latest_timestamp = ts

        return self.total_rows > 0

    def predict(self, now: datetime) -> Optional[Tuple[BikeMetrics, float, str]]:
        if self.total_rows <= 0:
            return None

        stats = self.by_hour.get(now.hour)
        reason = "historical_hourly_average"
        if stats is None or stats.count <= 0:
            stats = self.overall if self.overall.count > 0 else None
            reason = "historical_overall_average"

        if stats is None:
            return None

        averages = stats.averages()
        if averages is None:
            return None

        bikes_avg, docks_avg, stations_avg = averages

        metrics = BikeMetrics(
            available_bikes=max(0, int(round(bikes_avg))),
            available_docks=max(0, int(round(docks_avg))),
            stations_reporting=max(0, int(round(stations_avg))),
        )

        confidence = min(0.9, max(0.1, stats.count / 50.0))
        if reason == "historical_overall_average":
            confidence = min(confidence, 0.5)

        return metrics, confidence, reason


def predict_bikes_snapshot(
    cached_snapshot: Optional[MobilitySnapshot],
    now: Optional[datetime] = None,
) -> Optional[PredictionResult]:
    from backend.fallback.bikes_station_predictor import (
        aggregate_station_predictions,
        predict_bike_stations,
    )

    now_ts = now or datetime.now(timezone.utc)

    station_prediction = predict_bike_stations(now=now_ts)
    if station_prediction is not None and station_prediction.snapshot:
        total_bikes, total_docks, reporting = aggregate_station_predictions(station_prediction.snapshot)
        snapshot = MobilitySnapshot(
            timestamp=now_ts,
            location=_infer_location(cached_snapshot),
            bikes=BikeMetrics(
                available_bikes=total_bikes,
                available_docks=total_docks,
                stations_reporting=reporting,
            ),
        )
        reason = station_prediction.reason or "station_prediction"
        return PredictionResult(
            snapshot=snapshot,
            generated_at=now_ts,
            based_on=station_prediction.based_on,
            confidence=station_prediction.confidence,
            reason=f"from_{reason}",
        )

    return None


def _infer_location(cached_snapshot: Optional[MobilitySnapshot]) -> str:
    if cached_snapshot is not None and getattr(cached_snapshot, "location", None):
        return cached_snapshot.location
    return "dublin"


def _get_history_model() -> Optional[BikeHistoryModel]:
    global _MODEL, _MODEL_PATH, _MODEL_MTIME

    path = _resolve_history_path()
    if path is None:
        return None

    mtime = path.stat().st_mtime if path.exists() else None
    if _MODEL is None or path != _MODEL_PATH or mtime != _MODEL_MTIME:
        model = BikeHistoryModel(path)
        if not model.load():
            _MODEL = None
            _MODEL_PATH = path
            _MODEL_MTIME = mtime
            return None
        _MODEL = model
        _MODEL_PATH = path
        _MODEL_MTIME = mtime

    return _MODEL


def _resolve_history_path() -> Optional[Path]:
    env_path = os.getenv("BIKES_HISTORY_PATH")
    raw = env_path.strip() if env_path else _DEFAULT_HISTORY_PATH
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
    value = raw.strip()
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
