import os
import json
from pathlib import Path


def _default_users_file() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    candidate = repo_root / "frontend" / "users.json"
    if candidate.exists():
        return str(candidate)
    return ""


def _load_users():
    raw = os.getenv("DASHBOARD_USERS_JSON", "").strip()
    if not raw:
        raw = None
    try:
        if raw:
            data = json.loads(raw)
        else:
            data = None
    except json.JSONDecodeError:
        data = None
    if data is None:
        file_path = os.getenv("DASHBOARD_USERS_FILE", "").strip() or _default_users_file()
        if file_path:
            path = Path(file_path)
            if not path.is_absolute():
                repo_root = Path(__file__).resolve().parents[1]
                path = repo_root / path
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = None
    if data is None:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items()}


class Config:
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:5000")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "60"))
    DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
    DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "admin")
    DASHBOARD_USERS = _load_users()
    DASHBOARD_USERS_FILE = os.getenv("DASHBOARD_USERS_FILE", _default_users_file())
    # Shared secret used by the desktop app proxy to bypass browser auth.
    # Set DESKTOP_TOKEN env var on the cloud deployment to a strong secret.
    DESKTOP_TOKEN = os.getenv("DESKTOP_TOKEN", "dublin-dashboard-desktop-v1")
