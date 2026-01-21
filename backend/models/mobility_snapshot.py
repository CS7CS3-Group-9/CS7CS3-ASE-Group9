# Unified schema for all data
from datetime import datetime


class MobilitySnapshot:
    def __init__(
        self,
        timestamp: datetime,
        location: str,
        bikes=None,
        buses=None,
        traffic=None,
        events=None,
        source_status=None,
    ):
        self.timestamp = timestamp
        self.location = location
        self.bikes = bikes
        self.buses = buses
        self.traffic = traffic
        self.events = events
        self.source_status = source_status or {}
