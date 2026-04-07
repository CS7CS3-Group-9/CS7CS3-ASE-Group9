from backend.app import create_app


def test_create_app_and_test_firestore():
    app = create_app()
    client = app.test_client()
    # call the test-firestore endpoint which should return 500 when Firestore not enabled
    resp = client.get("/test-firestore")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data.get("status") == "error"
