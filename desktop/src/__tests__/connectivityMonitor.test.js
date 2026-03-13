'use strict';

/**
 * Unit tests for ConnectivityMonitor.
 *
 * fetch() is mocked globally so no real HTTP requests are made.
 */

const ConnectivityMonitor = require('../main/connectivityMonitor');

// Silence electron-log in tests
jest.mock('electron-log', () => ({
  info:  jest.fn(),
  warn:  jest.fn(),
  error: jest.fn(),
}));

describe('ConnectivityMonitor', () => {
  let monitor;
  let mockFetch;

  beforeEach(() => {
    jest.useFakeTimers();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    global.AbortSignal = { timeout: jest.fn(() => ({})) };

    monitor = new ConnectivityMonitor('http://127.0.0.1:5001/health', 30_000);
  });

  afterEach(() => {
    monitor.stop();
    jest.useRealTimers();
    delete global.fetch;
    delete global.AbortSignal;
  });

  // --------------------------------------------------------------------------
  // Initial state
  // --------------------------------------------------------------------------
  test('starts as online (optimistic)', () => {
    expect(monitor.isOnline).toBe(true);
  });

  // --------------------------------------------------------------------------
  // Online → offline transition
  // --------------------------------------------------------------------------
  test('emits "offline" when health check fails and was previously online', async () => {
    mockFetch.mockRejectedValue(new Error('ECONNREFUSED'));

    const offlineSpy = jest.fn();
    monitor.on('offline', offlineSpy);

    monitor.start();
    await Promise.resolve(); // allow _poll() microtask to run

    expect(offlineSpy).toHaveBeenCalledTimes(1);
    expect(offlineSpy.mock.calls[0][0]).toHaveProperty('cachedAt');
    expect(monitor.isOnline).toBe(false);
  });

  // --------------------------------------------------------------------------
  // Offline → online transition
  // --------------------------------------------------------------------------
  test('emits "online" when health check succeeds and was previously offline', async () => {
    monitor.isOnline = false; // simulate pre-existing offline state

    mockFetch.mockResolvedValue({ ok: true });

    const onlineSpy = jest.fn();
    monitor.on('online', onlineSpy);

    monitor.start();
    await Promise.resolve();

    expect(onlineSpy).toHaveBeenCalledTimes(1);
    expect(monitor.isOnline).toBe(true);
  });

  // --------------------------------------------------------------------------
  // No duplicate events
  // --------------------------------------------------------------------------
  test('does not emit "offline" again if already offline', async () => {
    mockFetch.mockRejectedValue(new Error('fail'));
    monitor.isOnline = false; // pre-set to offline

    const offlineSpy = jest.fn();
    monitor.on('offline', offlineSpy);

    monitor.start();
    await Promise.resolve();

    expect(offlineSpy).not.toHaveBeenCalled();
  });

  test('does not emit "online" again if already online', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    monitor.isOnline = true; // pre-set to online

    const onlineSpy = jest.fn();
    monitor.on('online', onlineSpy);

    monitor.start();
    await Promise.resolve();

    expect(onlineSpy).not.toHaveBeenCalled();
  });

  // --------------------------------------------------------------------------
  // Polling interval
  // --------------------------------------------------------------------------
  test('polls at the configured interval', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    monitor.start();

    // Allow initial poll
    await Promise.resolve();
    const callsAfterStart = mockFetch.mock.calls.length;

    // Advance timer by one interval
    jest.advanceTimersByTime(30_000);
    await Promise.resolve();

    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterStart);
  });

  // --------------------------------------------------------------------------
  // stop()
  // --------------------------------------------------------------------------
  test('stops polling after stop() is called', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    monitor.start();
    await Promise.resolve();

    monitor.stop();
    const callsAtStop = mockFetch.mock.calls.length;

    jest.advanceTimersByTime(60_000);
    await Promise.resolve();

    // No additional calls after stop
    expect(mockFetch.mock.calls.length).toBe(callsAtStop);
  });
});
