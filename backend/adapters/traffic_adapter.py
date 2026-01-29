import requests
from datetime import datetime, timezone
from backend.adapters.base_adapter import DataAdapter
from backend.models.traffic_models import TrafficIncident, TrafficMetrics, TrafficSnapshot


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
    
    def fetch(self, location: str, radius_km: float = 1.0) -> TrafficSnapshot:
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
        
        # Extract basic info
        location_name = data.get("location", location)
        coordinates = data.get("coordinates", {})
        lat = coordinates.get("lat")
        lng = coordinates.get("lng")
        
        # Parse incidents
        incidents = self._parse_incidents(data["incidents"])
        
        # Calculate metrics
        metrics = self._calculate_metrics(incidents, radius_km)
        
        # Create and return snapshot
        return TrafficSnapshot(
            location=location_name,
            latitude=lat,
            longitude=lng,
            radius_km=radius_km,
            timestamp=datetime.now(timezone.utc),
            metrics=metrics,
            source_status={"tomtom": "live"}
        )
    
    def _make_api_request(self, location: str, radius_km: float):
        """Make API request to traffic service"""
        # Note: In production, you'd need to:
        # 1. Geocode the location to lat/lng
        # 2. Build proper API request with bounding box
        # 3. Handle authentication
        
        # For now, this assumes your backend returns data in the expected format
        params = {
            "location": location,
            "radius_km": radius_km
        }
        
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
                delay_minutes=incident_data.get("delay_minutes", 0)
            )
            incidents.append(incident)
        
        return incidents
    
    def _calculate_metrics(self, incidents: list, radius_km: float) -> TrafficMetrics:
        """Calculate aggregated metrics from incidents"""
        total = len(incidents)
        
        # Group by category
        by_category = {}
        for inc in incidents:
            by_category[inc.category] = by_category.get(inc.category, 0) + 1
        
        # Group by severity
        by_severity = {}
        for inc in incidents:
            by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1
        
        # Calculate total delay (handle None values)
        total_delay = sum(
            inc.delay_minutes 
            for inc in incidents 
            if inc.delay_minutes is not None
        )
        
        # Calculate average delay per incident
        average_delay = total_delay / total if total > 0 else 0
        
        # Determine congestion level based on incidents per km
        incidents_per_km = total / radius_km if radius_km > 0 else 0
        if incidents_per_km > 5:
            congestion_level = "high"
        elif incidents_per_km > 2:
            congestion_level = "medium"
        else:
            congestion_level = "low"
        
        # Estimate average speed based on congestion level
        if congestion_level == "high":
            average_speed = 15  # km/h
        elif congestion_level == "medium":
            average_speed = 30  # km/h
        else:
            average_speed = 50  # km/h
        
        return TrafficMetrics(
            congestion_level=congestion_level,
            average_speed=average_speed,
            total_incidents=total,
            incidents_by_category=by_category,
            incidents_by_severity=by_severity,
            total_delay_minutes=total_delay,
            average_delay_minutes=average_delay,
            incidents=incidents
        )