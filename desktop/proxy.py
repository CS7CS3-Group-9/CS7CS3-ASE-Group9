"""Local caching reverse-proxy Flask app (port 8080).

The PyWebView window always loads from http://127.0.0.1:8080.
When the cloud is online:  requests are forwarded to the cloud, responses cached.
When the cloud is offline: cached responses are served from SQLite.

Key routes
----------
GET  /desktop/status          → {"offline": bool}  polled by the injected banner JS
GET  /tiles/<z>/<x>/<y>.png  → OSM tile (cached as BLOB)
GET  /static/vendor/<file>    → bundled MarkerCluster CSS
*    /<path>                  → catch-all proxy / cache
"""
import logging
import pathlib
import threading
from typing import Optional

import requests as req_lib
from flask import Flask, Response, jsonify, request, send_from_directory

import desktop.config as cfg
from desktop.cache import Cache

log = logging.getLogger(__name__)

proxy_app = Flask(__name__, static_folder=None)

# Shared with app.py — set = cloud online, cleared = cloud offline
_cloud_online: threading.Event = threading.Event()
_cache: Optional[Cache] = None

_assets_dir = pathlib.Path(__file__).parent / "assets"

# ---------------------------------------------------------------------------
# Offline banner + status polling script injected into every HTML response
# ---------------------------------------------------------------------------
_BANNER = f"""
<div id="desktop-offline-banner"
     style="display:none;position:fixed;bottom:0;left:0;right:0;z-index:99999;
            background:#b45309;color:#fff;padding:8px 16px;font-size:13px;
            font-family:system-ui,sans-serif;align-items:center;
            justify-content:space-between;gap:12px;
            box-shadow:0 -2px 4px rgba(0,0,0,.3)">
  <span>&#9888; Offline &mdash; showing cached data</span>
  <button onclick="location.reload()"
          style="background:rgba(255,255,255,.2);color:#fff;
                 border:1px solid rgba(255,255,255,.5);border-radius:4px;
                 padding:3px 10px;cursor:pointer;font-size:12px">Retry</button>
</div>
<script>
(function poll(){{
  fetch('http://127.0.0.1:{cfg.PROXY_PORT}/desktop/status')
    .then(function(r){{return r.json();}})
    .then(function(s){{
      var b=document.getElementById('desktop-offline-banner');
      if(b) b.style.display=s.offline?'flex':'none';
    }}).catch(function(){{}});
  setTimeout(poll, 5000);
}})();
</script>
"""


# ---------------------------------------------------------------------------
# HTML rewriting
# ---------------------------------------------------------------------------

def _rewrite_html(html: str) -> str:
    """Apply all rewrites to an HTML response string before caching/serving."""
    # 1. CDN → local proxy routes
    for cdn_url, local_url in cfg.CDN_REWRITE.items():
        html = html.replace(cdn_url, local_url)

    # 2. Tile URL → local proxy tile route
    #    Covers both the {s}-subdomain form and any a/b/c.tile.openstreetmap.org variants
    html = html.replace(cfg.TILE_ORIGIN, cfg.TILE_PROXY)
    for sub in ("a", "b", "c"):
        html = html.replace(
            f"https://{sub}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
            cfg.TILE_PROXY,
        )

    # 3. Inject offline banner before </body>
    html = html.replace("</body>", _BANNER + "</body>", 1)
    return html


def _ttl_for(content_type: str, path: str) -> int:
    """Return appropriate cache TTL in seconds for a given response."""
    if "text/html" in content_type:
        return cfg.TTL_HTML
    if "application/json" in content_type:
        if path in ("/buses/stops",):
            return cfg.TTL_BUS_STOPS
        if "analytics" in path:
            return cfg.TTL_ANALYTICS
        return cfg.TTL_API
    # CSS, JS, fonts, images
    return cfg.TTL_STATIC


def _cache_key(path: str, query: str) -> str:
    return f"{path}?{query}" if query else path


def _offline_miss_page() -> str:
    return _rewrite_html(
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<title>Dublin City Dashboard</title></head>"
        "<body style='margin:0;background:#0f172a;color:#e2e8f0;"
        "font-family:system-ui,sans-serif;display:flex;align-items:center;"
        "justify-content:center;height:100vh'>"
        "<div style='text-align:center;max-width:360px'>"
        "<div style='font-size:48px'>&#127961;</div>"
        "<h1 style='font-size:22px;margin:16px 0 8px'>Dublin City Dashboard</h1>"
        "<p style='color:#94a3b8;line-height:1.6'>No cached version of this page is available. "
        "Connect to the internet to load the dashboard for the first time.</p>"
        "</div></body></html>"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@proxy_app.route("/desktop/status")
def status():
    return jsonify({"offline": not _cloud_online.is_set()})


@proxy_app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile_proxy(z: int, x: int, y: int):
    cached = _cache.get_tile(z, x, y)
    if cached is not None:
        return Response(
            cached,
            mimetype="image/png",
            headers={"Cache-Control": f"public, max-age={cfg.TTL_TILES}"},
        )
    # Fetch from OSM even when offline (tiles may still be reachable independently)
    try:
        r = req_lib.get(
            f"https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            timeout=8,
            headers={"User-Agent": "DublinCityDashboard/2.0"},
        )
        if r.status_code == 200:
            _cache.set_tile(z, x, y, r.content)
            return Response(
                r.content,
                mimetype="image/png",
                headers={"Cache-Control": f"public, max-age={cfg.TTL_TILES}"},
            )
    except Exception as exc:
        log.debug("Tile fetch failed z=%d x=%d y=%d: %s", z, x, y, exc)
    # 204 No Content — Leaflet handles this gracefully (blank tile slot, no error)
    return Response(status=204)


@proxy_app.route("/static/vendor/<path:filename>")
def vendor_assets(filename: str):
    local_path = _assets_dir / "vendor" / filename
    if local_path.is_file():
        return send_from_directory(_assets_dir / "vendor", filename)
    # Not a locally bundled asset — proxy to cloud like catch_all
    return catch_all(f"static/vendor/{filename}")


@proxy_app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@proxy_app.route("/<path:path>",            methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def catch_all(path: str):
    req_path  = "/" + path
    query     = request.query_string.decode()
    cache_key = _cache_key(req_path, query)
    cloud_url = cfg.CLOUD_URL.rstrip("/") + req_path + ("?" + query if query else "")

    if _cloud_online.is_set():
        try:
            upstream = req_lib.request(
                method=request.method,
                url=cloud_url,
                headers={
                    k: v for k, v in request.headers
                    if k.lower() not in ("host", "accept-encoding")
                },
                data=request.get_data(),
                timeout=15,
                allow_redirects=True,
            )
            ct   = upstream.headers.get("Content-Type", "")
            body = upstream.content
            log.debug("Upstream %s %s → %d  ct=%r  len=%d", request.method, cloud_url, upstream.status_code, ct, len(body))

            if upstream.status_code < 400 and (
                "text/" in ct or "application/json" in ct or "javascript" in ct
            ):
                text = body.decode("utf-8", errors="replace")
                if "text/html" in ct:
                    text = _rewrite_html(text)
                _cache.set_text(cache_key, text, ct, _ttl_for(ct, req_path))
                return Response(text, status=upstream.status_code, content_type=ct)

            # Binary or non-cacheable (e.g. images served by cloud directly)
            return Response(
                body,
                status=upstream.status_code,
                content_type=ct,
                headers={
                    k: v for k, v in upstream.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding", "connection")
                },
            )
        except Exception as exc:
            log.warning("Upstream request failed for %s: %s — falling back to cache", cache_key, exc)

    # ------------------------------------------------------------------
    # Offline path: serve from SQLite cache
    # ------------------------------------------------------------------
    entry = _cache.get_text(cache_key)
    if entry is not None:
        body_text, ct, _, is_stale = entry
        resp = Response(body_text, status=200, content_type=ct)
        resp.headers["X-Cache"] = "HIT-STALE" if is_stale else "HIT"
        return resp

    log.info("Cache miss (offline): %s", cache_key)
    return Response(_offline_miss_page(), status=503, content_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Tile pre-warming helper (called by background sync in app.py)
# ---------------------------------------------------------------------------

def warm_tiles():
    """Proactively fetch and cache Dublin city-centre tiles that haven't been seen yet."""
    for z, xs, ys in cfg.TILE_WARM_REGIONS:
        for x in xs:
            for y in ys:
                if _cache.get_tile(z, x, y) is None:
                    try:
                        r = req_lib.get(
                            f"https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                            timeout=5,
                            headers={"User-Agent": "DublinCityDashboard/2.0"},
                        )
                        if r.status_code == 200:
                            _cache.set_tile(z, x, y, r.content)
                    except Exception:
                        pass


# ---------------------------------------------------------------------------
# Initialisation (called by app.py before starting the Flask thread)
# ---------------------------------------------------------------------------

def init_proxy(cache: Cache, cloud_online_event: threading.Event):
    global _cache, _cloud_online
    _cache        = cache
    _cloud_online = cloud_online_event
