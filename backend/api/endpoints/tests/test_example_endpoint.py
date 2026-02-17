from backend.app import create_app
from backend.api.contracts import validate_hello_contract


def test_example_hello_contract():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    resp = client.get("/api/hello")
    assert resp.status_code == 200
    data = resp.get_json()
    assert validate_hello_contract(data) == []
