'use strict';

/**
 * Unit tests for ProcessManager.
 *
 * child_process.spawn is mocked so no real processes are launched.
 * electron's app.isPackaged is mocked to false (dev mode).
 */

const { EventEmitter } = require('events');

// Mock electron
jest.mock('electron', () => ({
  app: { isPackaged: false, getPath: jest.fn(() => '/tmp') },
}));

// Mock electron-log
jest.mock('electron-log', () => ({
  info:  jest.fn(),
  warn:  jest.fn(),
  error: jest.fn(),
}));

// Mock child_process.spawn
const mockSpawn = jest.fn();
jest.mock('child_process', () => ({
  spawn:     mockSpawn,
  execSync:  jest.fn(() => Buffer.from('Python 3.11.0')),
}));

// Mock fs.existsSync
jest.mock('fs', () => ({
  existsSync: jest.fn(() => false),   // dev mode: no packaged binaries
}));

// Mock net (for port availability checks)
jest.mock('net', () => {
  const actual = jest.requireActual('net');
  return {
    ...actual,
    createServer: jest.fn(() => {
      const srv = new EventEmitter();
      srv.listen = jest.fn(function () { this.emit('listening'); });
      srv.close  = jest.fn();
      return srv;
    }),
  };
});

const ProcessManager = require('../main/processManager');

function makeFakeProcess() {
  const proc = new EventEmitter();
  proc.pid    = 12345;
  proc.stdout = new EventEmitter();
  proc.stderr = new EventEmitter();
  proc.kill   = jest.fn();
  return proc;
}

describe('ProcessManager', () => {
  const config = {
    backendPort:            5001,
    frontendPort:           5002,
    processReadyTimeoutMs:  5000,
  };

  let pm;
  let fakeProc;
  let mockFetch;

  beforeEach(() => {
    fakeProc  = makeFakeProcess();
    mockSpawn.mockReturnValue(fakeProc);

    mockFetch = jest.fn().mockResolvedValue({ ok: true });
    global.fetch = mockFetch;
    global.AbortSignal = { timeout: jest.fn(() => ({})) };

    pm = new ProcessManager({ ...config });
  });

  afterEach(() => {
    jest.clearAllMocks();
    delete global.fetch;
    delete global.AbortSignal;
  });

  // --------------------------------------------------------------------------
  // startBackend
  // --------------------------------------------------------------------------
  describe('startBackend', () => {
    test('spawns python with correct flask arguments', async () => {
      await pm.startBackend();

      expect(mockSpawn).toHaveBeenCalledTimes(1);
      const [cmd, args] = mockSpawn.mock.calls[0];
      expect(cmd).toMatch(/python/);
      expect(args).toContain('-m');
      expect(args).toContain('flask');
      expect(args).toContain('run');
    });

    test('passes ENABLE_FIRESTORE=false in env', async () => {
      await pm.startBackend();
      const env = mockSpawn.mock.calls[0][2].env;
      expect(env.ENABLE_FIRESTORE).toBe('false');
    });

    test('passes PORT in env', async () => {
      await pm.startBackend();
      const env = mockSpawn.mock.calls[0][2].env;
      expect(env.PORT).toBe(String(config.backendPort));
    });
  });

  // --------------------------------------------------------------------------
  // startFrontend
  // --------------------------------------------------------------------------
  describe('startFrontend', () => {
    test('spawns python with flask run for the frontend', async () => {
      await pm.startFrontend();

      expect(mockSpawn).toHaveBeenCalledTimes(1);
      const [cmd, args] = mockSpawn.mock.calls[0];
      expect(cmd).toMatch(/python/);
      expect(args).toContain('flask');
    });

    test('sets BACKEND_API_URL env var for the frontend', async () => {
      await pm.startFrontend();
      const env = mockSpawn.mock.calls[0][2].env;
      expect(env.BACKEND_API_URL).toContain(String(config.backendPort));
    });
  });

  // --------------------------------------------------------------------------
  // stopAll
  // --------------------------------------------------------------------------
  describe('stopAll', () => {
    test('calls kill on both processes', async () => {
      const backProc  = makeFakeProcess();
      const frontProc = makeFakeProcess();
      mockSpawn
        .mockReturnValueOnce(backProc)
        .mockReturnValueOnce(frontProc);

      await pm.startBackend();
      await pm.startFrontend();
      pm.stopAll();

      if (process.platform !== 'win32') {
        expect(backProc.kill).toHaveBeenCalledWith('SIGTERM');
        expect(frontProc.kill).toHaveBeenCalledWith('SIGTERM');
      }
    });

    test('does not throw when called before any process is started', () => {
      expect(() => pm.stopAll()).not.toThrow();
    });

    test('nullifies process references after stopping', async () => {
      await pm.startBackend();
      pm.stopAll();
      expect(pm.backendProcess).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // _isPortFree
  // --------------------------------------------------------------------------
  describe('_isPortFree', () => {
    test('returns true when the port is free (server emits listening)', async () => {
      const free = await pm._isPortFree(9999);
      expect(free).toBe(true);
    });
  });
});
