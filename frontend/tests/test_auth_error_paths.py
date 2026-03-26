import json
from werkzeug.security import generate_password_hash

from frontend.app import create_app
import frontend.auth as auth_mod


def _make_app(**overrides):
    app = create_app()
    app.config.update(
        TESTING=False,
        SECRET_KEY="test-secret",
        DASHBOARD_USERS={"alice": {"password": "wonderland", "role": "admin"}},
        DASHBOARD_USERS_FILE="",
        DASHBOARD_USER="",
        DASHBOARD_PASS="",
    )
    app.config.update(overrides)
    return app


def test_manage_users_backend_error(monkeypatch):
    app = _make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        # backend request fails
        monkeypatch.setattr(auth_mod, "_backend_request", lambda m, p: (None, "boom"))
        resp = client.get("/users")
    assert b"Unable to fetch users" in resp.data


def test_manage_users_post_validations(monkeypatch):
    app = _make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        # missing username
        resp = client.post("/users", data={"username": "", "password": "p", "confirm": "p"})
        assert b"Username is required" in resp.data

        # missing password
        resp = client.post("/users", data={"username": "bob", "password": "", "confirm": ""})
        assert b"Password is required" in resp.data

        # mismatch
        resp = client.post("/users", data={"username": "bob", "password": "a", "confirm": "b"})
        assert b"Passwords do not match" in resp.data


def test_manage_users_post_backend_error(monkeypatch):
    app = _make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        monkeypatch.setattr(auth_mod, "_backend_request", lambda m, p, payload=None: (None, "err"))
        resp = client.post("/users", data={"username": "bob", "password": "s3cret", "confirm": "s3cret"})
    assert b"Unable to add user" in resp.data


def test_delete_user_missing_and_backend_error(monkeypatch):
    app = _make_app()
    # missing username
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        resp = client.post("/users/delete", data={"username": ""})
        assert resp.status_code == 404
        assert b"User not found" in resp.data

    # backend error when deleting
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        monkeypatch.setattr(auth_mod, "_backend_request", lambda m, p, payload=None: (None, "boom"))
        resp = client.post("/users/delete", data={"username": "bob"})
        assert b"Unable to remove user" in resp.data
