# TDD tests for the dashboard overview route (GET /dashboard)
# TODO: Fixture that creates the Flask test client with app registered
# TODO: test_overview_returns_200 — GET /dashboard returns status 200
# TODO: test_overview_uses_correct_template — response renders index.html
# TODO: test_overview_contains_indicators — mock components/indicators.py
#       and assert indicator data is passed to the template context
# TODO: test_overview_contains_map_data — mock components/maps.py
#       and assert bike + traffic data is present in template context
# TODO: test_overview_data_endpoint — GET /dashboard/data returns valid JSON
#       with keys: indicators, bikes, traffic, air_quality
# TODO: test_overview_handles_backend_failure — mock the backend API call
#       to raise a ConnectionError and assert the route still returns 200
#       with a degraded/error state rather than a 500