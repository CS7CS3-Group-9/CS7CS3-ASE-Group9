from dataclasses import dataclass, field
from typing import List, Dict, Any


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
    stop_arrivals_next_hour: Dict[str, int] = field(default_factory=dict)  # stop_id -> arrivals within 1 hour
    stop_avg_wait_min: Dict[str, float] = field(default_factory=dict)  # stop_id -> avg wait in minutes
    stop_importance_scores: Dict[str, float] = field(default_factory=dict)  # stop_id -> importance score
    top_served_stops: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics
    wait_time_summary: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics
    wait_time_counts: Dict[str, int] = field(default_factory=dict)  # good/ok/poor counts
    wait_time_best: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics (lowest waits)
    wait_time_worst: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics (highest waits)
    wait_exposure_top: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics (highest exposure)
    wait_exposure_stats: Dict[str, Any] = field(default_factory=dict)  # derived analytics (summary stats)
    wait_exposure_metric: Dict[str, Any] = field(default_factory=dict)  # derived analytics (metric metadata)
    wait_exposure_by_stop: Dict[str, float] = field(default_factory=dict)  # stop_id -> exposure value
    top_importance_stops: List[Dict[str, Any]] = field(default_factory=list)  # derived analytics
    total_stops: int = 0
    total_routes: int = 0
