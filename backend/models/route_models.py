class RouteLeg:
    """Represents one segment of a multi-stop journey"""
    def __init__(
        self,
        from_location,
        to_location,
        duration_seconds,
        duration_formatted,
        distance_meters,
        distance_km
    ):
        self.from_location = from_location
        self.to_location = to_location
        self.duration_seconds = duration_seconds
        self.duration_formatted = duration_formatted
        self.distance_meters = distance_meters
        self.distance_km = distance_km


class MultiStopRoute:
    """Route with multiple waypoints/stops"""
    def __init__(
        self,
        optimal_route_order,
        total_duration_seconds,
        total_duration_formatted,
        total_distance_km,
        number_of_stops,
        legs
    ):
        self.optimal_route_order = optimal_route_order  # List of stop names in order
        self.total_duration_seconds = total_duration_seconds
        self.total_duration_formatted = total_duration_formatted
        self.total_distance_km = total_distance_km
        self.number_of_stops = number_of_stops
        self.legs = legs  # List of RouteLeg objects


class RouteRecommendation:
    """Single point-to-point route OR multi-stop route"""
    def __init__(
        self, 
        start, 
        end, 
        transport_mode=None, 
        dep_time=None, 
        arr_time=None, 
        fast_route=False, 
        eco_route=False, 
        route=None, 
        duration=None,
        origin_lat=None,
        origin_lng=None,
        dest_lat=None,
        dest_lng=None,
        distance_meters=None,
        waypoints=None,  # NEW: List of intermediate stops
        multi_stop_data=None  # NEW: MultiStopRoute object
    ):
        self.start = start
        self.end = end
        self.transport_mode = transport_mode
        
        if dep_time and arr_time:
            raise ValueError("Cannot specify both departure and arrival time")
        self.dep_time = dep_time
        self.arr_time = arr_time
        
        if fast_route and eco_route:
            raise ValueError("Cannot enable both fast and eco route")
        self.fast_route = fast_route
        self.eco_route = eco_route
        
        self.route = route
        self.duration = duration
        
        self.origin_lat = origin_lat
        self.origin_lng = origin_lng
        self.dest_lat = dest_lat
        self.dest_lng = dest_lng
        self.distance_meters = distance_meters
        
        # NEW: Multi-stop route support
        self.waypoints = waypoints or []
        self.multi_stop_data = multi_stop_data
        
    def is_multi_stop(self):
        """Check if this is a multi-stop route"""
        return len(self.waypoints) > 0 or self.multi_stop_data is not None