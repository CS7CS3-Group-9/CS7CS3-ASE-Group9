"""Dublin City Dashboard — desktop entry point.

Startup sequence
----------------
1. Open SQLite cache.
2. Spawn local Flask backend (port 5001) for cache-warmup endpoint.
3. Start local caching proxy (port 8080) in a daemon thread.
4. Probe cloud connectivity; set _cloud_online threading.Event accordingly.
5. Start ConnectivityMonitor (polls /health every 30 s).
6. Start background-sync daemon thread (runs every 60 s when cloud online).
7. Create pystray tray icon.
8. Open PyWebView window pointed at http://127.0.0.1:8080/dashboard.
9. Block on webview.start() until the window is closed.
10. Cleanup: stop monitor, kill backend, stop tray.

Usage
-----
    python desktop/app.py
    CLOUD_URL=http://myhost python desktop/app.py
"""
import json
import logging
import os
import pathlib
import subprocess
import sys
import threading
import time

import requests
import webview

import desktop.config as cfg
from desktop.cache import Cache
from desktop.monitor import ConnectivityMonitor
from desktop.proxy import init_proxy, proxy_app, warm_tiles
from desktop.tray import TrayManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_cloud_online = threading.Event()
_window = None
_tray: TrayManager = None
_monitor: ConnectivityMonitor = None
_backend_proc: subprocess.Popen = None


# ---------------------------------------------------------------------------
# Backend subprocess
# ---------------------------------------------------------------------------

def _find_python() -> str:
    for cmd in ("python3", "python", "py"):
        try:
            out = subprocess.check_output(
                [cmd, "--version"], stderr=subprocess.STDOUT, timeout=3
            )
            if b"Python 3" in out:
                return cmd
        except Exception:
            pass
    raise RuntimeError("Python 3 interpreter not found on PATH")


def _start_backend() -> subprocess.Popen:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    python = _find_python()
    env = {
        **os.environ,
        "ENABLE_FIRESTORE": "false",
        "PORT": str(cfg.BACKEND_PORT),
        "FLASK_APP": "backend.app:create_app",
    }
    proc = subprocess.Popen(
        [
            python, "-m", "flask", "--app", "backend.app:create_app",
            "run", "--port", str(cfg.BACKEND_PORT),
            "--no-debugger", "--no-reload",
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{cfg.BACKEND_PORT}/", timeout=2)
            if r.status_code < 500:
                log.info("Backend ready on port %d", cfg.BACKEND_PORT)
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    log.warning("Backend did not become ready within 30 s; cache warmup unavailable")
    return proc


# ---------------------------------------------------------------------------
# Proxy thread
# ---------------------------------------------------------------------------

def _start_proxy(cache: Cache):
    init_proxy(cache, _cloud_online)
    t = threading.Thread(
        target=lambda: proxy_app.run(
            host="127.0.0.1",
            port=cfg.PROXY_PORT,
            threaded=True,
            use_reloader=False,
        ),
        daemon=True,
        name="ProxyThread",
    )
    t.start()
    # Wait until the proxy is accepting connections
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            requests.get(
                f"http://127.0.0.1:{cfg.PROXY_PORT}/desktop/status", timeout=1
            )
            log.info("Proxy ready on port %d", cfg.PROXY_PORT)
            return
        except Exception:
            time.sleep(0.2)
    log.warning("Proxy may not be ready yet — proceeding anyway")


# ---------------------------------------------------------------------------
# Background sync
# ---------------------------------------------------------------------------

def _build_analytics(snapshot: dict) -> dict:
    """Port of main.js buildAnalyticsFromSnapshot."""
    aq = snapshot.get("airquality") or {}
    pollutants = aq.get("pollutants") or {}
    aq_keys   = ["pm2_5", "pm10", "nitrogen_dioxide", "carbon_monoxide", "ozone", "sulphur_dioxide"]
    aq_labels = ["PM2.5", "PM10", "NO\u2082", "CO", "O\u2083", "SO\u2082"]
    aq_values = [round((pollutants.get(k) or 0) * 100) / 100 for k in aq_keys]

    bikes = snapshot.get("bikes") or {}
    by_cat = ((snapshot.get("traffic") or {}).get("incidents_by_category")) or {}
    traffic_labels = list(by_cat.keys()) if by_cat else ["No Incidents"]
    traffic_values = list(by_cat.values()) if by_cat else [0]

    return {
        "air_quality_chart": {"labels": aq_labels, "values": aq_values},
        "bike_chart": {
            "labels": ["Available Bikes", "Empty Docks", "Stations Reporting"],
            "values": [
                bikes.get("available_bikes", 0),
                bikes.get("available_docks", 0),
                bikes.get("stations_reporting", 0),
            ],
        },
        "traffic_chart": {"labels": traffic_labels, "values": traffic_values},
        "timestamp": snapshot.get("timestamp"),
    }


def _run_background_sync(cache: Cache):
    if not _cloud_online.is_set():
        return
    try:
        # Try local backend first (dev mode); fall back to cloud endpoint.
        warmup_url = f"http://127.0.0.1:{cfg.BACKEND_PORT}/desktop/cache-warmup"
        try:
            r = requests.get(warmup_url, timeout=5)
            if not r.ok:
                raise ValueError("local backend not ready")
        except Exception:
            warmup_url = f"{cfg.CLOUD_URL.rstrip('/')}/desktop/cache-warmup"
            r = requests.get(warmup_url, timeout=30)
        if not r.ok:
            return
        data = r.json()

        if data.get("snapshot"):
            cache.set_text(
                cfg.CACHE_KEYS["snapshot"],
                json.dumps(data["snapshot"]),
                "application/json",
                cfg.TTL_API,
            )
            analytics = _build_analytics(data["snapshot"])
            cache.set_text(
                cfg.CACHE_KEYS["analytics"],
                json.dumps(analytics),
                "application/json",
                cfg.TTL_ANALYTICS,
            )
        if data.get("bike_stations"):
            cache.set_text(
                cfg.CACHE_KEYS["bikeStations"],
                json.dumps(data["bike_stations"]),
                "application/json",
                cfg.TTL_API,
            )
        if data.get("bus_stops"):
            cache.set_text(
                cfg.CACHE_KEYS["busStops"],
                json.dumps(data["bus_stops"]),
                "application/json",
                cfg.TTL_BUS_STOPS,
            )

        log.info("Background sync complete")

        # Proactively seed Dublin city-centre map tiles
        threading.Thread(target=warm_tiles, daemon=True, name="TileWarm").start()

    except Exception as exc:
        log.warning("Background sync failed: %s", exc)


def _sync_loop(cache: Cache):
    while True:
        time.sleep(cfg.SYNC_INTERVAL_S)
        _run_background_sync(cache)


# ---------------------------------------------------------------------------
# Quit handler
# ---------------------------------------------------------------------------

def _quit():
    global _monitor, _backend_proc, _tray, _window
    log.info("App shutting down")
    if _monitor:
        _monitor.stop()
    if _backend_proc:
        _backend_proc.terminate()
    if _tray:
        _tray.stop()
    if _window:
        try:
            _window.destroy()
        except Exception:
            pass
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _cloud_online, _window, _tray, _monitor, _backend_proc

    # 1. Cache
    cache = Cache(cfg.get_db_path())
    log.info("Cache database: %s", cfg.get_db_path())

    # 2. Local backend
    try:
        _backend_proc = _start_backend()
    except Exception as exc:
        log.warning("Could not start local backend: %s", exc)

    # 3. Proxy
    _start_proxy(cache)

    # 4. Initial connectivity probe
    monitor_url = f"{cfg.CLOUD_URL.rstrip('/')}/health"
    probe = ConnectivityMonitor(
        url=monitor_url,
        interval_s=cfg.POLL_INTERVAL_S,
        timeout_s=cfg.PROBE_TIMEOUT_S,
    )
    if probe.probe_once():
        _cloud_online.set()
        log.info("Initial state: cloud online")
    else:
        _cloud_online.clear()
        log.info("Initial state: cloud offline")

    # 5. Connectivity monitor (background)
    def on_online():
        _cloud_online.set()
        if _tray:
            _tray.set_status("online")
        threading.Thread(
            target=_run_background_sync, args=(cache,), daemon=True
        ).start()

    def on_offline():
        _cloud_online.clear()
        if _tray:
            _tray.set_status("offline")

    _monitor = ConnectivityMonitor(
        url=monitor_url,
        interval_s=cfg.POLL_INTERVAL_S,
        timeout_s=cfg.PROBE_TIMEOUT_S,
        on_online=on_online,
        on_offline=on_offline,
    )
    _monitor.start()

    # 6. Background sync loop
    threading.Thread(
        target=_sync_loop, args=(cache,), daemon=True, name="SyncLoop"
    ).start()
    if _cloud_online.is_set():
        threading.Thread(
            target=_run_background_sync, args=(cache,), daemon=True
        ).start()

    # 7. Tray icon
    _tray = TrayManager(
        on_force_sync=lambda: threading.Thread(
            target=_run_background_sync, args=(cache,), daemon=True
        ).start(),
        on_quit=_quit,
    )
    _tray.start()
    if not _cloud_online.is_set():
        _tray.set_status("offline")

    # 8–9. PyWebView window
    _window = webview.create_window(
        title="Dublin City Dashboard",
        url=f"http://127.0.0.1:{cfg.PROXY_PORT}/dashboard",
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    _tray._window = _window

    webview.start()

    # 10. Cleanup after window closed
    _quit()


if __name__ == "__main__":
    main()
