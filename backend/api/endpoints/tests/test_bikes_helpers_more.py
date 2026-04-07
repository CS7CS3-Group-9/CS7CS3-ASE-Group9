from flask import Flask

from backend.api.endpoints import bikes as bikes_mod


def test_parse_radius_and_coord_and_adapter_cache():
    assert bikes_mod._parse_radius_km(None) is None
    assert bikes_mod._parse_radius_km("0.05") == 0.1
    assert bikes_mod._parse_radius_km("1000") == 50.0
    assert bikes_mod._parse_radius_km("bad") is None

    # coord parsing with default
    assert bikes_mod._parse_coord(None, 1.23) == 1.23
    assert bikes_mod._parse_coord("3.4", 1.23) == 3.4
    assert bikes_mod._parse_coord("bad", 1.23) == 1.23

    app = Flask(__name__)
    with app.app_context():
        # ensure cache is created and stored on current_app
        cache = bikes_mod._get_adapter_cache()
        assert cache is not None
        # subsequent call returns same object
        cache2 = bikes_mod._get_adapter_cache()
        assert cache2 is cache
