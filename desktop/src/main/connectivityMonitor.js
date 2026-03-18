'use strict';

const { EventEmitter } = require('events');
const log = require('electron-log');

/**
 * Polls GET /health on the local backend every `pollIntervalMs` milliseconds
 * and emits 'online' / 'offline' events on state transitions.
 *
 * Events
 * ------
 * 'online'   – backend became reachable (was previously offline)
 * 'offline'  – backend became unreachable ({ cachedAt: number|null })
 */
class ConnectivityMonitor extends EventEmitter {
  /**
   * @param {string} healthUrl         Full URL to poll (e.g. 'http://127.0.0.1:5001/health').
   * @param {number} pollIntervalMs    How often to poll (ms).
   */
  constructor(healthUrl, pollIntervalMs) {
    super();
    this.healthUrl = healthUrl;
    this.pollIntervalMs = pollIntervalMs;
    this.isOnline = true;   // optimistic initial state
    this._timer = null;
    this._cachedAt = null;
  }

  // --------------------------------------------------------------------------
  // Public API
  // --------------------------------------------------------------------------

  start() {
    if (this._timer) return;
    this._timer = setInterval(() => this._poll(), this.pollIntervalMs);
    // Run immediately so we have an accurate status before the first interval
    this._poll();
  }

  stop() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  // --------------------------------------------------------------------------
  // Internal
  // --------------------------------------------------------------------------

  async _poll() {
    const url = this.healthUrl;
    let reachable = false;

    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
      reachable = resp.status === 0 || resp.status < 500;
    } catch (_) {
      reachable = false;
    }

    if (reachable && !this.isOnline) {
      this.isOnline = true;
      log.info('ConnectivityMonitor: online');
      this.emit('online');
    } else if (!reachable && this.isOnline) {
      this.isOnline = false;
      this._cachedAt = Date.now();
      log.warn('ConnectivityMonitor: offline');
      this.emit('offline', { cachedAt: this._cachedAt });
    }
    // No event emitted when status is unchanged
  }
}

module.exports = ConnectivityMonitor;
