from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from backend.fallback.predictor import PredictionResult
from backend.ml.bikes_model import predict_stations

_DEFAULT_STATION_HISTORY_PATH = "data/historical/bikes_station_history.csv"

_MODEL: Optional["BikeStationHistoryModel"] = None
_MODEL_PATH: Optional[Path] = None
_MODEL_MTIME: Optional[float] = None


@dataclass
class StationStats:
    count: int = 0
    bikes_sum: float = 0.0
    docks_sum: float = 0.0
    total_sum: float = 0.0

    def add(self, bikes: float, docks: float, total: float) -> None:
        self.count += 1
        self.bikes_sum += bikes
        self.docks_sum += docks
        self.total_sum += total

    def averages(self) -> Optional[Tuple[float, float, float]]:
        if self.count <= 0:
            return None
        return (
            self.bikes_sum / self.count,
            self.docks_sum / self.count,
            self.total_sum / self.count,
        )


@dataclass
class StationMeta:
    station_id: str
    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    total: Optional[float] = None

    def update(self, name: Optional[str], lat: Optional[float], lon: Optional[float], total: Optional[float]) -> None:
        if name:
            self.name = name
        if lat is not None:
            self.lat = lat
        if lon is not None:
            self.lon = lon
        if total is not None:
            self.total = total


class BikeStationHistoryModel:
    def __init__(self, path: Path):
        self.path = path
        self.by_station_bucket: Dict[Tuple[str, int], StationStats] = {}
        self.by_station: Dict[str, StationStats] = {}
        self.meta: Dict[str, StationMeta] = {}
        self.latest_timestamp: Optional[datetime] = None
        self.total_rows = 0

    def load(self) -> bool:
        if not self.path.exists():
            return False

        self.by_station_bucket.clear()
        self.by_station.clear()
        self.meta.clear()
        self.latest_timestamp = None
        self.total_rows = 0

        with self.path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ts = _parse_timestamp(_pick(row, ("timestamp", "time", "datetime", "last_update", "last_reported")))
                station_id_raw = _pick(row, ("station_id", "station_number", "number", "station"))
                bikes = _parse_float(
                    _pick(row, ("available_bikes", "bikes_available", "bike_available", "num_bikes_available"))
                )
                docks = _parse_float(
                    _pick(
                        row,
                        ("available_docks", "available_bike_stands", "docks_available", "num_docks_available"),
                    )
                )
                total = _parse_float(_pick(row, ("total", "bike_stands", "stands", "capacity")))

                if ts is None or bikes is None:
                    continue

                if docks is None and total is not None:
                    docks = max(0.0, total - bikes)
                if total is None and docks is not None:
                    total = bikes + docks
                if docks is None or total is None:
                    continue

                name = _pick(row, ("name", "station_name", "short_name", "address"))
                lat = _parse_float(_pick(row, ("lat", "latitude")))
                lon = _parse_float(_pick(row, ("lon", "lng", "longitude")))

                station_id = _build_station_id(station_id_raw, lat, lon, name)
                if station_id is None:
                    continue
                if station_id not in self.meta:
                    self.meta[station_id] = StationMeta(station_id=station_id)
                self.meta[station_id].update(name, lat, lon, total)

                bucket = ts.weekday() * 24 + ts.hour
                key = (station_id, bucket)
                stats = self.by_station_bucket.get(key)
                if stats is None:
                    stats = StationStats()
                    self.by_station_bucket[key] = stats
                stats.add(bikes, docks, total)

                overall = self.by_station.get(station_id)
                if overall is None:
                    overall = StationStats()
                    self.by_station[station_id] = overall
                overall.add(bikes, docks, total)

                self.total_rows += 1
                if self.latest_timestamp is None or ts > self.latest_timestamp:
                    self.latest_timestamp = ts

        return self.total_rows > 0

    def predict(self, now: datetime) -> List[dict]:
        if self.total_rows <= 0:
            return []

        bucket = now.weekday() * 24 + now.hour
        predictions: List[dict] = []

        for station_id, meta in self.meta.items():
            stats = self.by_station_bucket.get((station_id, bucket))
            if stats is None or stats.count <= 0:
                stats = self.by_station.get(station_id)
                reason = "station_overall_average"
            else:
                reason = "station_hourly_average"

            if stats is None or stats.count <= 0:
                continue

            averages = stats.averages()
            if averages is None:
                continue

            bikes_avg, docks_avg, total_avg = averages
            total_val = meta.total if meta.total is not None else total_avg
            bikes_val = max(0, int(round(bikes_avg)))
            docks_val = max(0, int(round(docks_avg)))

            predictions.append(
                {
                    "station_id": station_id,
                    "name": meta.name or f"Station {station_id}",
                    "lat": meta.lat,
                    "lon": meta.lon,
                    "free_bikes": bikes_val,
                    "empty_slots": docks_val,
                    "total": max(0, int(round(total_val))) if total_val is not None else bikes_val + docks_val,
                    "prediction_reason": reason,
                }
            )

        return predictions


def predict_bike_stations(now: Optional[datetime] = None) -> Optional[PredictionResult]:
    ml_prediction = predict_stations(now=now)
    if ml_prediction:
        now_ts = now or datetime.now(timezone.utc)
        return PredictionResult(
            snapshot=ml_prediction,
            generated_at=now_ts,
            based_on=None,
            confidence=0.75,
            reason="ml_model",
        )
    return None


def aggregate_station_predictions(stations: Iterable[dict]) -> Tuple[int, int, int]:
    bikes = 0
    docks = 0
    reporting = 0
    for s in stations:
        bikes += int(s.get("free_bikes", 0) or 0)
        docks += int(s.get("empty_slots", 0) or 0)
        reporting += 1
    return bikes, docks, reporting


def _get_station_model() -> Optional[BikeStationHistoryModel]:
    global _MODEL, _MODEL_PATH, _MODEL_MTIME

    path = _resolve_station_history_path()
    if path is None:
        return None

    mtime = path.stat().st_mtime if path.exists() else None
    if _MODEL is None or path != _MODEL_PATH or mtime != _MODEL_MTIME:
        model = BikeStationHistoryModel(path)
        if not model.load():
            _MODEL = None
            _MODEL_PATH = path
            _MODEL_MTIME = mtime
            return None
        _MODEL = model
        _MODEL_PATH = path
        _MODEL_MTIME = mtime

    return _MODEL


def _resolve_station_history_path() -> Optional[Path]:
    env_path = os.getenv("BIKES_STATION_HISTORY_PATH")
    raw = env_path.strip() if env_path else _DEFAULT_STATION_HISTORY_PATH
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / path
    return path


def _pick(row: dict, keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _build_station_id(
    station_id_raw: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    name: Optional[str],
) -> Optional[str]:
    if station_id_raw is not None and str(station_id_raw).strip() != "":
        return str(station_id_raw).strip()
    if lat is not None and lon is not None:
        return f"lat:{lat:.5f},lon:{lon:.5f}"
    if name:
        return f"name:{name.strip().lower()}"
    return None


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

    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            ts = datetime.strptime(value, fmt)
            return ts.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

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
