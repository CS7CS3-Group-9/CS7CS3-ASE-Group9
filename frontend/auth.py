import hmac
import json
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    return None


def _resolve_users_file() -> Path | None:
    file_path = current_app.config.get("DASHBOARD_USERS_FILE") or ""
    file_path = file_path.strip()
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / path
    return path


def _load_users_from_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items()}


def _save_users_to_file(path: Path, users: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users, indent=2, sort_keys=True), encoding="utf-8")


def _normalise_user_record(raw: object) -> dict | None:
    if isinstance(raw, str):
        return {"password": raw, "role": "admin"}
    if isinstance(raw, dict):
        role = str(raw.get("role") or "admin")
        if raw.get("password_hash"):
            return {"password_hash": str(raw["password_hash"]), "role": role}
        if raw.get("password"):
            return {"password": str(raw["password"]), "role": role}
    return None


def _resolve_auth_users() -> tuple[dict, Path | None]:
    path = _resolve_users_file()
    if path is not None:
        return _load_users_from_file(path), path
    return current_app.config.get("DASHBOARD_USERS") or {}, None


def _is_admin() -> bool:
    return session.get("auth_ok") and session.get("auth_role", "admin") == "admin"


def _user_role(raw: object) -> str:
    normalised = _normalise_user_record(raw)
    if normalised is None:
        return "user"
    return str(normalised.get("role") or "admin")


def _build_user_rows(users: dict) -> list[dict]:
    current_user = session.get("auth_user")
    rows = []
    for name, record in users.items():
        role = _user_role(record)
        rows.append(
            {
                "username": name,
                "role": role,
                "is_self": name == current_user,
                "is_admin": role == "admin",
            }
        )
    rows.sort(key=lambda x: (x["role"] != "admin", x["username"]))
    return rows


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

    expected_user = current_app.config.get("DASHBOARD_USER", "")
    expected_pass = current_app.config.get("DASHBOARD_PASS", "")
    expected_users, users_path = _resolve_auth_users()

    mapped = _normalise_user_record(expected_users.get(username))
    if mapped is not None:
        if mapped.get("password_hash") and check_password_hash(mapped["password_hash"], password):
            session["auth_ok"] = True
            session["auth_user"] = username
            session["auth_role"] = mapped.get("role", "admin")
            return redirect(next_url or url_for("overview.dashboard"))
        if mapped.get("password") and hmac.compare_digest(password, mapped["password"]):
            if users_path is not None:
                users = _load_users_from_file(users_path)
                users[username] = {
                    "password_hash": generate_password_hash(password),
                    "role": mapped.get("role", "admin"),
                }
                _save_users_to_file(users_path, users)
            session["auth_ok"] = True
            session["auth_user"] = username
            session["auth_role"] = mapped.get("role", "admin")
            return redirect(next_url or url_for("overview.dashboard"))

    if username == expected_user and hmac.compare_digest(password, expected_pass):
        session["auth_ok"] = True
        session["auth_user"] = username
        session["auth_role"] = "admin"
        return redirect(next_url or url_for("overview.dashboard"))

    return render_template(
        "login.html",
        error="Invalid credentials. Please try again.",
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
    path = _resolve_users_file()
    if path is None:
        return render_template(
            "users.html",
            users=[],
            error="DASHBOARD_USERS_FILE is not set. Configure it to manage users.",
            message=None,
        )
    users = _load_users_from_file(path)
    return render_template(
        "users.html",
        users=_build_user_rows(users),
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
    path = _resolve_users_file()
    if path is None:
        return render_template(
            "users.html",
            users=[],
            error="DASHBOARD_USERS_FILE is not set. Configure it to manage users.",
            message=None,
        )

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    users = _load_users_from_file(path)

    if not username:
        return render_template(
            "users.html",
            users=_build_user_rows(users),
            error="Username is required.",
            message=None,
        )
    if not password:
        return render_template(
            "users.html",
            users=_build_user_rows(users),
            error="Password is required.",
            message=None,
        )
    if password != confirm:
        return render_template(
            "users.html",
            users=_build_user_rows(users),
            error="Passwords do not match.",
            message=None,
        )

    users[username] = {
        "password_hash": generate_password_hash(password),
        "role": "user",
    }
    _save_users_to_file(path, users)
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

    path = _resolve_users_file()
    if path is None:
        return render_template(
            "users.html",
            users=[],
            error="DASHBOARD_USERS_FILE is not set. Configure it to manage users.",
            message=None,
        )

    username = (request.form.get("username") or "").strip()
    users = _load_users_from_file(path)
    if not username or username not in users:
        return (
            render_template(
                "users.html",
                users=_build_user_rows(users),
                error="User not found.",
                message=None,
            ),
            404,
        )

    current_user = session.get("auth_user")
    if username == current_user:
        return redirect(url_for("auth.manage_users", message="Cannot remove your own account."))

    target_role = _user_role(users.get(username))
    if target_role == "admin":
        return redirect(url_for("auth.manage_users", message="Admin accounts cannot be removed."))

    users.pop(username, None)
    _save_users_to_file(path, users)
    return redirect(url_for("auth.manage_users", message=f"Removed user: {username}"))
