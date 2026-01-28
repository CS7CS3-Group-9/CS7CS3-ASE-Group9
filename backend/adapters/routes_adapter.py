import requests
from backend.adapters.base_adapter import DataAdapter
from backend.models.route_models import RouteRecommendation, MultiStopRoute, RouteLeg


class RoutesAdapter(DataAdapter):
    """
    Adapter for Google Routes API
    Supports both point-to-point and multi-stop routes
    """
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    def source_name(self) -> str:
        return "routes"
    
    def fetch(
        self, 
        start: str, 
        end: str,
        transport_mode: str = "DRIVE",
        dep_time=None,
        arr_time=None,
        fast_route: bool = False,
        eco_route: bool = False,
        waypoints: list = None  # NEW: List of intermediate stops
    ) -> RouteRecommendation:
        """
        Fetch route recommendation from Google Routes API
        
        Args:
            start: Starting location
            end: Destination location
            transport_mode: DRIVE, WALK, BICYCLE, TRANSIT
            dep_time: Departure time
            arr_time: Arrival time
            fast_route: Optimize for speed
            eco_route: Optimize for fuel efficiency
            waypoints: List of intermediate stops (for multi-stop routes)
            
        Returns:
            RouteRecommendation object
        """
        # Validate inputs
        if dep_time and arr_time:
            raise ValueError("Cannot specify both departure and arrival time")
        
        if fast_route and eco_route:
            raise ValueError("Cannot enable both fast and eco route")
        
        waypoints = waypoints or []
        is_multistop = len(waypoints) > 0
        
        # TODO: Build request payload
        if is_multistop:
            # Multi-stop route with waypoints
            # payload = {
            #     "origin": {"address": start},
            #     "destination": {"address": end},
            #     "intermediates": [{"address": wp} for wp in waypoints],
            #     "travelMode": transport_mode,
            #     "optimizeWaypointOrder": True,
            #     ...
            # }
            pass
        else:
            # Simple point-to-point route
            # payload = {
            #     "origin": {"address": start},
            #     "destination": {"address": end},
            #     "travelMode": transport_mode,
            #     ...
            # }
            pass
        
        # TODO: Make API request
        # headers = {
        #     "Content-Type": "application/json",
        #     "X-Goog-Api-Key": self.api_key,
        #     "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs,routes.polyline.encodedPolyline"
        # }
        # response = requests.post(self.base_url, json=payload, headers=headers, timeout=10)
        # response.raise_for_status()
        # data = response.json()
        
        # TODO: Parse response
        multi_stop_data = None
        if is_multistop:
            # Parse multi-stop response
            # legs = []
            # for leg_data in data.get("legs", []):
            #     leg = RouteLeg(
            #         from_location=leg_data["from"],
            #         to_location=leg_data["to"],
            #         duration_seconds=leg_data["duration_seconds"],
            #         duration_formatted=leg_data["duration_formatted"],
            #         distance_meters=leg_data["distance_meters"],
            #         distance_km=leg_data["distance_km"]
            #     )
            #     legs.append(leg)
            # 
            # multi_stop_data = MultiStopRoute(
            #     optimal_route_order=data["optimal_route_order"],
            #     total_duration_seconds=data["total_duration_seconds"],
            #     total_duration_formatted=data["total_duration_formatted"],
            #     total_distance_km=data["total_distance_km"],
            #     number_of_stops=data["number_of_stops"],
            #     legs=legs
            # )
            pass
        
        # TODO: Create and return RouteRecommendation
        # return RouteRecommendation(
        #     start=start,
        #     end=end,
        #     transport_mode=transport_mode,
        #     dep_time=dep_time,
        #     arr_time=arr_time,
        #     fast_route=fast_route,
        #     eco_route=eco_route,
        #     route=data.get("encoded_polyline"),
        #     duration=data.get("duration"),
        #     origin_lat=data.get("origin", {}).get("coordinates", {}).get("lat"),
        #     origin_lng=data.get("origin", {}).get("coordinates", {}).get("lng"),
        #     dest_lat=data.get("destination", {}).get("coordinates", {}).get("lat"),
        #     dest_lng=data.get("destination", {}).get("coordinates", {}).get("lng"),
        #     distance_meters=data.get("distance_meters"),
        #     waypoints=waypoints,
        #     multi_stop_data=multi_stop_data
        # )
        
        raise NotImplementedError("Route fetching not yet implemented")