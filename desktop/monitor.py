"""Background thread connectivity monitor.

Polls a health URL on a fixed interval and fires on_online / on_offline
callbacks when the reachability state changes.
"""
import threading
import logging
from typing import Callable, Optional

import requests

log = logging.getLogger(__name__)


class ConnectivityMonitor:
    def __init__(
        self,
        url: str,
        interval_s: int,
        timeout_s: int,
        on_online: Optional[Callable] = None,
        on_offline: Optional[Callable] = None,
    ):
        self._url = url
        self._interval = interval_s
        self._timeout = timeout_s
        self._on_online = on_online
        self._on_offline = on_offline
        self._online: Optional[bool] = None  # None = unknown (pre-first-probe)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_online(self) -> bool:
        return self._online is True

    def probe_once(self) -> bool:
        """Single synchronous probe. Returns True if the URL is reachable."""
        try:
            r = requests.get(self._url, timeout=self._timeout, allow_redirects=True)
            return r.status_code < 500
        except Exception:
            return False

    def start(self):
        """Start the background polling thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="ConnMonitor")
        self._thread.start()

    def stop(self):
        """Signal the polling thread to exit."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._timeout + 1)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        # Probe immediately so we have a state before the first interval elapses
        self._update(self.probe_once())
        while not self._stop.wait(self._interval):
            self._update(self.probe_once())

    def _update(self, reachable: bool):
        if reachable == self._online:
            return  # no state change — suppress duplicate events
        self._online = reachable
        if reachable:
            log.info("ConnectivityMonitor: online (%s)", self._url)
            if self._on_online:
                self._on_online()
        else:
            log.warning("ConnectivityMonitor: offline (%s)", self._url)
            if self._on_offline:
                self._on_offline()
