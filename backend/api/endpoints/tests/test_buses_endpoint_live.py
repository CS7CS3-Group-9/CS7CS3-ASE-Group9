from pathlib import Path
import time

from flask import Flask

from backend.api.endpoints import buses as buses_mod


def test_cache_key_and_get_cached_and_stale():
    k = buses_mod._cache_key(5, 53.0, -6.0)
    assert isinstance(k, str) and ":" in k
    # prepare cache entry
    key = buses_mod._cache_key(None, 53.0, -6.0)
    with buses_mod._STOPS_LOCK:
        buses_mod._STOPS_CACHE[key] = {"data": [1, 2, 3], "timestamp": time.time()}
    got = buses_mod._get_cached_stops(key)
    assert got == [1, 2, 3]
    # expire entry
    with buses_mod._STOPS_LOCK:
        buses_mod._STOPS_CACHE[key]["timestamp"] = time.time() - (buses_mod._CACHE_TTL_SECONDS + 10)
    assert buses_mod._get_cached_stops(key) is None


def test_bus_stops_overpass(monkeypatch):
    app = Flask(__name__)

    # Ensure GTFS resolution returns a non-existent file
    class DummyAdapter:
        def __init__(self, gtfs_path=None):
            pass

        def _resolve_stops_file(self):
            return Path("nonexistent_gtfs_stops.csv")

    monkeypatch.setattr(buses_mod, "BusAdapter", DummyAdapter)

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"elements": [{"lat": 53.3, "lon": -6.2, "tags": {"name": "Stop1", "ref": "R1", "route_ref": "1"}}]}

    monkeypatch.setattr(buses_mod.requests, "post", lambda *a, **k: FakeResp())

    # clear _STOPS_CACHE for deterministic behavior
    with buses_mod._STOPS_LOCK:
        buses_mod._STOPS_CACHE.clear()

    with app.test_request_context("/buses/stops"):
        resp = buses_mod.bus_stops()
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list) and data[0]["name"] == "Stop1"

    # call again to exercise cache path
    with app.test_request_context("/buses/stops"):
        resp2 = buses_mod.bus_stops()
        assert resp2.status_code == 200
        assert "Cache-Control" in resp2.headers
