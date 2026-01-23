class BusRouteMetrics:
    def __init__(self, route_id, stop_count, schedule, frequency):
        self.route_id = route_id
        self.stop_count = stop_count
        self.schedule = schedule  # designed bus schedule for route
        self.frequency = frequency  # how often should the bus come


class BusSystemMetrics:
    def __init__(self, route_id, active_buses, average_delay):
        self.route_id = route_id
        self.active_buses = active_buses  # number of active buses for specified route
        self.average_delay = average_delay
