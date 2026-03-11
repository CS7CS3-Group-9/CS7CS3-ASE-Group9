'use strict';

const { contextBridge, ipcRenderer } = require('electron');

/**
 * Exposes a safe, narrowly-scoped API to the renderer process via
 * contextBridge. Node.js APIs are never exposed directly.
 *
 * Usage in renderer / injected overlay:
 *   window.electronAPI.getCachedData('snapshot:dublin:5')
 *   window.electronAPI.onConnectivityChange(({ online, cachedAt }) => …)
 */
contextBridge.exposeInMainWorld('electronAPI', {
  // ---- Cache ----------------------------------------------------------------

  /** Retrieve a cache entry by key. Returns the entry object or null. */
  getCachedData: (key) =>
    ipcRenderer.invoke('cache:get', key),

  /** Store data in the cache with a TTL. */
  setCachedData: (key, data, ttlSeconds) =>
    ipcRenderer.invoke('cache:set', key, data, ttlSeconds),

  /** Clear one cache entry (key) or all entries (no argument). */
  clearCache: (key) =>
    ipcRenderer.invoke('cache:clear', key),

  /** Get recent route history (newest first, max 10). */
  getRouteHistory: () =>
    ipcRenderer.invoke('cache:getRouteHistory'),

  /** Save a calculated route to the local history. */
  saveRoute: (stops, result) =>
    ipcRenderer.invoke('cache:saveRoute', stops, result),

  // ---- Connectivity ---------------------------------------------------------

  /**
   * Register a callback for connectivity change events.
   * @param {function({ online: boolean, cachedAt?: number }): void} callback
   * @returns {function} Unsubscribe function — call it to remove the listener.
   */
  onConnectivityChange: (callback) => {
    const handler = (_event, status) => callback(status);
    ipcRenderer.on('connectivity:change', handler);
    return () => ipcRenderer.removeListener('connectivity:change', handler);
  },
});
