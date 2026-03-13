import requests
import os


class BikeStationsAdapter:
    def source_name(self) -> str:
        return "bikes_stations"

    def fetch(self, location: str = "dublin"):
        if os.getenv("FORCE_BIKES_PREDICTION", "").lower() in ("1", "true", "yes"):
            raise RuntimeError("Forced bikes station prediction")
        url = "https://api.citybik.es/v2/networks/dublinbikes"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        stations = response.json()["network"]["stations"]
        return [
            {
                "name": s["name"],
                "lat": s["latitude"],
                "lon": s["longitude"],
                "free_bikes": s["free_bikes"],
                "empty_slots": s["empty_slots"],
                "total": s["extra"]["slots"],
            }
            for s in stations
        ]
