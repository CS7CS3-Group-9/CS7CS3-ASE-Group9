'use strict';

const path = require('path');

/**
 * SQLite-backed local cache for offline dashboard data.
 *
 * Uses better-sqlite3 (synchronous API) — all operations are safe to call
 * from the Electron main process without async overhead.
 *
 * Schema
 * ------
 * cache_entries  – key/value store for API response snapshots
 * route_history  – last N calculated routes for offline replay
 */
class CacheLayer {
  /**
   * @param {string} dbPath  Absolute path to the SQLite database file.
   */
  constructor(dbPath) {
    // Lazily require so Jest can mock it in unit tests
    const Database = require('better-sqlite3');
    this._db = new Database(dbPath);
    this._init();
  }

  // --------------------------------------------------------------------------
  // Schema setup
  // --------------------------------------------------------------------------
  _init() {
    // WAL mode allows concurrent reads during writes
    this._db.pragma('journal_mode = WAL');

    this._db.exec(`
      CREATE TABLE IF NOT EXISTS cache_entries (
        key         TEXT PRIMARY KEY,
        data_json   TEXT NOT NULL,
        fetched_at  INTEGER NOT NULL,
        ttl_seconds INTEGER NOT NULL DEFAULT 7200
      );

      CREATE TABLE IF NOT EXISTS route_history (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        stops_json     TEXT NOT NULL,
        result_json    TEXT NOT NULL,
        calculated_at  INTEGER NOT NULL
      );
    `);

    this._stmtGet    = this._db.prepare('SELECT * FROM cache_entries WHERE key = ?');
    this._stmtUpsert = this._db.prepare(`
      INSERT INTO cache_entries (key, data_json, fetched_at, ttl_seconds)
      VALUES (@key, @data_json, @fetched_at, @ttl_seconds)
      ON CONFLICT(key) DO UPDATE SET
        data_json   = excluded.data_json,
        fetched_at  = excluded.fetched_at,
        ttl_seconds = excluded.ttl_seconds
    `);
    this._stmtDelete = this._db.prepare('DELETE FROM cache_entries WHERE key = ?');
    this._stmtClear  = this._db.prepare('DELETE FROM cache_entries');

    this._stmtInsertRoute  = this._db.prepare(`
      INSERT INTO route_history (stops_json, result_json, calculated_at)
      VALUES (@stops_json, @result_json, @calculated_at)
    `);
    this._stmtGetRoutes    = this._db.prepare(
      'SELECT * FROM route_history ORDER BY calculated_at DESC LIMIT ?'
    );
    this._stmtCountRoutes  = this._db.prepare('SELECT COUNT(*) AS cnt FROM route_history');
    this._stmtDeleteOldest = this._db.prepare(`
      DELETE FROM route_history WHERE id = (
        SELECT id FROM route_history ORDER BY calculated_at ASC LIMIT 1
      )
    `);
  }

  // --------------------------------------------------------------------------
  // cache_entries API
  // --------------------------------------------------------------------------

  /**
   * Retrieve a cache entry.
   * @param {string} key
   * @returns {{ data_json: string, fetched_at: number, ttl_seconds: number,
   *             age_seconds: number, is_stale: boolean } | null}
   */
  get(key) {
    const row = this._stmtGet.get(key);
    if (!row) return null;
    const ageSeconds = Math.floor((Date.now() - row.fetched_at) / 1000);
    return {
      data_json:   row.data_json,
      fetched_at:  row.fetched_at,
      ttl_seconds: row.ttl_seconds,
      age_seconds: ageSeconds,
      is_stale:    ageSeconds > row.ttl_seconds,
    };
  }

  /**
   * Store or update a cache entry.
   * @param {string} key
   * @param {object|array} data  Will be JSON-serialised.
   * @param {number} ttlSeconds  Time-to-live in seconds.
   */
  set(key, data, ttlSeconds) {
    this._stmtUpsert.run({
      key,
      data_json:   JSON.stringify(data),
      fetched_at:  Date.now(),
      ttl_seconds: ttlSeconds,
    });
  }

  /**
   * Returns true if the entry exists and its age exceeds its TTL.
   * @param {string} key
   */
  isStale(key) {
    const entry = this.get(key);
    if (!entry) return false;
    return entry.is_stale;
  }

  /**
   * Delete one cache entry (or all if key is omitted).
   * @param {string} [key]
   */
  clear(key) {
    if (key !== undefined) {
      this._stmtDelete.run(key);
    } else {
      this._stmtClear.run();
    }
  }

  // --------------------------------------------------------------------------
  // route_history API
  // --------------------------------------------------------------------------

  /**
   * Retrieve the most recent route calculations (newest first).
   * @param {number} [limit=10]
   * @returns {Array<{ id, stops_json, result_json, calculated_at }>}
   */
  getRouteHistory(limit = 10) {
    return this._stmtGetRoutes.all(limit);
  }

  /**
   * Persist a calculated route. Enforces a maximum of config.maxRouteHistory rows.
   * @param {object} stops   The route stops/options that were sent to the API.
   * @param {object} result  The route result returned by the API.
   * @param {number} [maxRows=10]
   */
  saveRoute(stops, result, maxRows = 10) {
    const { cnt } = this._stmtCountRoutes.get();
    if (cnt >= maxRows) {
      this._stmtDeleteOldest.run();
    }
    this._stmtInsertRoute.run({
      stops_json:    JSON.stringify(stops),
      result_json:   JSON.stringify(result),
      calculated_at: Date.now(),
    });
  }

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------
  close() {
    if (this._db && this._db.open) this._db.close();
  }
}

module.exports = CacheLayer;
