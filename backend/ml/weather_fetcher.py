from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests


def refresh_forecast(path: Path) -> bool:
    params = {
        "latitude": float(os.getenv("WEATHER_FORECAST_LAT", "53.3498")),
        "longitude": float(os.getenv("WEATHER_FORECAST_LON", "-6.2603")),
        "hourly": os.getenv("WEATHER_FORECAST_HOURLY", "temperature_2m,rain"),
        "forecast_days": int(os.getenv("WEATHER_FORECAST_DAYS", "16")),
        "timezone": os.getenv("WEATHER_FORECAST_TIMEZONE", "Europe/Dublin"),
        "format": "csv",
    }
    url = os.getenv("WEATHER_FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()

    rows = _parse_open_meteo_csv(resp.text)
    if not rows:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_output(path, rows)
    return True


def _parse_open_meteo_csv(text: str) -> List[Dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip() != ""]
    if not lines:
        return []

    reader = csv.reader(lines)
    rows = list(reader)
    if not rows:
        return []

    header_idx = None
    for i, row in enumerate(rows):
        if not row:
            continue
        first = row[0].strip().lower()
        if first in ("time", "timestamp"):
            header_idx = i
            break
    if header_idx is None:
        return []

    header = rows[header_idx]
    normalised = [_normalise_header(h) for h in header]
    data_rows: List[Dict[str, str]] = []
    start_index = header_idx + 1
    for row in rows[start_index:]:
        if len(row) != len(header):
            break
        data_rows.append(dict(zip(normalised, row)))

    return data_rows


def _normalise_header(name: str) -> str:
    clean = name.strip()
    clean = re.sub(r"\s*\(.*\)$", "", clean)
    clean = clean.replace(" ", "_")
    return clean


def _write_output(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    header = list(rows[0].keys())
    if "time" in header and "timestamp" not in header:
        header = ["timestamp" if h == "time" else h for h in header]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            if "time" in row and "timestamp" not in row:
                row = {("timestamp" if k == "time" else k): v for k, v in row.items()}
            writer.writerow(row)


def should_refresh(path: Path, refresh_hours: int = 24) -> bool:
    if not path.exists():
        return True
    age_seconds = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age_seconds >= refresh_hours * 3600
