import json
import os
from pathlib import Path
from typing import Tuple, Optional

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_users_file() -> Path:
    raw = os.getenv("BACKEND_USERS_FILE", "backend/users.json").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _load_users(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items()}


def _save_users(path: Path, users: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users, indent=2, sort_keys=True), encoding="utf-8")


def _normalise_user_record(raw: object) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    password_hash = raw.get("password_hash")
    if not password_hash:
        return None
    role = str(raw.get("role") or "admin")
    return {"password_hash": str(password_hash), "role": role}


def _verify_credentials(username: str, password: str) -> Tuple[bool, Optional[str]]:
    path = _resolve_users_file()
    users = _load_users(path)

    record = _normalise_user_record(users.get(username))
    if record is None:
        return False, None
    if check_password_hash(record["password_hash"], password):
        return True, record.get("role", "admin")
    return False, None


def _basic_auth() -> Tuple[Optional[str], Optional[str]]:
    auth = request.authorization
    if not auth:
        return None, None
    return auth.username, auth.password


def _require_admin() -> Tuple[bool, Optional[tuple]]:
    username, password = _basic_auth()
    if not username or not password:
        return False, (jsonify({"error": "Missing credentials"}), 401)
    ok, role = _verify_credentials(username, password)
    if not ok:
        return False, (jsonify({"error": "Invalid credentials"}), 401)
    if role != "admin":
        return False, (jsonify({"error": "Admin access required"}), 403)
    return True, (username, role)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or request.form or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    ok, role = _verify_credentials(username, password)
    if not ok:
        return jsonify({"error": "invalid credentials"}), 401

    return jsonify({"ok": True, "role": role})


@auth_bp.get("/users")
def list_users():
    ok, result = _require_admin()
    if not ok:
        return result
    path = _resolve_users_file()
    users = _load_users(path)
    response = []
    for name, record in users.items():
        normalised = _normalise_user_record(record)
        role = normalised.get("role") if normalised else "invalid"
        response.append({"username": name, "role": role})
    response.sort(key=lambda x: (x["role"] != "admin", x["username"]))
    return jsonify({"users": response})


@auth_bp.post("/users")
def add_user():
    ok, result = _require_admin()
    if not ok:
        return result
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    role = str(payload.get("role") or "user")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    path = _resolve_users_file()
    users = _load_users(path)
    users[username] = {
        "password_hash": generate_password_hash(password),
        "role": role,
    }
    _save_users(path, users)
    return jsonify({"ok": True, "username": username, "role": role}), 201


@auth_bp.post("/users/delete")
def delete_user():
    ok, result = _require_admin()
    if not ok:
        return result
    admin_user = result[0]
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    path = _resolve_users_file()
    users = _load_users(path)
    if username not in users:
        return jsonify({"error": "user not found"}), 404

    if username == admin_user:
        return jsonify({"error": "cannot remove your own account"}), 400

    role = (_normalise_user_record(users.get(username)) or {}).get("role", "admin")
    if role == "admin":
        return jsonify({"error": "admin accounts cannot be removed"}), 400

    users.pop(username, None)
    _save_users(path, users)
    return jsonify({"ok": True, "removed": username})
