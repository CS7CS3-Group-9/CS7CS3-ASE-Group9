import math

from frontend.dashboard import overview


def test_parse_radius_km_valid_and_bounds():
    assert overview._parse_radius_km("10") == 10.0
    assert overview._parse_radius_km("0.2") == 1.0
    assert overview._parse_radius_km("100") == 50.0
    assert overview._parse_radius_km(None) == 5.0
    assert overview._parse_radius_km("abc") == 5.0


def test_distance_and_within_radius():
    d0 = overview._distance_km(overview._DUBLIN_LAT, overview._DUBLIN_LON, overview._DUBLIN_LAT, overview._DUBLIN_LON)
    assert isinstance(d0, float) and abs(d0) < 1e-6
    assert overview._within_radius_km(overview._DUBLIN_LAT, overview._DUBLIN_LON, 1)
    assert not overview._within_radius_km(overview._DUBLIN_LAT + 10, overview._DUBLIN_LON + 10, 1)


def test_filter_points_within_radius_and_missing_coords():
    pts = [{"lat": overview._DUBLIN_LAT, "lon": overview._DUBLIN_LON}, {"lat": None, "lon": -6}, {"foo": "bar"}]
    res = overview._filter_points_within_radius(pts, None)
    assert res == pts
    res2 = overview._filter_points_within_radius(pts, 1)
    assert res2 == [pts[0]]


def test_build_bike_metrics_and_station_helpers():
    assert overview._build_bike_metrics([]) is None
    stations = [
        {"free_bikes": 3, "empty_slots": 2, "total": 5, "name": "A", "station_id": "1"},
        {"free_bikes": 2, "empty_slots": 1, "capacity": 4, "station_id": "2"},
    ]
    metrics = overview._build_bike_metrics(stations)
    assert metrics["available_bikes"] == 5
    assert metrics["available_docks"] == 3
    assert metrics["stations_reporting"] == 2

    assert overview._station_total({"total": "3"}) == 3.0
    assert overview._station_total({"capacity": "7"}) == 7.0
    assert overview._station_total({"capacity": "bad"}) == 0.0
    assert overview._station_value({"free_bikes": "2"}, "free_bikes") == 2.0
    assert overview._station_value({"free_bikes": "bad"}, "free_bikes") == 0.0


def test_top_used_and_needing_more_docks_format():
    stations = [
        {"name": "S1", "total": 10, "free_bikes": 1, "empty_slots": 9},
        {"station_id": "S2", "capacity": 5, "free_bikes": 4, "empty_slots": 1},
        {"name": "Zero", "total": 0, "free_bikes": 0, "empty_slots": 0},
    ]
    top = overview._top_used_bike_stations(stations, limit=2)
    assert len(top) == 2
    assert any("S1" in t or "S2" in t for t in top)
    docks = overview._stations_needing_more_docks(stations, limit=2)
    assert len(docks) == 2
    assert "docks free" in docks[0]


def test_nearest_and_max_distance_and_tracked_overlap():
    points = [
        {"lat": overview._DUBLIN_LAT, "lon": overview._DUBLIN_LON},
        {"lat": overview._DUBLIN_LAT + 0.1, "lon": overview._DUBLIN_LON + 0.1},
    ]
    nearest = overview._nearest_distance_km(overview._DUBLIN_LAT, overview._DUBLIN_LON, points)
    assert nearest is not None and nearest >= 0
    maxd = overview._max_distance_from_centre_km(points)
    assert maxd is not None and maxd >= 0
    assert overview._tracked_overlap_km(points, points) == min(maxd, maxd)


def test_get_population_centres_and_needs_behaviour():
    centres = overview._get_population_centres()
    assert isinstance(centres, list) and len(centres) > 0
    # empty bus stops -> no needs
    assert overview._needs_bus_areas([], [], None) == []
    # cached needs retrieval
    bus, bike = overview._get_needs_cached([], [], None)
    assert isinstance(bus, list) and isinstance(bike, list)
    # cache stale retrieval
    cache = {}
    overview._cache_set(cache, "k", {"x": 1})
    assert overview._cache_get_stale(cache, "k") == {"x": 1}
