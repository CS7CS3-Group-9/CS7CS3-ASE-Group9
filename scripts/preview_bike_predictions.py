from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.fallback.bikes_predictor import predict_bikes_snapshot  # noqa: E402
from backend.fallback.bikes_station_predictor import predict_bike_stations  # noqa: E402


def main() -> None:
    now = datetime.now(timezone.utc)
    station_result = predict_bike_stations(now=now)
    if station_result is None:
        print("No station predictions available.")
    else:
        stations = station_result.snapshot or []
        print(f"Station predictions: {len(stations)} (reason={station_result.reason})")
        for s in stations[:5]:
            print(
                f"- {s.get('name')} @ ({s.get('lat')},{s.get('lon')}): "
                f"{s.get('free_bikes')} bikes, {s.get('empty_slots')} docks"
            )

    city_result = predict_bikes_snapshot(None, now=now)
    if city_result is None or city_result.snapshot is None:
        print("No citywide prediction available.")
    else:
        bikes = city_result.snapshot.bikes
        print(
            "Citywide prediction: "
            f"{bikes.available_bikes} bikes, "
            f"{bikes.available_docks} docks, "
            f"{bikes.stations_reporting} stations "
            f"(reason={city_result.reason})"
        )


if __name__ == "__main__":
    main()
