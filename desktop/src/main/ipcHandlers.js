'use strict';

/**
 * Registers all ipcMain handlers that bridge the renderer (via preload.js)
 * to the main-process services (CacheLayer, ConnectivityMonitor).
 *
 * @param {Electron.IpcMain} ipcMain
 * @param {CacheLayer} cacheLayer
 */
function registerIpcHandlers(ipcMain, cacheLayer) {
  // Retrieve a cache entry by key.
  // Returns { data_json, fetched_at, ttl_seconds, age_seconds, is_stale } or null.
  ipcMain.handle('cache:get', (_event, key) => {
    return cacheLayer.get(key);
  });

  // Store a cache entry.
  ipcMain.handle('cache:set', (_event, key, data, ttlSeconds) => {
    cacheLayer.set(key, data, ttlSeconds);
  });

  // Clear one entry (key provided) or all entries (no key).
  ipcMain.handle('cache:clear', (_event, key) => {
    cacheLayer.clear(key);
  });

  // Retrieve recent route history (newest first, max 10).
  ipcMain.handle('cache:getRouteHistory', () => {
    return cacheLayer.getRouteHistory();
  });

  // Persist a calculated route.
  ipcMain.handle('cache:saveRoute', (_event, stops, result) => {
    cacheLayer.saveRoute(stops, result);
  });
}

module.exports = { registerIpcHandlers };
