import math
import os
import requests
from datetime import datetime, timezone
from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.traffic_models import TrafficIncident

# Dublin city centre — fixed for now (same as tour/bike adapters)
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603

_CATEGORY_NAMES = {
    0: "Unknown", 1: "Accident", 2: "Fog", 3: "Dangerous Conditions",
    4: "Rain", 5: "Ice", 6: "Jam", 7: "Lane Closed", 8: "Road Closed",
    9: "Road Works", 10: "Wind", 11: "Flooding", 14: "Broken Down Vehicle",
}
_SEVERITY_NAMES = {0: "Unknown", 1: "Minor", 2: "Moderate", 3: "Major", 4: "Undefined"}


class TrafficAdapter(DataAdapter):
    """
    Adapter for TomTom Traffic Incidents API v5.

    Set the TOMTOM_API_KEY environment variable, or pass api_key= directly.
    Without a key the live request will fail with a 401; the fallback/cache
    layer will then serve cached or predicted data instead.
    """

    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("TOMTOM_API_KEY", "")
        self.base_url = base_url or "https://api.tomtom.com/traffic/services/5/incidentDetails"

    def source_name(self) -> str:
        return "traffic"

    def fetch(self, location: str = "dublin", radius_km: float = 5.0) -> MobilitySnapshot:
        response = self._make_api_request(radius_km)
        data = response.json()

        if "incidents" not in data:
            raise KeyError("Missing required field: 'incidents'")

        incidents = self._parse_incidents(data["incidents"])

        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=data.get("location", location),
            traffic=incidents,
        )

    def _make_api_request(self, radius_km: float):
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * math.cos(math.radians(_DUBLIN_LAT)))

        bbox = (
            f"{_DUBLIN_LON - lon_offset},{_DUBLIN_LAT - lat_offset},"
            f"{_DUBLIN_LON + lon_offset},{_DUBLIN_LAT + lat_offset}"
        )

        params = {
            "bbox": bbox,
            "fields": (
                "{incidents{type,geometry{type,coordinates},"
                "properties{iconCategory,magnitudeOfDelay,"
                "events{description,code},startTime,endTime,"
                "from,to,length,delay,roadNumbers}}}"
            ),
            "language": "en-GB",
            "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",
            "timeValidityFilter": "present",
        }

        if self.api_key:
            params["key"] = self.api_key

        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        return response

    @staticmethod
    def _midpoint(geometry):
        """
        Return (latitude, longitude) midpoint from a GeoJSON geometry.
        TomTom coordinates are [longitude, latitude] (GeoJSON convention).
        Handles Point and LineString; returns (None, None) if unavailable.
        """
        if not geometry:
            return None, None
        coords = geometry.get("coordinates")
        if not coords:
            return None, None
        geom_type = geometry.get("type", "")
        if geom_type == "Point":
            lon, lat = coords[0], coords[1]
            return lat, lon
        if geom_type == "LineString" and len(coords) >= 1:
            mid = coords[len(coords) // 2]
            return mid[1], mid[0]
        return None, None

    def _parse_incidents(self, incidents_data: list) -> list:
        """
        Handles two formats:
        - TomTom v5 native: each item has a 'properties' key with nested fields
        - Pre-formatted / flat: each item has 'category', 'severity', etc. directly
          (used by existing tests and the custom-backend fallback)
        """
        incidents = []
        for item in incidents_data:
            if "properties" in item:
                # TomTom v5 native format
                props = item["properties"]
                events = props.get("events", [])
                descriptions = [e["description"] for e in events if e.get("description")]
                road_numbers = props.get("roadNumbers", [])
                delay_seconds = props.get("delay", 0) or 0
                lat, lon = self._midpoint(item.get("geometry"))

                incident = TrafficIncident(
                    category=_CATEGORY_NAMES.get(props.get("iconCategory", 0), "Unknown"),
                    severity=_SEVERITY_NAMES.get(props.get("magnitudeOfDelay", 0), "Unknown"),
                    description=" | ".join(descriptions) if descriptions else "No description",
                    from_location=props.get("from", "Unknown"),
                    to_location=props.get("to", "Unknown"),
                    road=", ".join(road_numbers) if road_numbers else "Unknown road",
                    length_meters=props.get("length", 0),
                    delay_seconds=delay_seconds,
                    delay_minutes=round(delay_seconds / 60, 1),
                    latitude=lat,
                    longitude=lon,
                )
            else:
                # Flat / pre-formatted format
                delay_seconds = item.get("delay_seconds")
                delay_minutes = item.get("delay_minutes", 0)

                incident = TrafficIncident(
                    category=item.get("category"),
                    severity=item.get("severity"),
                    description=item.get("description"),
                    from_location=item.get("from"),
                    to_location=item.get("to"),
                    road=item.get("road"),
                    length_meters=item.get("length_meters"),
                    delay_seconds=delay_seconds,
                    delay_minutes=delay_minutes,
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                )
            incidents.append(incident)
        return incidents
