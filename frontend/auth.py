import requests
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    return None


def _backend_url() -> str:
    return current_app.config.get("BACKEND_API_URL", "http://localhost:5000").rstrip("/")


def _backend_login(username: str, password: str) -> tuple[bool, str | None, str | None]:
    try:
        resp = requests.post(
            f"{_backend_url()}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
    except Exception as e:
        return False, None, str(e)
    if resp.status_code != 200:
        return False, None, "Invalid credentials"
    data = resp.json() or {}
    return True, data.get("role") or "user", None


def _backend_request(method: str, path: str, payload: dict | None = None):
    username = session.get("auth_user")
    password = session.get("auth_pass")
    if not username or not password:
        return None, "Missing admin credentials in session."
    try:
        resp = requests.request(
            method,
            f"{_backend_url()}{path}",
            json=payload,
            auth=(username, password),
            timeout=8,
        )
    except Exception as e:
        return None, str(e)
    if resp.status_code >= 400:
        return None, resp.text
    return resp.json(), None


def _is_admin() -> bool:
    return session.get("auth_ok") and session.get("auth_role", "user") == "admin"


@auth_bp.get("/login")
def login():
    if session.get("auth_ok"):
        return redirect(url_for("overview.dashboard"))
    next_url = _safe_next_url(request.args.get("next"))
    return render_template("login.html", error=None, next_url=next_url)


@auth_bp.post("/login")
def login_post():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    next_url = _safe_next_url(request.form.get("next"))

    ok, role, err = _backend_login(username, password)
    if ok:
        session["auth_ok"] = True
        session["auth_user"] = username
        session["auth_role"] = role or "user"
        if role == "admin":
            session["auth_pass"] = password
        return redirect(next_url or url_for("overview.dashboard"))

    return render_template(
        "login.html",
        error=err or "Login failed",
        next_url=next_url,
    )


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.get("/users")
def manage_users():
    if not _is_admin():
        return (
            render_template(
                "users.html",
                users=[],
                error="Admin access required.",
                message=None,
            ),
            403,
        )
    data, err = _backend_request("GET", "/auth/users")
    if err:
        return render_template(
            "users.html",
            users=[],
            error=f"Unable to fetch users: {err}",
            message=None,
        )
    users = data.get("users", []) if isinstance(data, dict) else []
    rows = [
        {
            "username": u.get("username"),
            "role": u.get("role"),
            "is_self": u.get("username") == session.get("auth_user"),
            "is_admin": u.get("role") == "admin",
        }
        for u in users
    ]
    return render_template(
        "users.html",
        users=rows,
        error=None,
        message=request.args.get("message"),
    )


@auth_bp.post("/users")
def manage_users_post():
    if not _is_admin():
        return (
            render_template(
                "users.html",
                users=[],
                error="Admin access required.",
                message=None,
            ),
            403,
        )

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if not username:
        return render_template(
            "users.html",
            users=[],
            error="Username is required.",
            message=None,
        )
    if not password:
        return render_template(
            "users.html",
            users=[],
            error="Password is required.",
            message=None,
        )
    if password != confirm:
        return render_template(
            "users.html",
            users=[],
            error="Passwords do not match.",
            message=None,
        )

    _, err = _backend_request(
        "POST",
        "/auth/users",
        payload={"username": username, "password": password, "role": "user"},
    )
    if err:
        return render_template(
            "users.html",
            users=[],
            error=f"Unable to add user: {err}",
            message=None,
        )
    return redirect(url_for("auth.manage_users", message=f"Saved user: {username}"))


@auth_bp.post("/users/delete")
def delete_user():
    if not _is_admin():
        return (
            render_template(
                "users.html",
                users=[],
                error="Admin access required.",
                message=None,
            ),
            403,
        )

    username = (request.form.get("username") or "").strip()
    if not username:
        return (
            render_template(
                "users.html",
                users=[],
                error="User not found.",
                message=None,
            ),
            404,
        )

    _, err = _backend_request("POST", "/auth/users/delete", payload={"username": username})
    if err:
        return render_template(
            "users.html",
            users=[],
            error=f"Unable to remove user: {err}",
            message=None,
        )
    return redirect(url_for("auth.manage_users", message=f"Removed user: {username}"))
