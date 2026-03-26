import json
from pathlib import Path
from flask import Flask

from frontend import auth as auth_mod


def test_safe_next_and_normalise_and_user_role_and_build_rows():
    assert auth_mod._safe_next_url(None) is None
    assert auth_mod._safe_next_url("/ok") == "/ok"
    assert auth_mod._safe_next_url("//evil") is None

    assert auth_mod._normalise_user_record("pass") == {"password": "pass", "role": "admin"}
    assert auth_mod._normalise_user_record({"password_hash": "h", "role": "user"})["role"] == "user"
    assert auth_mod._normalise_user_record({"password": "p"})["password"] == "p"
    assert auth_mod._normalise_user_record(123) is None

    assert auth_mod._user_role("x") == "admin"

    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.test_request_context():
        # test build rows with session
        from flask import session

        session["auth_user"] = "bob"
        rows = auth_mod._build_user_rows({"bob": "p", "alice": {"role": "user"}})
        assert any(r["username"] == "bob" for r in rows)


def test_resolve_and_load_and_save_users(tmp_path, monkeypatch):
    app = Flask(__name__)
    users_file = tmp_path / "users.json"
    data = {"u1": "pass"}
    users_file.write_text(json.dumps(data), encoding="utf-8")

    with app.app_context():
        monkeypatch.setenv("DASHBOARD_USERS_FILE", "")
        # set config to absolute path
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        path = auth_mod._resolve_users_file()
        assert path == Path(str(users_file))
        loaded = auth_mod._load_users_from_file(path)
        assert isinstance(loaded, dict) and "u1" in loaded

        # save new users
        new_users = {"a": {"password": "x"}}
        auth_mod._save_users_to_file(path, new_users)
        assert "a" in json.loads(path.read_text(encoding="utf-8"))


def test_manage_users_and_posts_and_delete(tmp_path, monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps({"admin": {"password": "p", "role": "admin"}}), encoding="utf-8")

    with app.test_request_context("/users"):
        # not admin -> 403 tuple
        from flask import session

        # avoid needing real templates in tests
        monkeypatch.setattr(
            auth_mod, "render_template", lambda template, *a, **kw: kw.get("error") or kw.get("message") or "OK"
        )
        monkeypatch.setattr(auth_mod, "url_for", lambda *a, **kw: "/fake")

        session.clear()
        result = auth_mod.manage_users()
        assert isinstance(result, tuple) and result[1] == 403

    with app.test_request_context("/users"):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        # no config -> message about file
        auth_mod.current_app.config.pop("DASHBOARD_USERS_FILE", None)
        res = auth_mod.manage_users()
        assert "DASHBOARD_USERS_FILE is not set" in res

    with app.test_request_context("/users"):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        out = auth_mod.manage_users()
        assert isinstance(out, str)

    # test manage_users_post errors and success
    with app.test_request_context("/users", method="POST", data={}):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        resp = auth_mod.manage_users_post()
        assert "Username is required" in resp

    with app.test_request_context("/users", method="POST", data={"username": "bob", "password": "x", "confirm": "y"}):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        resp = auth_mod.manage_users_post()
        assert "Passwords do not match" in resp

    with app.test_request_context("/users", method="POST", data={"username": "bob", "password": "x", "confirm": "x"}):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        resp = auth_mod.manage_users_post()
        # redirect on success
        assert resp.status_code == 302

    # test delete_user flows
    with app.test_request_context("/users/delete", method="POST", data={"username": "nonexist"}):
        from flask import session

        session["auth_ok"] = True
        session["auth_role"] = "admin"
        auth_mod.current_app.config["DASHBOARD_USERS_FILE"] = str(users_file)
        resp = auth_mod.delete_user()
        assert isinstance(resp, tuple) and resp[1] == 404
