'use strict';

const { spawn } = require('child_process');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const net = require('net');
const log = require('electron-log');

/**
 * Manages the lifecycle of the embedded Flask backend and frontend processes.
 *
 * In a packaged app (electron-builder), it looks for PyInstaller-compiled
 * binaries in process.resourcesPath. In development it falls back to launching
 * `python -m flask ...` directly using the project root as cwd.
 */
class ProcessManager {
  constructor(config) {
    this.config = config;
    this.backendProcess = null;
    this.frontendProcess = null;
    // __dirname = desktop/src/main  →  3 levels up = repo root
    this._projectRoot = path.join(__dirname, '..', '..', '..');
  }

  // --------------------------------------------------------------------------
  // Port availability check
  // --------------------------------------------------------------------------
  _isPortFree(port) {
    return new Promise((resolve) => {
      const srv = net.createServer();
      srv.once('error', () => resolve(false));
      srv.once('listening', () => { srv.close(); resolve(true); });
      srv.listen(port);
    });
  }

  async _findFreePort(preferred) {
    for (let p = preferred; p < preferred + 10; p++) {
      if (await this._isPortFree(p)) return p;
    }
    throw new Error(`No free port found near ${preferred}`);
  }

  // --------------------------------------------------------------------------
  // Determine Python executable
  // --------------------------------------------------------------------------
  _findPython() {
    for (const cmd of ['python3', 'python']) {
      try {
        const out = execSync(`${cmd} --version 2>&1`, { timeout: 3000 }).toString();
        const match = out.match(/Python (\d+)\.(\d+)/);
        if (match && (parseInt(match[1]) > 3 || (parseInt(match[1]) === 3 && parseInt(match[2]) >= 10))) {
          return cmd;
        }
      } catch (_) { /* try next */ }
    }
    throw new Error(
      'Python 3.10 or later is required but was not found.\n' +
      'Please install Python from https://python.org and restart the application.'
    );
  }

  // --------------------------------------------------------------------------
  // Resolve binary or fall back to Python
  // --------------------------------------------------------------------------
  _resolveBackendCommand() {
    const { app } = require('electron');
    if (app.isPackaged) {
      const binName = process.platform === 'win32' ? 'backend-server.exe' : 'backend-server';
      const binPath = path.join(process.resourcesPath, binName);
      if (fs.existsSync(binPath)) {
        return { cmd: binPath, args: [], cwd: process.resourcesPath };
      }
    }
    const python = this._findPython();
    return {
      cmd: python,
      args: ['-m', 'flask', '--app', 'backend.app:create_app', 'run',
             '--port', String(this.config.backendPort), '--no-debugger', '--no-reload'],
      cwd: this._projectRoot,
    };
  }

  _resolveFrontendCommand() {
    const { app } = require('electron');
    if (app.isPackaged) {
      const binName = process.platform === 'win32' ? 'frontend-server.exe' : 'frontend-server';
      const binPath = path.join(process.resourcesPath, binName);
      if (fs.existsSync(binPath)) {
        return { cmd: binPath, args: [], cwd: process.resourcesPath };
      }
    }
    const python = this._findPython();
    return {
      cmd: python,
      args: ['-m', 'flask', '--app', 'app:create_app', 'run',
             '--port', String(this.config.frontendPort), '--no-debugger', '--no-reload'],
      cwd: path.join(this._projectRoot, 'frontend'),
    };
  }

  // --------------------------------------------------------------------------
  // Spawn a process and pipe its output to electron-log
  // --------------------------------------------------------------------------
  _spawn(label, cmd, args, cwd, env) {
    log.info(`[${label}] Starting: ${cmd} ${args.join(' ')}`);
    const proc = spawn(cmd, args, {
      cwd,
      env,
      detached: false,
      windowsHide: true,
    });
    proc.stdout.on('data', (d) => log.info(`[${label}]`, d.toString().trim()));
    proc.stderr.on('data', (d) => log.warn(`[${label}]`, d.toString().trim()));
    proc.on('exit', (code, sig) => log.info(`[${label}] exited code=${code} sig=${sig}`));
    return proc;
  }

  // --------------------------------------------------------------------------
  // Poll until the process on the given port responds to HTTP
  // --------------------------------------------------------------------------
  _waitForReady(port, timeoutMs) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const tryFetch = async () => {
        try {
          // redirect:'manual' means we get the 302 instantly without waiting for
          // the redirected page (e.g. /dashboard/ which makes slow backend calls).
          // An opaque redirect has status 0, which satisfies status < 500.
          const resp = await fetch(`http://127.0.0.1:${port}/`, {
            signal: AbortSignal.timeout(3000),
            redirect: 'manual',
          });
          // status 0  = opaque redirect (302 → not yet followed) ✓
          // status 404 = backend has no / route ✓
          // status 200 = direct success ✓
          if (resp.ok || resp.status < 500) { resolve(); return; }
        } catch (_) { /* port not open yet — retry */ }

        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Process on port ${port} did not become ready within ${timeoutMs}ms`));
          return;
        }
        setTimeout(tryFetch, 500);
      };
      setTimeout(tryFetch, 500);
    });
  }

  // --------------------------------------------------------------------------
  // Public API
  // --------------------------------------------------------------------------
  async startBackend() {
    this.config.backendPort = await this._findFreePort(this.config.backendPort);
    const { cmd, args, cwd } = this._resolveBackendCommand();
    const env = {
      ...process.env,
      ENABLE_FIRESTORE: 'false',
      PORT: String(this.config.backendPort),
      FLASK_APP: 'backend.app:create_app',
    };
    this.backendProcess = this._spawn('backend', cmd, args, cwd, env);
    await this._waitForReady(this.config.backendPort, this.config.processReadyTimeoutMs);
  }

  async startFrontend() {
    this.config.frontendPort = await this._findFreePort(this.config.frontendPort);
    const { cmd, args, cwd } = this._resolveFrontendCommand();
    const env = {
      ...process.env,
      BACKEND_API_URL: `http://localhost:${this.config.backendPort}`,
      PORT: String(this.config.frontendPort),
      FLASK_APP: 'app:create_app',
      SECRET_KEY: `desktop-${Date.now()}`,
    };
    this.frontendProcess = this._spawn('frontend', cmd, args, cwd, env);
    await this._waitForReady(this.config.frontendPort, this.config.processReadyTimeoutMs);
  }

  stopAll() {
    for (const [label, proc] of [['backend', this.backendProcess], ['frontend', this.frontendProcess]]) {
      if (!proc) continue;
      try {
        log.info(`Stopping ${label} process (pid=${proc.pid})`);
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t']);
        } else {
          proc.kill('SIGTERM');
        }
      } catch (err) {
        log.warn(`Error stopping ${label}:`, err.message);
      }
    }
    this.backendProcess = null;
    this.frontendProcess = null;
  }
}

module.exports = ProcessManager;
