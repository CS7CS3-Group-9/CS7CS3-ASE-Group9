class RouteRecommendation:
    def __init__(self, start, end, transport_mode, dep_time, arr_time, fast_route, eco_route, route, duration):
        self.start = start  # start location
        self.end = end  # end location
        self.transport_mode = transport_mode  # walking, bus, car, bike
        # only one of the following two can be given a value as the other will be calculated
        self.dep_time = dep_time
        self.arr_time = arr_time
        # booleans where if one is true the other MUST be false
        self.fast_route = fast_route  # boolean
        self.eco_route = eco_route  # boolean
        self.route = route  # vector of coordinates to create the route
        self.duration = duration  # duration of journey
