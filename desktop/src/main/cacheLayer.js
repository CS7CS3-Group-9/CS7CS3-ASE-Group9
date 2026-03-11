'use strict';

const fs = require('fs');
const path = require('path');

/**
 * SQLite-backed local cache for offline dashboard data.
 *
 * Uses sql.js (pure-JS/WASM) — no native compilation required.
 * The database is loaded from and saved to disk on every write.
 *
 * Schema
 * ------
 * cache_entries  – key/value store for API response snapshots
 * route_history  – last N calculated routes for offline replay
 */
class CacheLayer {
  /**
   * Use CacheLayer.create(dbPath) to construct an instance.
   * @param {object} db      Initialised sql.js Database object.
   * @param {string} dbPath  Absolute path to the SQLite file (or ':memory:').
   */
  constructor(db, dbPath) {
    this._db = db;
    this._dbPath = dbPath;
    this._init();
  }

  /**
   * Async factory — initialises sql.js, loads existing DB file if present.
   * @param {string} dbPath  Absolute path to the SQLite file (or ':memory:').
   * @returns {Promise<CacheLayer>}
   */
  static async create(dbPath) {
    const initSqlJs = require('sql.js');
    // Locate the WASM binary relative to the installed sql.js package
    const wasmDir = path.dirname(require.resolve('sql.js'));
    const SQL = await initSqlJs({
      locateFile: file => path.join(wasmDir, file),
    });

    let db;
    if (dbPath !== ':memory:' && fs.existsSync(dbPath)) {
      const fileBuffer = fs.readFileSync(dbPath);
      db = new SQL.Database(fileBuffer);
    } else {
      db = new SQL.Database();
    }

    return new CacheLayer(db, dbPath);
  }

  // --------------------------------------------------------------------------
  // Schema setup
  // --------------------------------------------------------------------------
  _init() {
    this._db.run(`
      CREATE TABLE IF NOT EXISTS cache_entries (
        key         TEXT PRIMARY KEY,
        data_json   TEXT NOT NULL,
        fetched_at  INTEGER NOT NULL,
        ttl_seconds INTEGER NOT NULL DEFAULT 7200
      )
    `);

    this._db.run(`
      CREATE TABLE IF NOT EXISTS route_history (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        stops_json     TEXT NOT NULL,
        result_json    TEXT NOT NULL,
        calculated_at  INTEGER NOT NULL
      )
    `);
  }

  // Persist the in-memory database to disk after every write
  _save() {
    if (!this._dbPath || this._dbPath === ':memory:') return;
    try {
      const data = this._db.export();
      fs.writeFileSync(this._dbPath, Buffer.from(data));
    } catch (_err) {
      // Non-fatal — cache will be rebuilt from online data on next sync
    }
  }

  // --------------------------------------------------------------------------
  // cache_entries API
  // --------------------------------------------------------------------------

  /**
   * Retrieve a cache entry.
   * @param {string} key
   * @returns {{ data_json, fetched_at, ttl_seconds, age_seconds, is_stale } | null}
   */
  get(key) {
    const stmt = this._db.prepare('SELECT * FROM cache_entries WHERE key = :key');
    stmt.bind({ ':key': key });
    let row = null;
    if (stmt.step()) row = stmt.getAsObject();
    stmt.free();
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
    this._db.run(
      `INSERT INTO cache_entries (key, data_json, fetched_at, ttl_seconds)
       VALUES (:key, :data_json, :fetched_at, :ttl_seconds)
       ON CONFLICT(key) DO UPDATE SET
         data_json   = excluded.data_json,
         fetched_at  = excluded.fetched_at,
         ttl_seconds = excluded.ttl_seconds`,
      {
        ':key':         key,
        ':data_json':   JSON.stringify(data),
        ':fetched_at':  Date.now(),
        ':ttl_seconds': ttlSeconds,
      }
    );
    this._save();
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
      this._db.run('DELETE FROM cache_entries WHERE key = :key', { ':key': key });
    } else {
      this._db.run('DELETE FROM cache_entries');
    }
    this._save();
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
    const stmt = this._db.prepare(
      'SELECT * FROM route_history ORDER BY calculated_at DESC, id DESC LIMIT :limit'
    );
    stmt.bind({ ':limit': limit });
    const rows = [];
    while (stmt.step()) rows.push(stmt.getAsObject());
    stmt.free();
    return rows;
  }

  /**
   * Persist a calculated route. Enforces a maximum of maxRows rows.
   * @param {object} stops   The route stops/options sent to the API.
   * @param {object} result  The route result returned by the API.
   * @param {number} [maxRows=10]
   */
  saveRoute(stops, result, maxRows = 10) {
    const countStmt = this._db.prepare('SELECT COUNT(*) AS cnt FROM route_history');
    countStmt.step();
    const { cnt } = countStmt.getAsObject();
    countStmt.free();

    if (cnt >= maxRows) {
      this._db.run(`
        DELETE FROM route_history WHERE id = (
          SELECT id FROM route_history ORDER BY calculated_at ASC LIMIT 1
        )
      `);
    }

    this._db.run(
      `INSERT INTO route_history (stops_json, result_json, calculated_at)
       VALUES (:stops_json, :result_json, :calculated_at)`,
      {
        ':stops_json':    JSON.stringify(stops),
        ':result_json':   JSON.stringify(result),
        ':calculated_at': Date.now(),
      }
    );
    this._save();
  }

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------
  close() {
    if (this._db) {
      this._save();
      this._db.close();
      this._db = null;
    }
  }
}

module.exports = CacheLayer;
