'use strict';

/**
 * Centralised configuration for the Dublin City Dashboard desktop app.
 * All port numbers, TTLs, and tuneable constants live here.
 */
module.exports = {
  // Cloud frontend URL — when reachable this is loaded directly (no local Flask startup).
  // Set via CLOUD_URL env var or hardcode below.
  cloudUrl: process.env.CLOUD_URL || 'http://ase-citydash-board.duckdns.org',

  // Reliable external endpoint used to distinguish "cloud down" from "no internet".
  // Cloudflare DNS-over-HTTPS — no API key, no CORS issues in Electron main process.
  internetProbeUrl: 'https://1.1.1.1',

  // Ports used by the embedded Flask processes (local / offline fallback)
  backendPort: 5001,
  frontendPort: 5002,

  // How often the connectivity monitor polls /health (ms)
  connectivityPollIntervalMs: 30_000,

  // How often background sync refreshes the SQLite cache (ms)
  backgroundSyncIntervalMs: 60_000,

  // Timeout waiting for a Flask process to become ready on startup (ms)
  processReadyTimeoutMs: 30_000,

  // SQLite cache TTLs (seconds)
  cacheTtl: {
    snapshot: 120,
    bikeStations: 120,
    busStops: 86_400,   // bus stops rarely change
    analytics: 300,
    route: 3_600,
  },

  // Max number of routes stored in route_history table
  maxRouteHistory: 10,

  // SQLite database filename (stored in Electron userData directory)
  dbFileName: 'dublin-dashboard-cache.db',

  // Cache keys used by background sync and the overlay
  cacheKeys: {
    snapshot: 'snapshot:dublin:5',
    bikeStations: 'bikes:stations',
    busStops: 'buses:stops',
    analytics: 'analytics:data',
  },
};
