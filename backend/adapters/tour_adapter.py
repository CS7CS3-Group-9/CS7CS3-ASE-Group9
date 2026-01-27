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

        overpass_query = (
            "[out:json]; "
            "("
            '  node["tourism"="attraction"](around: 10000, 53.3498, -6.2603); '
            '  node["tourism"="museum"](around: 10000, 53.3498, -6.2603); '
            '  node["historic"="monument"](around: 10000, 53.3498, -6.2603); '
            '  node["historic"="castle"](around: 10000, 53.3498, -6.2603); '
            '  way["tourism"="attraction"](around: 10000, 53.3498, -6.2603); '
            '  way["tourism"="museum"](around: 10000, 53.3498, -6.2603);'
            "); "
            "out center; "
        )

        response = requests.get(url, data=overpass_query, timeout=30)
        response.raise_for_status()
        data = response.json()

        elements = data.get("elements", [])

        attractions = []
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name", "Unknown")

            # Get coordinates
            lat_detail = None
            lon_detail = None

            if "lat" in element and "lon" in element:
                lat_detail = element["lat"]
                lon_detail = element["lon"]
            elif "center" in element:
                lat_detail = element["center"].get("lat")
                lon_detail = element["center"].get("lon")

            if lat_detail is None or lon_detail is None:
                continue

            opening_hours = tags.get("opening_hours", "Not available")
            # Get price/fee information if available
            price = "Not available"
            if tags.get("fee") == "yes":
                # Check for specific price tags
                if tags.get("charge"):
                    price = tags.get("charge")
                elif tags.get("price"):
                    price = tags.get("price")
                else:
                    price = "Yes (contact for details)"
            elif tags.get("fee") == "no":
                price = "Free"
            elif tags.get("price"):
                price = tags.get("price")
            elif tags.get("charge"):
                price = tags.get("charge")

            attractions.append(
                AttractionMetrics(
                    attraction_name=name,
                    open_times=opening_hours,
                    location={lat_detail, lon_detail},
                    price=price,
                )
            )

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            events=attractions,
            source_status={self.source_name(): "live"},
        )
