"""System tray icon manager using pystray.

pystray.Icon.run() blocks, so the icon runs in a daemon thread.
The public API (set_status, stop) is thread-safe.
"""
import logging
import pathlib
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

_STATUS_LABELS = {
    "online":  "● Online",
    "stale":   "◐ Stale data",
    "offline": "○ Offline",
}


class TrayManager:
    def __init__(
        self,
        on_force_sync: Callable,
        on_quit: Callable,
        window=None,
    ):
        self._on_force_sync = on_force_sync
        self._on_quit = on_quit
        self._window = window
        self._status = "online"
        self._icon = None
        self._pystray = None

    def start(self):
        """Start the tray icon in a daemon thread. Non-fatal if pystray is unavailable."""
        try:
            import pystray
            from PIL import Image

            self._pystray = pystray
            icon_path = pathlib.Path(__file__).parent / "assets" / "tray-icon.png"
            if icon_path.exists():
                image = Image.open(icon_path)
            else:
                # Fallback: plain green square
                image = Image.new("RGB", (16, 16), color=(22, 163, 74))

            self._icon = pystray.Icon(
                "DublinCityDashboard",
                image,
                "Dublin City Dashboard",
                menu=self._build_menu(),
            )
            t = threading.Thread(target=self._icon.run, daemon=True, name="TrayIcon")
            t.start()
        except Exception as exc:
            log.warning("System tray unavailable: %s", exc)

    def set_status(self, status: str):
        """Update the tray tooltip and menu. status: 'online' | 'stale' | 'offline'"""
        self._status = status
        if self._icon and self._pystray:
            label = _STATUS_LABELS.get(status, status)
            self._icon.title = f"Dublin City Dashboard — {label}"
            try:
                self._icon.menu = self._build_menu()
                self._icon.update_menu()
            except Exception:
                pass

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_menu(self):
        pystray = self._pystray
        if pystray is None:
            return None

        status_label = _STATUS_LABELS.get(self._status, self._status)

        def show(icon, item):
            if self._window:
                try:
                    self._window.show()
                except Exception:
                    pass

        def force_sync(icon, item):
            threading.Thread(target=self._on_force_sync, daemon=True).start()

        def quit_app(icon, item):
            self._on_quit()

        return pystray.Menu(
            pystray.MenuItem("Dublin City Dashboard", None, enabled=False),
            pystray.MenuItem(status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Dashboard", show),
            pystray.MenuItem("Force Sync", force_sync),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_app),
        )
