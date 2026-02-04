from backend.models.traffic_models import TrafficMetrics


def build_traffic_metrics(incidents, radius_km: float) -> TrafficMetrics:
    total = len(incidents)

    by_category = {}
    by_severity = {}

    for inc in incidents:
        if inc.category is not None:
            by_category[inc.category] = by_category.get(inc.category, 0) + 1
        if inc.severity is not None:
            by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1

    total_delay = sum((inc.delay_minutes or 0) for inc in incidents)
    avg_delay = total_delay / total if total else 0

    incidents_per_km = total / radius_km if radius_km and radius_km > 0 else 0
    if incidents_per_km > 5:
        congestion = "high"
    elif incidents_per_km > 2:
        congestion = "medium"
    else:
        congestion = "low"

    avg_speed = 15 if congestion == "high" else 30 if congestion == "medium" else 50

    return TrafficMetrics(
        congestion_level=congestion,
        average_speed=avg_speed,
        total_incidents=total,
        incidents_by_category=by_category,
        incidents_by_severity=by_severity,
        total_delay_minutes=total_delay,
        average_delay_minutes=avg_delay,
        incidents=incidents,
    )
