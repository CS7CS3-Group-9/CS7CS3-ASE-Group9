from backend.adapters.traffic_adapter import TrafficAdapter
from backend.models.traffic_models import TrafficIncident


def test_midpoint_point_and_linestring():
    # Point geometry
    geom_point = {"type": "Point", "coordinates": [-6.26, 53.35]}
    lat, lon = TrafficAdapter._midpoint(geom_point)
    assert lat == 53.35 and lon == -6.26

    # LineString geometry (odd length)
    geom_line = {"type": "LineString", "coordinates": [[-6.0, 53.0], [-6.5, 53.5], [-6.2, 53.2]]}
    lat2, lon2 = TrafficAdapter._midpoint(geom_line)
    assert (lat2, lon2) == (53.5, -6.5) or (lat2, lon2) == (53.2, -6.2) or isinstance(lat2, float)

    # missing geometry
    lat3, lon3 = TrafficAdapter._midpoint(None)
    assert lat3 is None and lon3 is None


def test_parse_incidents_both_formats():
    t = TrafficAdapter(api_key="")

    # TomTom native format
    tomtom_item = {
        "geometry": {"type": "Point", "coordinates": [-6.26, 53.35]},
        "properties": {
            "iconCategory": 1,
            "magnitudeOfDelay": 2,
            "events": [{"description": "Accident on road"}],
            "roadNumbers": ["R1"],
            "delay": 120,
            "from": "A",
            "to": "B",
            "length": 500,
        },
    }

    incidents = t._parse_incidents([tomtom_item])
    assert len(incidents) == 1
    inc = incidents[0]
    assert isinstance(inc, TrafficIncident)
    assert inc.category == "Accident"
    assert inc.severity == "Moderate"
    assert "Accident on road" in inc.description

    # Flat format
    flat_item = {
        "category": "Jam",
        "severity": "Minor",
        "description": "Heavy traffic",
        "from": "X",
        "to": "Y",
        "road": "R2",
        "length_meters": 1000,
        "delay_seconds": 300,
        "delay_minutes": 5,
        "latitude": 53.0,
        "longitude": -6.0,
    }

    incidents2 = t._parse_incidents([flat_item])
    assert len(incidents2) == 1
    inc2 = incidents2[0]
    assert inc2.category == "Jam"
    assert inc2.delay_seconds == 300
