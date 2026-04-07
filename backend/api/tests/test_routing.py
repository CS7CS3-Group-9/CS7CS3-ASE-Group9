from flask import Flask

from backend.api.endpoints import routing as routing_module


def _make_client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routing_module.routing_api_bp)
    return app.test_client()


def _sample_route(local_fallback=False):
    return {
        "geometry": {"type": "LineString", "coordinates": [[-6.26, 53.34], [-6.25, 53.35]]},
        "distance_meters": 1500,
        "distance_km": 1.5,
        "duration_seconds": 600,
        "duration_minutes": 10,
        "steps": [{"instruction": "Head north", "distance_m": 100, "duration_s": 30}],
        "local_fallback": local_fallback,
    }


class FakeAdapter:
    def __init__(self, mapping):
        self._mapping = mapping
        self.calls = []

    def geocode(self, raw):
        self.calls.append(raw)
        result = self._mapping[raw]
        if isinstance(result, Exception):
            raise result
        return result


def test_calculate_requires_at_least_two_locations():
    client = _make_client()

    resp = client.get("/routing/calculate", query_string=[("stops[]", "Only one stop")])

    assert resp.status_code == 400
    assert "origin and destination" in resp.get_json()["error"].lower()


def test_calculate_accepts_origin_and_destination_params(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "Start": (53.34, -6.26, "Start"),
            "Finish": (53.35, -6.25, "Finish"),
        }
    )
    captured = {}

    def fake_call_routes(ordered_coords, g_mode, dep_time=None, arr_time=None):
        captured["ordered_coords"] = ordered_coords
        captured["g_mode"] = g_mode
        return _sample_route()

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_call_routes", fake_call_routes)

    resp = client.get("/routing/calculate", query_string={"origin": "Start", "destination": "Finish"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert [stop["input"] for stop in data["stops"]] == ["Start", "Finish"]
    assert captured["ordered_coords"] == [(53.34, -6.26), (53.35, -6.25)]
    assert captured["g_mode"] == "DRIVE"


def test_calculate_uses_nominatim_when_primary_geocoder_fails(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter({"Trinity College": RuntimeError("google down"), "Heuston": (53.35, -6.29, "Heuston")})

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(
        routing_module,
        "_geocode_nominatim",
        lambda address: (53.3438, -6.2546, "Trinity College Dublin"),
    )
    monkeypatch.setattr(routing_module, "_call_routes", lambda *args, **kwargs: _sample_route())

    resp = client.get(
        "/routing/calculate",
        query_string=[("stops[]", "Trinity College"), ("stops[]", "Heuston")],
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["stops"][0]["name"] == "Trinity College Dublin"
    assert data["stops"][1]["name"] == "Heuston"


def test_calculate_transit_mode_returns_transit_payload(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "A": (53.34, -6.26, "A"),
            "B": (53.35, -6.25, "B"),
        }
    )
    transit_route = {
        "legs": [
            {"mode": "BUS", "from_name": "A", "to_name": "B", "duration_s": 420, "distance_m": 1200, "coords": []}
        ],
        "geometry": {"type": "LineString", "coordinates": [[-6.26, 53.34], [-6.25, 53.35]]},
        "distance_meters": 1200,
        "distance_km": 1.2,
        "duration_seconds": 420,
        "duration_minutes": 7,
    }

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_call_transit", lambda *args, **kwargs: (transit_route, None))

    resp = client.get(
        "/routing/calculate",
        query_string=[("stops[]", "A"), ("stops[]", "B"), ("mode", "transit")],
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "transit"
    assert data["is_transit"] is True
    assert data["waypoint_order_changed"] is False
    assert data["route"]["distance_meters"] == 1200


def test_calculate_optimizes_unlocked_waypoints(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "A": (53.3400, -6.2600, "A"),
            "B": (53.3410, -6.2610, "B"),
            "C": (53.3420, -6.2620, "C"),
            "D": (53.3430, -6.2630, "D"),
        }
    )
    captured = {}

    def fake_optimize(all_coords, g_mode, locked):
        captured["all_coords"] = all_coords
        captured["g_mode"] = g_mode
        captured["locked"] = locked
        return [0, 2, 1, 3]

    def fake_call_routes(ordered_coords, g_mode, dep_time=None, arr_time=None):
        captured["ordered_coords"] = ordered_coords
        return _sample_route()

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_optimize_stop_order", fake_optimize)
    monkeypatch.setattr(routing_module, "_call_routes", fake_call_routes)

    resp = client.get(
        "/routing/calculate",
        query_string=[
            ("stops[]", "A"),
            ("stops[]", "B"),
            ("stops[]", "C"),
            ("stops[]", "D"),
        ],
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert [stop["name"] for stop in data["stops"]] == ["A", "C", "B", "D"]
    assert data["waypoint_order_changed"] is True
    assert captured["locked"] == [True, False, False, True]
    assert captured["ordered_coords"] == [
        (53.3400, -6.2600),
        (53.3420, -6.2620),
        (53.3410, -6.2610),
        (53.3430, -6.2630),
    ]


def test_calculate_eco_driving_switches_to_cycling(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "Origin": (53.34, -6.26, "Origin"),
            "Destination": (53.35, -6.25, "Destination"),
        }
    )
    captured = {}

    def fake_call_routes(ordered_coords, g_mode, dep_time=None, arr_time=None):
        captured["g_mode"] = g_mode
        return _sample_route()

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_call_routes", fake_call_routes)

    resp = client.get(
        "/routing/calculate",
        query_string=[
            ("stops[]", "Origin"),
            ("stops[]", "Destination"),
            ("mode", "driving"),
            ("type", "eco"),
        ],
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "cycling"
    assert "lower-emission" in data["eco_note"]
    assert captured["g_mode"] == "BICYCLE"


def test_calculate_uses_local_fallback_for_two_stop_driving_routes(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "Origin": (53.34, -6.26, "Origin"),
            "Destination": (53.35, -6.25, "Destination"),
        }
    )

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_call_routes", lambda *args, **kwargs: None)
    monkeypatch.setattr(routing_module, "_call_local_route", lambda *args, **kwargs: _sample_route(local_fallback=True))

    resp = client.get(
        "/routing/calculate",
        query_string=[("stops[]", "Origin"), ("stops[]", "Destination")],
    )

    assert resp.status_code == 200
    assert resp.get_json()["route"]["local_fallback"] is True


def test_calculate_returns_404_when_no_route_found(monkeypatch):
    client = _make_client()
    adapter = FakeAdapter(
        {
            "Origin": (53.34, -6.26, "Origin"),
            "Destination": (53.35, -6.25, "Destination"),
        }
    )

    monkeypatch.setattr(routing_module, "_adapter", adapter)
    monkeypatch.setattr(routing_module, "_call_routes", lambda *args, **kwargs: None)
    monkeypatch.setattr(routing_module, "_call_local_route", lambda *args, **kwargs: None)

    resp = client.get(
        "/routing/calculate",
        query_string=[("stops[]", "Origin"), ("stops[]", "Destination")],
    )

    assert resp.status_code == 404
    assert "no route found" in resp.get_json()["error"].lower()


def test_calculate_rejects_departure_and_arrival_time_together():
    client = _make_client()

    resp = client.get(
        "/routing/calculate",
        query_string=[
            ("stops[]", "Origin"),
            ("stops[]", "Destination"),
            ("dep_time", "2026-03-24T09:00"),
            ("arr_time", "2026-03-24T10:00"),
        ],
    )

    assert resp.status_code == 400
    assert "either departure time or arrival time" in resp.get_json()["error"].lower()
