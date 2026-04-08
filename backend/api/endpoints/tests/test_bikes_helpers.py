from flask import Flask

from backend.api.endpoints import bikes


def test_parse_radius_and_coord_and_distance():
    # radius parsing
    assert bikes._parse_radius_km(None) is None
    assert bikes._parse_radius_km("abc") is None
    assert bikes._parse_radius_km("0.01") == 0.1
    assert bikes._parse_radius_km("100") == 50.0

    # coord parsing with default
    assert bikes._parse_coord(None, 1.23) == 1.23
    assert bikes._parse_coord("bad", 1.23) == 1.23
    assert bikes._parse_coord("53.1", 1.23) == 53.1

    # distance sanity: zero distance for same point
    d = bikes._distance_km(53.3498, -6.2603, 53.3498, -6.2603)
    assert abs(d) < 1e-6


def test_get_adapter_cache_app_context():
    app = Flask(__name__)
    with app.app_context():
        cache = bikes._get_adapter_cache()
        assert cache is not None
        # subsequent call should return same instance from config
        cache2 = bikes._get_adapter_cache()
        assert cache is cache2
