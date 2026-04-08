"""Centralised configuration for the Dublin City Dashboard desktop app."""
import os
import platform
import pathlib

CLOUD_URL    = os.environ.get("CLOUD_URL", "http://ase-citydash-board.duckdns.org")
PROXY_PORT   = int(os.environ.get("PROXY_PORT", "8080"))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "5001"))

# Connectivity monitoring
POLL_INTERVAL_S = 30
SYNC_INTERVAL_S = 60
PROBE_TIMEOUT_S = 5

# Cache TTLs (seconds)
TTL_HTML      = 60
TTL_API       = 120
TTL_STATIC    = 86_400        # 24 h — CSS, JS, images
TTL_BUS_STOPS = 86_400        # 24 h — rarely change
TTL_ANALYTICS = 300           # 5 min
TTL_TILES     = 2_592_000     # 30 days

# CDN URLs rewritten to local proxy routes so they work offline
CDN_REWRITE = {
    "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css":
        f"http://127.0.0.1:{PROXY_PORT}/static/vendor/MarkerCluster.css",
    "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css":
        f"http://127.0.0.1:{PROXY_PORT}/static/vendor/MarkerCluster.Default.css",
}

# Exact tile URL string in frontend/static/js/map.js line 12
TILE_ORIGIN = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_PROXY  = f"http://127.0.0.1:{PROXY_PORT}/tiles/{{z}}/{{x}}/{{y}}.png"

# SQLite cache keys (matching existing backend/desktop.py warmup response)
CACHE_KEYS = {
    "snapshot":     "snapshot:dublin:5",
    "bikeStations": "bikes:stations",
    "busStops":     "buses:stops",
    "analytics":    "analytics:data",
}

# Dublin city centre tile coordinates to pre-warm (z, x_range, y_range)
TILE_WARM_REGIONS = [
    (12, range(2043, 2047), range(1356, 1361)),
    (13, range(4086, 4094), range(2712, 2722)),
]


def get_db_path() -> pathlib.Path:
    if platform.system() == "Windows":
        base = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home()))
    elif platform.system() == "Darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    else:
        base = pathlib.Path(
            os.environ.get("XDG_DATA_HOME", str(pathlib.Path.home() / ".local" / "share"))
        )
    p = base / "DublinCityDashboard"
    p.mkdir(parents=True, exist_ok=True)
    return p / "cache.db"
