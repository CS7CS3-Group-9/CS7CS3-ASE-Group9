import requests
from datetime import datetime
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.adapters.base_adapter import DataAdapter
from backend.models.bus_models import BusRouteMetrics, BusSystemMetrics

# NEEDS LOADS OF FIXES


class BusAdapter(DataAdapter):
    def source_name(self) -> str:
        return "buses"

    def fetch(self, location: str = "dublin") -> MobilitySnapshot:
        """
        Fetch live bus data and convert it into domain models.
        """

        # Example endpoint (replace with real one later)
        url = "https://api.nationaltransport.ie/gtfsr/v2"

        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # ---- Route-level (static-ish) metrics ----
        routes = []
        for route in data.get("routes", []):
            routes.append(
                BusRouteMetrics(
                    route_id=route["id"],
                    stop_count=len(route["stops"]),
                    schedule=route.get("schedule"),
                    frequency=route.get("frequency"),
                )
            )

        # ---- System-level (live) metrics ----
        systems = []
        for vehicle in data.get("vehicles", []):
            systems.append(
                BusSystemMetrics(
                    route_id=vehicle["route_id"],
                    active_buses=vehicle.get("active_buses", 1),
                    current_location=vehicle.get("location"),
                )
            )

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            buses={"routes": routes, "system": systems},
            source_status={self.source_name(): "live"},
        )
