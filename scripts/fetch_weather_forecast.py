from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import requests


def main() -> None:
    args = _parse_args()
    params = {
        "latitude": args.lat,
        "longitude": args.lon,
        "hourly": args.hourly,
        "forecast_days": args.days,
        "timezone": args.timezone,
        "format": "csv",
    }
    response = requests.get(args.url, params=params, timeout=30)
    response.raise_for_status()

    rows = _parse_csv(response.text)
    if not rows:
        raise SystemExit("No weather rows found in API response.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_output(output, rows)

    print(f"Wrote {len(rows)} rows to {output}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Open-Meteo forecast CSV.")
    parser.add_argument("--url", default="https://api.open-meteo.com/v1/forecast")
    parser.add_argument("--lat", type=float, default=53.3498)
    parser.add_argument("--lon", type=float, default=-6.2603)
    parser.add_argument("--hourly", default="temperature_2m,rain")
    parser.add_argument("--days", type=int, default=16)
    parser.add_argument("--timezone", default="Europe/Dublin")
    parser.add_argument("--output", default="data/historical/weather_forecast.csv")
    return parser.parse_args()


def _parse_csv(text: str) -> List[Dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip() != ""]
    if not lines:
        return []

    reader = csv.reader(lines)
    rows = list(reader)
    if not rows:
        return []

    header, data_rows = _find_time_section(rows)
    if not header or not data_rows:
        return []

    normalised = [_normalise_header(h) for h in header]
    parsed: List[Dict[str, str]] = []
    for row in data_rows:
        if len(row) != len(normalised):
            continue
        parsed.append(dict(zip(normalised, row)))
    return parsed


def _normalise_header(name: str) -> str:
    clean = name.strip()
    clean = re.sub(r"\s*\(.*\)$", "", clean)
    clean = clean.replace(" ", "_")
    return clean


def _find_time_section(rows: List[List[str]]) -> tuple[List[str], List[List[str]]]:
    """
    Open-Meteo CSV includes metadata rows before the hourly table.
    Find the header row that begins with 'time' or 'timestamp' and
    return that header and its data rows until the next section.
    """
    header_idx = None
    for i, row in enumerate(rows):
        if not row:
            continue
        first = row[0].strip().lower()
        if first in ("time", "timestamp"):
            header_idx = i
            break
    if header_idx is None:
        return [], []

    header = rows[header_idx]
    data_rows: List[List[str]] = []
    start_index = header_idx + 1
    for row in rows[start_index:]:
        if not row:
            break
        first = row[0].strip().lower()
        if first in ("latitude", "longitude", "hourly_units", "daily_units", "daily", "hourly"):
            break
        # If row length mismatches, assume section ended
        if len(row) != len(header):
            break
        data_rows.append(row)

    return header, data_rows


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


if __name__ == "__main__":
    main()
