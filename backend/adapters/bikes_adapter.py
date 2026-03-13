import requests
from datetime import datetime
import os
from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.bike_models import StationMetrics, BikeMetrics


class BikesAdapter(DataAdapter):

    def source_name(self) -> str:
        return "bikes"

    def fetch(self, location="dublin") -> MobilitySnapshot:
        if os.getenv("FORCE_BIKES_PREDICTION", "").lower() in ("1", "true", "yes"):
            raise RuntimeError("Forced bikes prediction")
        url = "https://api.citybik.es/v2/networks/dublinbikes"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()["network"]["stations"]

        stations = [
            StationMetrics(
                name=s["name"],
                free_bikes=s["free_bikes"],
                empty_slots=s["empty_slots"],
                total_spaces=s["extra"]["slots"],
            )
            for s in data
        ]

        metrics = BikeMetrics(
            available_bikes=sum(s.free_bikes for s in stations),
            available_docks=sum(s.empty_slots for s in stations),
            stations_reporting=len(stations),
        )

        return MobilitySnapshot(timestamp=datetime.utcnow(), location=location, bikes=metrics)
