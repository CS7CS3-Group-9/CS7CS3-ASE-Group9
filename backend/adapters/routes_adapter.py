import os
import requests
from datetime import datetime
from typing import List, Optional, Tuple

from backend.models.route_models import RouteRecommendation, MultiStopRoute, RouteLeg

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_ROUTES_URL  = "https://routes.googleapis.com/directions/v2:computeRoutes"

_DEFAULT_FIELD_MASK = (
    "routes.duration,routes.distanceMeters,"
    "routes.polyline.encodedPolyline,"
    "routes.legs.duration,routes.legs.distanceMeters,"
    "routes.legs.startLocation,routes.legs.endLocation"
)


class RoutesAdapter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")

    def source_name(self) -> str:
        return "routes"

    # ------------------------------------------------------------------ #
    # Public helpers — shared with the routing endpoint                   #
    # ------------------------------------------------------------------ #

    def geocode(self, address: str) -> Tuple[float, float, str]:
        """Convert a free-text address to (lat, lng, display_name)."""
        needs_city = not any(kw in address.lower() for kw in ("dublin", "ireland"))
        query = address + ", Dublin, Ireland" if needs_city else address
        resp = requests.get(
            _GEOCODE_URL,
            params={"address": query, "key": self.api_key},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            raise RuntimeError(f"Geocoding failed for '{address}': {data.get('status')}")
        loc  = data["results"][0]["geometry"]["location"]
        name = data["results"][0].get("formatted_address", address)
        return float(loc["lat"]), float(loc["lng"]), name

    def route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "DRIVE",
        dep_time: Optional[datetime] = None,
        arr_time: Optional[datetime] = None,
        intermediates: Optional[List[Tuple[float, float]]] = None,
        field_mask: str = None,
    ) -> dict:
        """
        Call Google Routes API between two (lat, lon) pairs.
        Returns the raw API response dict.
        """
        payload = {
            "origin":      {"location": {"latLng": {"latitude": origin[0],      "longitude": origin[1]}}},
            "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
            "travelMode":  mode,
        }
        if intermediates:
            payload["intermediates"] = [
                {"location": {"latLng": {"latitude": wp[0], "longitude": wp[1]}}}
                for wp in intermediates
            ]
        if dep_time:
            payload["departureTime"] = dep_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if arr_time and mode == "TRANSIT":
            payload["arrivalTime"] = arr_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if mode == "DRIVE":
            payload["routingPreference"] = "TRAFFIC_AWARE"

        resp = requests.post(
            _ROUTES_URL,
            headers={
                "Content-Type":     "application/json",
                "X-Goog-Api-Key":   self.api_key,
                "X-Goog-FieldMask": field_mask or _DEFAULT_FIELD_MASK,
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # DataAdapter interface                                               #
    # ------------------------------------------------------------------ #

    def fetch(
        self,
        start: str,
        end: str,
        transport_mode: str = None,
        dep_time: Optional[datetime] = None,
        arr_time: Optional[datetime] = None,
        fast_route: bool = False,
        eco_route: bool = False,
        waypoints: Optional[List[str]] = None,
        location: str = None,   # ignored — kept for SnapshotService compat
    ) -> RouteRecommendation:
        if dep_time and arr_time:
            raise ValueError("Cannot specify both departure and arrival time")
        if fast_route and eco_route:
            raise ValueError("Cannot enable both fast and eco route")

        waypoints = waypoints or []
        mode = transport_mode or "DRIVE"

        # Geocode all stops
        origin_lat, origin_lng, _ = self.geocode(start)
        dest_lat,   dest_lng,   _ = self.geocode(end)

        if waypoints:
            intermediate_coords = [self.geocode(wp)[:2] for wp in waypoints]
            data = self.route(
                (origin_lat, origin_lng), (dest_lat, dest_lng),
                mode=mode, dep_time=dep_time, arr_time=arr_time,
                intermediates=intermediate_coords,
            )
            return self._parse_multistop(
                data, start, end, transport_mode, dep_time, arr_time,
                fast_route, eco_route, waypoints,
            )

        data = self.route(
            (origin_lat, origin_lng), (dest_lat, dest_lng),
            mode=mode, dep_time=dep_time, arr_time=arr_time,
        )
        return self._parse_single(
            data, start, end, transport_mode, dep_time, arr_time,
            fast_route, eco_route, origin_lat, origin_lng, dest_lat, dest_lng,
        )

    # ------------------------------------------------------------------ #
    # Internal parsing                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_duration_s(duration_str) -> int:
        if isinstance(duration_str, str) and duration_str.endswith("s"):
            try:
                return int(duration_str[:-1])
            except ValueError:
                pass
        if isinstance(duration_str, int):
            return duration_str
        return 0

    @staticmethod
    def _fmt_dur(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m" if h else f"{m}m"

    def _parse_single(
        self, data, start, end, transport_mode, dep_time, arr_time,
        fast_route, eco_route,
        origin_lat=None, origin_lng=None, dest_lat=None, dest_lng=None,
    ) -> RouteRecommendation:
        if "routes" not in data or not data["routes"]:
            raise KeyError("routes")
        r = data["routes"][0]

        # Extract leg coordinates when not provided by caller
        legs = r.get("legs", [])
        if origin_lat is None and legs:
            start_ll = legs[0].get("startLocation", {}).get("latLng", {})
            origin_lat = start_ll.get("latitude")
            origin_lng = start_ll.get("longitude")
            end_ll = legs[-1].get("endLocation", {}).get("latLng", {})
            dest_lat = end_ll.get("latitude")
            dest_lng = end_ll.get("longitude")

        return RouteRecommendation(
            start=start,
            end=end,
            transport_mode=transport_mode,
            dep_time=dep_time,
            arr_time=arr_time,
            fast_route=fast_route,
            eco_route=eco_route,
            route=r.get("polyline", {}).get("encodedPolyline"),
            duration=r.get("duration", "0s"),
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            distance_meters=r.get("distanceMeters", 0),
            waypoints=[],
            multi_stop_data=None,
        )

    def _parse_multistop(
        self, data, start, end, transport_mode, dep_time, arr_time,
        fast_route, eco_route, waypoints,
    ) -> RouteRecommendation:
        if "routes" not in data or not data["routes"]:
            raise KeyError("routes")
        r = data["routes"][0]

        total_dur_s  = self._parse_duration_s(r.get("duration", "0s"))
        total_dist_m = r.get("distanceMeters", 0)
        all_stops    = [start] + list(waypoints) + [end]

        legs_out = []
        for i, leg in enumerate(r.get("legs", [])):
            leg_dur_s  = self._parse_duration_s(leg.get("duration", "0s"))
            leg_dist_m = leg.get("distanceMeters", 0)
            legs_out.append(RouteLeg(
                from_location     = all_stops[i]     if i     < len(all_stops) else start,
                to_location       = all_stops[i + 1] if i + 1 < len(all_stops) else end,
                duration_seconds  = leg_dur_s,
                duration_formatted= self._fmt_dur(leg_dur_s),
                distance_meters   = leg_dist_m,
                distance_km       = round(leg_dist_m / 1000, 1),
            ))

        multi = MultiStopRoute(
            optimal_route_order      = all_stops,
            total_duration_seconds   = total_dur_s,
            total_duration_formatted = self._fmt_dur(total_dur_s),
            total_distance_km        = round(total_dist_m / 1000, 1),
            number_of_stops          = len(all_stops),
            legs                     = legs_out,
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
            waypoints=list(waypoints),
            multi_stop_data=multi,
        )
