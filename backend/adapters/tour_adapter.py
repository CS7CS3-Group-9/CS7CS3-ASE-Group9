import requests
from datetime import datetime

from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.tour_models import AttractionMetrics


class TourAdapter(DataAdapter):

    def source_name(self) -> str:
        return "tours"

    def fetch(self, location: str = "dublin") -> MobilitySnapshot:
        """
        Fetch tourism / attraction data and convert it into AttractionMetrics.
        """
        # Example endpoint – replace with a real one later
        url = "https://overpass-api.de/api/interpreter"

        elements = data.get("elements", [])

        response = requests.get(url, data=overpass_query, timeout=30)
        response.raise_for_status()
        data = response.json()

        attractions = []
        for item in data.get("attractions", []):
            attractions.append(
                AttractionMetrics(
                    attraction_name=item["name"],
                    open_times=item.get("opening_hours"),
                    location=item.get("location"),
                    price=item.get("price"),
                )
            )

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            events=attractions,
            source_status={self.source_name(): "live"},
        )
