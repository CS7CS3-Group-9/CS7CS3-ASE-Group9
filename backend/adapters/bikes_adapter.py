import requests
from datetime import datetime
from backend.models.mobility_snapshot import MobilitySnapshot


class BikeAdapter:
    def fetch(self, location="dublin"):
        url = "https://api.citybik.es/v2/networks/dublinbikes"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            bikes=data["network"]["stations"],
            source_status={"bikes": "live"},
        )
