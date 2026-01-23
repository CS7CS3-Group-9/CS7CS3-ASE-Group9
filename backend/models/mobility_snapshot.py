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
        airquality=None,
        population=None,
        alerts=None,
        recommendations=None,
        source_status=None,
    ):
        self.timestamp = timestamp
        self.location = location
        self.bikes = bikes
        self.buses = buses
        self.traffic = traffic
        self.airquality = airquality
        self.population = population
        self.alerts = alerts
        self.recommendations = recommendations
        self.source_status = source_status or {}
