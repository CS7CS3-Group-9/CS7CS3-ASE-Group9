import requests
from datetime import datetime, timezone
from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.traffic_models import TrafficIncident


class TrafficAdapter(DataAdapter):
    """
    Adapter for Traffic API (TomTom or custom backend)
    Fetches traffic incidents and congestion data
    """

    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key
        # Default to TomTom, but allow custom backend
        self.base_url = base_url or "https://api.tomtom.com/traffic/services/4/incidentDetails"

    def source_name(self) -> str:
        return "traffic"

    def fetch(self, location: str, radius_km: float = 1.0) -> MobilitySnapshot:
        """
        Fetch traffic incidents from Traffic API

        Args:
            location: Location name (city, area)
            radius_km: Search radius in kilometers (default: 1km)

        Returns:
            TrafficSnapshot object with incidents and metrics
        """
        # Make API request
        response = self._make_api_request(location, radius_km)

        # Parse the response
        data = response.json()

        # Validate required fields (raise KeyError if missing)
        if "incidents" not in data:
            raise KeyError("Missing required field: 'incidents'")

        # Parse incidents
        incidents = self._parse_incidents(data["incidents"])

        # Create and return snapshot
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=data.get("location", location),
            traffic=incidents,
        )

    def _make_api_request(self, location: str, radius_km: float):
        """Make API request to traffic service"""
        # Note: In production, you'd need to:
        # 1. Geocode the location to lat/lng
        # 2. Build proper API request with bounding box
        # 3. Handle authentication

        # For now, this assumes your backend returns data in the expected format
        params = {"location": location, "radius_km": radius_km}

        if self.api_key:
            params["key"] = self.api_key

        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()

        return response

    def _parse_incidents(self, incidents_data: list) -> list:
        """Parse incidents from API response"""
        incidents = []

        for incident_data in incidents_data:
            incident = TrafficIncident(
                category=incident_data.get("category"),
                severity=incident_data.get("severity"),
                description=incident_data.get("description"),
                from_location=incident_data.get("from"),
                to_location=incident_data.get("to"),
                road=incident_data.get("road"),
                length_meters=incident_data.get("length_meters"),
                delay_seconds=incident_data.get("delay_seconds"),
                delay_minutes=incident_data.get("delay_minutes", 0),
            )
            incidents.append(incident)

        return incidents
