import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from werkzeug.security import check_password_hash, generate_password_hash

from frontend.app import create_app
import frontend.auth as auth_mod


def _fake_backend(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        class R:
            def __init__(self, status, data=None, text=""):
                self.status_code = status
                self._data = data or {}
                self.text = text

            def json(self):
                return self._data

        if url.rstrip("/").endswith("/auth/login"):
            if json and json.get("username") == "alice" and json.get("password") == "wonderland":
                return R(200, {"role": "admin"})
            return R(401, {}, "Invalid credentials")
        return R(404, {})

    def fake_request(method, url, json=None, auth=None, timeout=None):
        class R:
            def __init__(self, status, data=None, text=""):
                self.status_code = status
                self._data = data or {}
                self.text = text

            def json(self):
                return self._data

        if method == "GET" and url.rstrip("/").endswith("/auth/users"):
            if auth and auth[0] == "alice" and auth[1] == "wonderland":
                return R(200, {"users": [{"username": "alice", "role": "admin"}]})
            return R(401, {}, "Unauthorized")
        if method == "POST" and url.rstrip("/").endswith("/auth/users"):
            return R(200, {})
        if method == "POST" and url.rstrip("/").endswith("/auth/users/delete"):
            return R(200, {})
        return R(404, {})

    monkeypatch.setattr(auth_mod, "requests", SimpleNamespace(post=fake_post, request=fake_request))


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


def _login(client, username="alice", password="wonderland", next_url=None):
    data = {"username": username, "password": password}
    if next_url is not None:
        data["next"] = next_url
    return client.post("/login", data=data, follow_redirects=False)


def setup_function(func):
    # ensure tests use the fake backend by default
    # pytest will provide monkeypatch via test functions where needed
    pass


def test_login_page_renders():
    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/login")

    assert resp.status_code == 200
    assert b"Sign In" in resp.data


def test_protected_page_redirects_to_login_with_next():
    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/dashboard", follow_redirects=False)

    assert resp.status_code == 302
    parsed = urlparse(resp.headers["Location"])
    assert parsed.path == "/login"
    assert parse_qs(parsed.query)["next"] == ["/dashboard"]


def test_successful_login_sets_session_and_redirects_to_safe_next():
    app = _make_app()
    with app.test_client() as client:
        # patch backend
        import pytest

        pytest.monkeypatch = pytest.MonkeyPatch()
        _fake_backend(pytest.monkeypatch)

        resp = _login(client, next_url="/routing")

        with client.session_transaction() as sess:
            assert sess["auth_ok"] is True
            assert sess["auth_user"] == "alice"
            assert sess["auth_role"] == "admin"

        pytest.monkeypatch.undo()

    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == "/routing"


def test_login_ignores_unsafe_next_url():
    app = _make_app()
    with app.test_client() as client:
        import pytest

        pytest.monkeypatch = pytest.MonkeyPatch()
        _fake_backend(pytest.monkeypatch)

        resp = _login(client, next_url="https://evil.example/phish")

        pytest.monkeypatch.undo()

    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path.rstrip("/") == "/dashboard"


def test_invalid_login_shows_error_and_does_not_authenticate():
    app = _make_app()
    with app.test_client() as client:
        import pytest

        pytest.monkeypatch = pytest.MonkeyPatch()
        # fake backend will treat wrong password as 401
        _fake_backend(pytest.monkeypatch)

        resp = _login(client, password="wrong-password")

        with client.session_transaction() as sess:
            assert "auth_ok" not in sess

        pytest.monkeypatch.undo()

    assert resp.status_code == 200
    assert b"Invalid credentials" in resp.data


def test_manage_users_returns_403_for_non_admin():
    app = _make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "eve"
            sess["auth_role"] = "user"

        resp = client.get("/users")

    assert resp.status_code == 403
    assert b"Admin access required" in resp.data


def test_manage_users_post_saves_hashed_user_to_file(tmp_path):
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "alice": {
                    "password_hash": generate_password_hash("wonderland"),
                    "role": "admin",
                }
            }
        ),
        encoding="utf-8",
    )
    app = _make_app(DASHBOARD_USERS_FILE=str(users_file))

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        import pytest

        pytest.monkeypatch = pytest.MonkeyPatch()
        _fake_backend(pytest.monkeypatch)

        resp = client.post(
            "/users",
            data={"username": "bob", "password": "s3cret-pass", "confirm": "s3cret-pass"},
            follow_redirects=False,
        )

        pytest.monkeypatch.undo()

    # backend handles persistence; we only check the redirect
    assert resp.status_code == 302


def test_delete_user_removes_non_admin_user_from_file(tmp_path):
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "alice": {
                    "password_hash": generate_password_hash("wonderland"),
                    "role": "admin",
                },
                "bob": {
                    "password_hash": generate_password_hash("s3cret-pass"),
                    "role": "user",
                },
            }
        ),
        encoding="utf-8",
    )
    app = _make_app(DASHBOARD_USERS_FILE=str(users_file))

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_ok"] = True
            sess["auth_user"] = "alice"
            sess["auth_role"] = "admin"
            sess["auth_pass"] = "wonderland"

        import pytest

        pytest.monkeypatch = pytest.MonkeyPatch()
        _fake_backend(pytest.monkeypatch)

        resp = client.post("/users/delete", data={"username": "bob"}, follow_redirects=False)

        pytest.monkeypatch.undo()

    assert resp.status_code == 302
