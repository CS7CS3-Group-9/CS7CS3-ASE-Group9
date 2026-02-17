from dataclasses import dataclass, field
from typing import List, Dict


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
    route_type: int


@dataclass
class BusMetrics:
    stops: List[BusStop] = field(default_factory=list)
    routes: List[BusRoute] = field(default_factory=list)
    stop_frequencies: Dict[str, int] = field(default_factory=dict)  # stop_id -> trip count
    total_stops: int = 0
    total_routes: int = 0
