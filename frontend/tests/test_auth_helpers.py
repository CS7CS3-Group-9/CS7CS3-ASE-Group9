from types import SimpleNamespace

from frontend.app import create_app
import frontend.auth as auth_mod


def test_safe_next_url():
    assert auth_mod._safe_next_url(None) is None
    assert auth_mod._safe_next_url("") is None
    assert auth_mod._safe_next_url("/dashboard") == "/dashboard"
    assert auth_mod._safe_next_url("//evil") is None
    assert auth_mod._safe_next_url("https://example.com") is None


def test_backend_login_success_and_failure(monkeypatch):
    app = create_app()

    # success
    def fake_post_success(url, json=None, timeout=None):
        class R:
            status_code = 200

            def json(self):
                return {"role": "admin"}

        return R()

    monkeypatch.setattr(auth_mod, "requests", SimpleNamespace(post=fake_post_success))
    with app.app_context():
        ok, role, err = auth_mod._backend_login("alice", "pwd")
    assert ok is True
    assert role == "admin"
    assert err is None

    # invalid credentials
    def fake_post_401(url, json=None, timeout=None):
        class R:
            status_code = 401

            def json(self):
                return {}

        return R()

    monkeypatch.setattr(auth_mod, "requests", SimpleNamespace(post=fake_post_401))
    with app.app_context():
        ok, role, err = auth_mod._backend_login("alice", "bad")
    assert ok is False
    assert role is None
    assert "Invalid" in (err or "")

    # exception path
    def fake_post_exc(url, json=None, timeout=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(auth_mod, "requests", SimpleNamespace(post=fake_post_exc))
    with app.app_context():
        ok, role, err = auth_mod._backend_login("alice", "pwd")
    assert ok is False
    assert role is None
    assert "boom" in (err or "")


def test_backend_request_missing_and_error(monkeypatch):
    app = create_app()
    # missing credentials in session
    monkeypatch.setattr(auth_mod, "session", {})
    with app.app_context():
        data, err = auth_mod._backend_request("GET", "/auth/users")
    assert data is None
    assert "Missing" in err

    # request raises exception
    monkeypatch.setattr(auth_mod, "session", {"auth_user": "alice", "auth_pass": "pwd"})

    def fake_request_exc(method, url, json=None, auth=None, timeout=None):
        raise ValueError("net error")

    monkeypatch.setattr(auth_mod, "requests", SimpleNamespace(request=fake_request_exc))
    with app.app_context():
        data, err = auth_mod._backend_request("GET", "/auth/users")
    assert data is None
    assert "net error" in err


def test_is_admin_checks_session(monkeypatch):
    monkeypatch.setattr(auth_mod, "session", {"auth_ok": True, "auth_role": "admin"})
    assert auth_mod._is_admin() is True
    monkeypatch.setattr(auth_mod, "session", {"auth_ok": True, "auth_role": "user"})
    assert auth_mod._is_admin() is False
