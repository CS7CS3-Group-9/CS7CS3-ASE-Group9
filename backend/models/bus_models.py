from dataclasses import dataclass, field
from typing import List


@dataclass
class BusStop:
    stop_id: str
    name: str
    lat: float
    longitude: float


@dataclass
class BusRoute:
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: str
    route_type: int  # 0 = tram, 1 = subway, 2 = rail, 3 = bus, etc.
    # Optional: add route_color, route_text_color, etc. as needed


@dataclass
class BusMetrics:
    """
    Container for bus stop and route data.
    """

    stops: List[BusStop] = field(default_factory=list)
    routes: List[BusRoute] = field(default_factory=list)
    total_stops: int = 0
    total_routes: int = 0
