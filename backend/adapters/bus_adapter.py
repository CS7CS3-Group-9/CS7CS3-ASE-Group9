import requests
from datetime import datetime
import time
from pathlib import Path
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.adapters.base_adapter import DataAdapter
from backend.models.bus_models import BusRouteMetrics, BusSystemMetrics, BusMetrics


class BusAdapter(DataAdapter):
    BASE_URL = "https://api.nationaltransport.ie/gtfsr/v2"

    def __init__(self, api_key: str, gtfs_dir: str):
        self.api_key = api_key
        self.gtfs_dir = Path(gtfs_dir)

    def source_name(self) -> str:
        return "buses"

    def _headers(self):
        return {"x-api-key": self.api_key, "Accept": "application/json"}

    def _get_json(self, endpoint: str) -> dict:
        url = f"{self.BASE_URL}/{endpoint}?format=json"
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def _load_routes_lookup(self) -> dict:
        """
        route_id -> route_short_name
        """
        routes_path = self.gtfs_dir / "routes.txt"
        lookup = {}

        with routes_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                route_id = (row.get("route_id") or "").strip()
                if not route_id:
                    continue
                lookup[route_id] = (row.get("route_short_name") or "").strip()

        return lookup

    def _delays_by_route(self) -> dict:
        """
        route_id -> list(delay_seconds)
        """
        data = self._get_json("TripUpdates")
        delays = defaultdict(list)

        for entity in data.get("entity", []):
            trip_update = entity.get("trip_update") or {}
            trip = trip_update.get("trip") or {}
            route_id = trip.get("route_id")
            if not route_id:
                continue

            stop_updates = trip_update.get("stop_time_update") or []
            if not stop_updates:
                continue

            next_stop = stop_updates[0]
            delay = next_stop.get("arrival", {}).get("delay") or next_stop.get("departure", {}).get("delay") or 0

            try:
                delays[str(route_id)].append(int(delay))
            except (TypeError, ValueError):
                continue

        return delays

    def fetch(self, location: str) -> MobilitySnapshot:
        routes_lookup = self._load_routes_lookup()

        active_by_route = self._active_vehicle_ids_by_route()
        delays_by_route = self._delays_by_route()

        # Include anything we know about: routes from static + routes seen in realtime
        all_route_ids = set(routes_lookup.keys()) | set(active_by_route.keys()) | set(delays_by_route.keys())

        route_metrics = {}
        system_metrics = {}

        for route_id in all_route_ids:
            # placeholders for later analytics
            route_metrics[route_id] = BusRouteMetrics(
                route_id=route_id,
                stop_count=None,
                schedule=None,
                frequency=None,
            )

            # lightweight live numbers (ok to keep; you can recompute later in metrics layer)
            active_buses = len(active_by_route.get(route_id, set()))
            delays = delays_by_route.get(route_id, [])
            average_delay = (sum(delays) / len(delays)) if delays else 0.0

            system_metrics[route_id] = BusSystemMetrics(
                route_id=route_id,
                active_buses=active_buses,
                average_delay=average_delay,
            )

        buses = BusMetrics(
            routes_lookup=routes_lookup,
            route_metrics=route_metrics,
            system_metrics=system_metrics,
        )

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            buses=buses,
            source_status={self.source_name(): "live"},
        )
