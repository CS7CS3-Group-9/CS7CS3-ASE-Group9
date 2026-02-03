class Attraction:
    """Individual attraction with all details"""

    def __init__(
        self,
        attraction_id,
        attraction_name,
        attraction_type,
        latitude,
        longitude,
        open_times=None,
        website=None,
        phone=None,
        wheelchair_accessible=None,
        tags=None,
    ):
        self.attraction_id = attraction_id
        self.attraction_name = attraction_name
        self.attraction_type = attraction_type  # museum, castle, park, etc.
        self.latitude = latitude
        self.longitude = longitude
        self.open_times = open_times
        self.website = website
        self.phone = phone
        self.wheelchair_accessible = wheelchair_accessible
        self.tags = tags or {}  # Additional OSM tags


class AttractionMetrics:
    """Aggregated metrics for attractions in an area"""

    def __init__(
        self,
        total_attractions,
        attractions_by_type,
        wheelchair_accessible_count,
        attractions,  # List of Attraction objects
    ):
        self.total_attractions = total_attractions
        self.attractions_by_type = attractions_by_type  # Dict: {"museum": 3, "castle": 1}
        self.wheelchair_accessible_count = wheelchair_accessible_count
        self.attractions = attractions  # Full list of Attraction objects
