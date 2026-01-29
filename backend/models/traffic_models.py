class TrafficIncident:
    """Individual traffic incident"""
    def __init__(
        self,
        category,
        severity,
        description,
        from_location,
        to_location,
        road,
        length_meters,
        delay_seconds,
        delay_minutes
    ):
        self.category = category  # Jam, Road Closed, Accident, etc.
        self.severity = severity  # Major, Moderate, Minor, Undefined
        self.description = description  # Stationary traffic, Queuing traffic, etc.
        self.from_location = from_location
        self.to_location = to_location
        self.road = road
        self.length_meters = length_meters
        self.delay_seconds = delay_seconds
        self.delay_minutes = delay_minutes


class TrafficMetrics:
    """Aggregated traffic metrics for an area"""
    def __init__(
        self,
        congestion_level,
        average_speed,
        total_incidents,
        incidents_by_category,
        incidents_by_severity,
        total_delay_minutes,
        average_delay_minutes,
        incidents  # List of TrafficIncident objects
    ):
        self.congestion_level = congestion_level  # low, medium, high
        self.average_speed = average_speed  # km/h (if available)
        self.total_incidents = total_incidents
        self.incidents_by_category = incidents_by_category  # {"Jam": 13, "Road Closed": 1}
        self.incidents_by_severity = incidents_by_severity  # {"Major": 6, "Moderate": 4}
        self.total_delay_minutes = total_delay_minutes
        self.average_delay_minutes = average_delay_minutes
        self.incidents = incidents  # Full list of TrafficIncident objects


class TrafficSnapshot:
    """Snapshot of traffic data for a location"""
    def __init__(
        self,
        location,
        latitude,
        longitude,
        radius_km,
        timestamp,
        metrics,
        source_status
    ):
        self.location = location
        self.latitude = latitude
        self.longitude = longitude
        self.radius_km = radius_km
        self.timestamp = timestamp
        self.metrics = metrics  # TrafficMetrics object
        self.source_status = source_status  # {"tomtom": "live"}