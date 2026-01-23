class TrafficMetrics:
    def __init__(self, congestion_level, average_speed, incidents):
        self.congestion_level = congestion_level  # low, medium, high
        self.average_speed = average_speed  # km/h
        self.incidents = incidents  # number of incidents
