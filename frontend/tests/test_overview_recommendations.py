import copy

from frontend.dashboard import overview as ov


def test_filter_traffic_within_radius_and_congestion_levels():
    traffic = {
        "incidents": [
            {"latitude": 53.3498, "longitude": -6.2603, "category": "accident", "severity": 2, "delay_minutes": 10},
            {"latitude": 53.3500, "longitude": -6.2600, "category": "roadworks", "severity": 1, "delay_minutes": 5},
        ]
    }
    # small radius -> high incidents per km
    out = ov._filter_traffic_within_radius(traffic, 0.1)
    assert out["total_incidents"] == 2
    assert out["congestion_level"] in ("high", "medium", "low")

    # None traffic passes through unchanged
    assert ov._filter_traffic_within_radius(None, 5) is None


def test_build_recommendations_multiple_branches(monkeypatch):
    # prepare inputs that trigger many recommendation branches
    bikes = {"available_bikes": 5}
    traffic = {"congestion_level": "high", "total_incidents": 12}
    airquality = {"aqi_value": 120}
    bike_stations = [
        {"name": "A", "total": 10, "free_bikes": 1, "empty_slots": 9},
        {"name": "B", "station_id": "S2", "total": 20, "free_bikes": 2, "empty_slots": 18},
    ]
    buses = {"wait_time_worst": [{"name": "Stop1", "avg_wait_min": 75}, {"stop_id": "S2", "avg_wait_min": 50}]}

    # ensure needs sections are present
    fake_need_bus = [{"name": "FarAway", "bus_km": 2.5, "bike_km": 2.5, "lat": 0, "lon": 0}]
    fake_need_bike = [{"name": "FarAwayB", "bus_km": 2.0, "bike_km": 2.0, "lat": 0, "lon": 0}]
    monkeypatch.setattr(ov, "_get_needs_cached", lambda a, b, r: (fake_need_bus, fake_need_bike))

    recs = ov._build_recommendations(
        bikes, traffic, airquality, bike_stations=bike_stations, bus_stops=None, buses=buses, radius_km=None
    )
    titles = {r["title"] for r in recs}
    assert any("High" in t or "Low" in t or "Add" in t or "Long Wait" in t for t in titles)


def test_build_recommendations_bike_availability_and_shift(monkeypatch):
    # bikes abundant
    bikes = {"available_bikes": 200}
    traffic = {"congestion_level": "low", "total_incidents": 0}
    airquality = {"aqi_value": 10}
    monkeypatch.setattr(ov, "_get_needs_cached", lambda a, b, r: ([], []))
    recs = ov._build_recommendations(
        bikes, traffic, airquality, bike_stations=None, bus_stops=None, buses=None, radius_km=None
    )
    # should contain the Good Bike Availability recommendation
    assert any(r.get("source") == "bikes" and "Good" in r.get("title", "") for r in recs)
