from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from backend.ml.bikes_model import BikesModelBundle


def main() -> None:
    args = _parse_args()
    data_path = Path(args.input)
    if not data_path.exists():
        raise SystemExit(f"Input CSV not found: {data_path}")

    usecols = {
        "last_reported",
        "timestamp",
        "num_bikes_available",
        "num_docks_available",
        "capacity",
        "lat",
        "lon",
        "name",
        "station_id",
    }
    df = pd.read_csv(
        data_path,
        usecols=lambda c: c in usecols,
        nrows=args.max_rows if args.max_rows else None,
        low_memory=False,
    )
    df = _normalise_columns(df)

    df = _prepare_time_features(df)
    df = _apply_filters(df)

    if args.weather:
        weather = _read_weather_csv(Path(args.weather))
        weather = _prepare_weather(weather)
        df = _merge_weather(df, weather)

    if args.sample_frac:
        df = df.sample(frac=args.sample_frac, random_state=42)
    if args.max_rows and len(df) > args.max_rows:
        df = df.sample(n=args.max_rows, random_state=42)

    feature_cols = [
        "hour",
        "weekday",
        "month",
        "day_of_year",
        "is_weekend",
        "lat",
        "lon",
        "capacity",
    ]

    weather_cols = [c for c in df.columns if c.startswith("weather_")]
    feature_cols.extend(weather_cols)

    target_col = "num_bikes_available"
    X = df[feature_cols].to_numpy(dtype=float)
    y = df[target_col].to_numpy(dtype=float)

    model = HistGradientBoostingRegressor(
        max_depth=10,
        learning_rate=0.1,
        max_iter=200,
        l2_regularization=0.1,
        random_state=42,
    )
    model.fit(X, y)

    stations = _build_station_metadata(df)

    bundle = BikesModelBundle(
        model=model,
        feature_columns=feature_cols,
        stations=stations,
        weather_feature_columns=weather_cols,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)

    print(f"Model saved to: {out_path}")
    print(f"Rows used: {len(df)}")
    print(f"Stations: {len(stations)}")
    print(f"Features: {feature_cols}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train bikes availability model.")
    parser.add_argument("--input", required=True, help="Path to bikes history CSV.")
    parser.add_argument("--output", default="backend/ml/artifacts/bikes_model.joblib")
    parser.add_argument("--weather", help="Optional weather CSV to merge.")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--sample-frac", type=float, default=None)
    return parser.parse_args()


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "last_reported": "timestamp",
        "num_bikes_available": "num_bikes_available",
        "num_docks_available": "num_docks_available",
        "capacity": "capacity",
        "lat": "lat",
        "lon": "lon",
        "name": "name",
        "station_id": "station_id",
    }
    df = df.rename(columns=rename)
    if "station_id" not in df.columns:
        df["station_id"] = np.nan
    if "name" not in df.columns:
        df["name"] = np.nan
    return df


def _prepare_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["timestamp"] = df["timestamp"].apply(_parse_timestamp)
    df = df[df["timestamp"].notna()].copy()

    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday
    df["month"] = df["timestamp"].dt.month
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    return df


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    required = ["num_bikes_available", "num_docks_available", "capacity", "lat", "lon"]
    df = df.dropna(subset=required)
    df = df[(df["capacity"] > 0)]
    return df


def _prepare_weather(weather: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in weather.columns and "time" in weather.columns:
        weather = weather.rename(columns={"time": "timestamp"})
    weather = weather.rename(columns={"timestamp": "weather_timestamp"})
    weather["weather_timestamp"] = weather["weather_timestamp"].apply(_parse_timestamp)
    weather = weather[weather["weather_timestamp"].notna()].copy()
    for col in weather.columns:
        if col == "weather_timestamp":
            continue
        weather = weather.rename(columns={col: f"weather_{col}"})
    return weather


def _merge_weather(df: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["weather_key"] = df["timestamp"].dt.floor("H")
    weather["weather_key"] = weather["weather_timestamp"].dt.floor("H")
    merged = df.merge(weather.drop(columns=["weather_timestamp"]), on="weather_key", how="left")
    merged = merged.drop(columns=["weather_key"])
    for col in merged.columns:
        if col.startswith("weather_"):
            merged[col] = merged[col].fillna(0.0)
    return merged


def _build_station_metadata(df: pd.DataFrame) -> list[Dict[str, Optional[float]]]:
    meta_cols = ["station_id", "name", "lat", "lon", "capacity"]
    meta = df[meta_cols].dropna(subset=["lat", "lon", "capacity"]).drop_duplicates(subset=["station_id", "lat", "lon"])

    stations = []
    for _, row in meta.iterrows():
        station_id = None
        if pd.notna(row.get("station_id")):
            station_id = str(row["station_id"])
        else:
            station_id = f"lat:{float(row['lat']):.5f},lon:{float(row['lon']):.5f}"
        stations.append(
            {
                "station_id": station_id,
                "name": row["name"] if pd.notna(row["name"]) else None,
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "capacity": float(row["capacity"]),
            }
        )
    return stations


def _parse_timestamp(raw: object) -> Optional[pd.Timestamp]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    text = str(raw).strip()
    if text == "":
        return None

    if "/" in text:
        try:
            return pd.to_datetime(text, utc=True, dayfirst=True)
        except Exception:
            pass

    try:
        return pd.to_datetime(text, utc=True)
    except Exception:
        pass

    try:
        return pd.to_datetime(float(text), unit="s", utc=True)
    except Exception:
        return None


def _read_weather_csv(path: Path) -> pd.DataFrame:
    """
    Open-Meteo CSV includes a metadata block before the hourly table.
    This reads the file and extracts the section that starts with "time" or "timestamp".
    """
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip() != ""]
    if not lines:
        return pd.DataFrame()

    header_idx = None
    for i, line in enumerate(lines):
        first = line.split(",")[0].strip().lower()
        if first in ("time", "timestamp"):
            header_idx = i
            break
    if header_idx is None:
        return pd.read_csv(path)

    header = lines[header_idx].split(",")
    rows = []
    start_index = header_idx + 1
    for line in lines[start_index:]:
        parts = line.split(",")
        if len(parts) != len(header):
            break
        rows.append(parts)

    if not rows:
        return pd.DataFrame(columns=header)
    return pd.DataFrame(rows, columns=header)


if __name__ == "__main__":
    main()
