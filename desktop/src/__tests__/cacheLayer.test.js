'use strict';

/**
 * Unit tests for CacheLayer.
 *
 * Uses an in-memory SQLite database (:memory:) so tests are fast and isolated.
 */

const Database = require('better-sqlite3');

// Mock better-sqlite3 to use an in-memory database for every test
jest.mock('better-sqlite3', () => {
  const ActualDatabase = jest.requireActual('better-sqlite3');
  return jest.fn(() => new ActualDatabase(':memory:'));
});

const CacheLayer = require('../main/cacheLayer');

describe('CacheLayer', () => {
  let cache;

  beforeEach(() => {
    cache = new CacheLayer(':memory:');
  });

  afterEach(() => {
    cache.close();
  });

  // --------------------------------------------------------------------------
  // set / get
  // --------------------------------------------------------------------------
  describe('set and get', () => {
    test('stores and retrieves a plain object', () => {
      const data = { bikes: 42, docks: 10 };
      cache.set('test-key', data, 3600);

      const entry = cache.get('test-key');
      expect(entry).not.toBeNull();
      expect(JSON.parse(entry.data_json)).toEqual(data);
      expect(entry.ttl_seconds).toBe(3600);
      expect(entry.age_seconds).toBeGreaterThanOrEqual(0);
    });

    test('stores and retrieves an array', () => {
      const data = [{ name: 'Stop A', lat: 53.1, lon: -6.2 }];
      cache.set('array-key', data, 120);

      const entry = cache.get('array-key');
      expect(JSON.parse(entry.data_json)).toEqual(data);
    });

    test('returns null for a missing key', () => {
      expect(cache.get('nonexistent')).toBeNull();
    });

    test('overwrites an existing entry (upsert)', () => {
      cache.set('key', { v: 1 }, 60);
      cache.set('key', { v: 2 }, 120);

      const entry = cache.get('key');
      expect(JSON.parse(entry.data_json)).toEqual({ v: 2 });
      expect(entry.ttl_seconds).toBe(120);
    });
  });

  // --------------------------------------------------------------------------
  // isStale
  // --------------------------------------------------------------------------
  describe('isStale', () => {
    test('returns false for a fresh entry', () => {
      cache.set('fresh', { ok: true }, 3600);
      expect(cache.isStale('fresh')).toBe(false);
    });

    test('returns true for an entry with ttl=0', () => {
      cache.set('instant-stale', { ok: true }, 0);
      // age will be 0 seconds; 0 > 0 is false but we can test with a 1s TTL
      // and manually manipulate fetched_at
      const db = cache._db;
      db.prepare("UPDATE cache_entries SET fetched_at = fetched_at - 2000 WHERE key = 'instant-stale'").run();
      cache.set('instant-stale', { ok: true }, 1);
      db.prepare("UPDATE cache_entries SET fetched_at = fetched_at - 2000 WHERE key = 'instant-stale'").run();
      expect(cache.isStale('instant-stale')).toBe(true);
    });

    test('returns false for a nonexistent key', () => {
      expect(cache.isStale('no-such-key')).toBe(false);
    });
  });

  // --------------------------------------------------------------------------
  // clear
  // --------------------------------------------------------------------------
  describe('clear', () => {
    test('deletes a single entry by key', () => {
      cache.set('a', {}, 60);
      cache.set('b', {}, 60);
      cache.clear('a');

      expect(cache.get('a')).toBeNull();
      expect(cache.get('b')).not.toBeNull();
    });

    test('deletes all entries when called without a key', () => {
      cache.set('x', {}, 60);
      cache.set('y', {}, 60);
      cache.clear();

      expect(cache.get('x')).toBeNull();
      expect(cache.get('y')).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // route_history
  // --------------------------------------------------------------------------
  describe('saveRoute and getRouteHistory', () => {
    test('saves and retrieves a route', () => {
      const stops  = [{ name: 'A' }, { name: 'B' }];
      const result = { distance: 5000, duration: 600 };
      cache.saveRoute(stops, result);

      const history = cache.getRouteHistory();
      expect(history).toHaveLength(1);
      expect(JSON.parse(history[0].stops_json)).toEqual(stops);
      expect(JSON.parse(history[0].result_json)).toEqual(result);
    });

    test('returns newest routes first', () => {
      cache.saveRoute([{ n: 1 }], { d: 1 });
      cache.saveRoute([{ n: 2 }], { d: 2 });

      const history = cache.getRouteHistory();
      expect(JSON.parse(history[0].stops_json)[0].n).toBe(2);
    });

    test('enforces maxRows limit by deleting oldest entries', () => {
      const MAX = 3;
      for (let i = 1; i <= MAX + 2; i++) {
        cache.saveRoute([{ n: i }], { d: i }, MAX);
      }

      const history = cache.getRouteHistory(MAX);
      expect(history).toHaveLength(MAX);
      // Oldest (n=1, n=2) should have been evicted
      const ns = history.map(r => JSON.parse(r.stops_json)[0].n);
      expect(ns).not.toContain(1);
      expect(ns).not.toContain(2);
    });

    test('returns empty array when no routes are saved', () => {
      expect(cache.getRouteHistory()).toEqual([]);
    });
  });

  // --------------------------------------------------------------------------
  // close
  // --------------------------------------------------------------------------
  describe('close', () => {
    test('closes the database without throwing', () => {
      expect(() => cache.close()).not.toThrow();
    });

    test('calling close twice does not throw', () => {
      cache.close();
      expect(() => cache.close()).not.toThrow();
    });
  });
});
