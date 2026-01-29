import os
import requests
from datetime import datetime
from typing import List, Optional

from backend.models.route_models import RouteRecommendation, MultiStopRoute, RouteLeg


class RoutesAdapter:
    def source_name(self) -> str:
        return "routes"

    def fetch(
        self,
        start: str,
        end: str,
        transport_mode: str = None,
        dep_time: datetime = None,
        arr_time: datetime = None,
        fast_route: bool = False,
        eco_route: bool = False,
        waypoints: Optional[List[str]] = None,
    ) -> RouteRecommendation:
        # Enforce your model rules (your tests expect ValueError)
        if dep_time and arr_time:
            raise ValueError("Cannot specify both departure and arrival time")
        if fast_route and eco_route:
            raise ValueError("Cannot enable both fast and eco route")

        waypoints = waypoints or []

        # NOTE: For now you said "no real API call" — tests will mock this anyway.
        # Keep a placeholder URL so requests.post exists for mocking.
        url = "https://example.com/routes"
        payload = {
            "start": start,
            "end": end,
            "transport_mode": transport_mode,
            "fast_route": fast_route,
            "eco_route": eco_route,
            "waypoints": waypoints,
            "dep_time": dep_time.isoformat() if dep_time else None,
            "arr_time": arr_time.isoformat() if arr_time else None,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Multi-stop mocked schema
        if waypoints:
            return self._parse_multistop(
                data, start, end, transport_mode, dep_time, arr_time, fast_route, eco_route, waypoints
            )

        # Single route mocked schema
        return self._parse_single(data, start, end, transport_mode, dep_time, arr_time, fast_route, eco_route)

    def _parse_single(
        self,
        data: dict,
        start: str,
        end: str,
        transport_mode: str,
        dep_time: datetime,
        arr_time: datetime,
        fast_route: bool,
        eco_route: bool,
    ) -> RouteRecommendation:
        origin = data["origin"]
        destination = data["destination"]

        ocoords = origin["coordinates"]
        dcoords = destination["coordinates"]

        distance_meters = data["distance_meters"]
        duration = data["duration"]
        polyline = data.get("encoded_polyline")  # may be missing

        return RouteRecommendation(
            start=start,
            end=end,
            transport_mode=transport_mode,
            dep_time=dep_time,
            arr_time=arr_time,
            fast_route=fast_route,
            eco_route=eco_route,
            route=polyline if polyline is not None else None,
            duration=duration,
            origin_lat=ocoords["lat"],
            origin_lng=ocoords["lng"],
            dest_lat=dcoords["lat"],
            dest_lng=dcoords["lng"],
            distance_meters=distance_meters,
            waypoints=[],
            multi_stop_data=None,
        )

    def _parse_multistop(
        self,
        data: dict,
        start: str,
        end: str,
        transport_mode: str,
        dep_time: datetime,
        arr_time: datetime,
        fast_route: bool,
        eco_route: bool,
        waypoints: List[str],
    ) -> RouteRecommendation:
        legs = [
            RouteLeg(
                from_location=leg["from"],
                to_location=leg["to"],
                duration_seconds=leg["duration_seconds"],
                duration_formatted=leg["duration_formatted"],
                distance_meters=leg["distance_meters"],
                distance_km=leg["distance_km"],
            )
            for leg in data["legs"]
        ]

        multi = MultiStopRoute(
            optimal_route_order=data["optimal_route_order"],
            total_duration_seconds=data["total_duration_seconds"],
            total_duration_formatted=data["total_duration_formatted"],
            total_distance_km=data["total_distance_km"],
            number_of_stops=data["number_of_stops"],
            legs=legs,
        )

        return RouteRecommendation(
            start=start,
            end=end,
            transport_mode=transport_mode,
            dep_time=dep_time,
            arr_time=arr_time,
            fast_route=fast_route,
            eco_route=eco_route,
            route=None,
            duration=None,
            waypoints=waypoints,
            multi_stop_data=multi,
        )
