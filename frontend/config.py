import os


class Config:
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:5000")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "60"))
