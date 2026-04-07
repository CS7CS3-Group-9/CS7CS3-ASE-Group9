from unittest.mock import MagicMock, patch

import requests

from frontend.app import create_app


def _make_app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        BACKEND_API_URL="http://mock-backend",
    )
    return app


def _mock_response(data, status_code=200):
    response = MagicMock()
    response.json.return_value = data
    response.status_code = status_code
    return response


def test_routing_page_renders():
    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/routing")

    assert resp.status_code == 200
    assert b"Route" in resp.data or b"routing" in resp.data.lower()


def test_calculate_forwards_multi_value_query_params():
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.get",
            return_value=_mock_response({"ok": True}, status_code=201),
        ) as mock_get:
            resp = client.get(
                "/routing/calculate",
                query_string=[
                    ("stops[]", "Trinity College"),
                    ("stops[]", "Heuston"),
                    ("locked[]", "true"),
                    ("locked[]", "false"),
                    ("mode", "driving"),
                ],
            )

    assert resp.status_code == 201
    assert resp.get_json() == {"ok": True}
    assert mock_get.call_args.args[0] == "http://mock-backend/routing/calculate"
    assert mock_get.call_args.kwargs["params"] == [
        ("stops[]", "Trinity College"),
        ("stops[]", "Heuston"),
        ("locked[]", "true"),
        ("locked[]", "false"),
        ("mode", "driving"),
    ]


def test_calculate_timeout_returns_504():
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.get",
            side_effect=requests.exceptions.Timeout,
        ):
            resp = client.get("/routing/calculate", query_string={"origin": "A", "destination": "B"})

    assert resp.status_code == 504
    assert "timed out" in resp.get_json()["error"].lower()


def test_local_route_proxies_backend_response():
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.get",
            return_value=_mock_response({"found": True, "distance_m": 1200}),
        ) as mock_get:
            resp = client.get(
                "/routing/local-route",
                query_string={"from_lat": "53.34", "from_lon": "-6.26", "to_lat": "53.35", "to_lon": "-6.25"},
            )

    assert resp.status_code == 200
    assert resp.get_json()["found"] is True
    assert mock_get.call_args.args[0] == "http://mock-backend/traffic/local-route"


def test_network_nodes_returns_backend_json():
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.get",
            return_value=_mock_response({"nodes": [[53.34, -6.26]], "sampled": 1}),
        ):
            resp = client.get("/routing/network-nodes", query_string={"step": "10"})

    assert resp.status_code == 200
    assert resp.get_json()["sampled"] == 1


def test_efficiency_posts_json_body_to_backend():
    payload = {"action": "build", "stops": [{"lat": 53.34, "lon": -6.26}], "vehicles": 1}
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.post",
            return_value=_mock_response({"score": 88}, status_code=202),
        ) as mock_post:
            resp = client.post("/routing/efficiency", json=payload)

    assert resp.status_code == 202
    assert resp.get_json()["score"] == 88
    assert mock_post.call_args.args[0] == "http://mock-backend/routing/efficiency"
    assert mock_post.call_args.kwargs["json"] == payload


def test_network_edges_returns_502_on_backend_error():
    app = _make_app()
    with app.test_client() as client:
        with patch(
            "frontend.dashboard.routing.requests.get",
            side_effect=RuntimeError("backend exploded"),
        ):
            resp = client.get("/routing/network-edges")

    assert resp.status_code == 502
    assert "backend exploded" in resp.get_json()["error"]
