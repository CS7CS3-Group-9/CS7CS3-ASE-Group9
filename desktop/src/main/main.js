'use strict';

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const log = require('electron-log');

const config = require('../../config/app.config');
const ProcessManager = require('./processManager');
const CacheLayer = require('./cacheLayer');
const ConnectivityMonitor = require('./connectivityMonitor');
const { registerIpcHandlers } = require('./ipcHandlers');
const TrayManager = require('./trayManager');

log.initialize();
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

let win = null;
let processManager = null;
let cacheLayer = null;
let connectivityMonitor = null;
let trayManager = null;
let syncTimer = null;

// --------------------------------------------------------------------------
// Paths for overlay / leaflet.offline scripts
// --------------------------------------------------------------------------
const overlayPath = path.join(__dirname, '..', 'renderer', 'desktop-overlay.js');
const leafletOfflinePath = path.join(
  __dirname, '..', '..', '..', 'node_modules',
  'leaflet.offline', 'dist', 'leaflet.offline.min.js'
);

// --------------------------------------------------------------------------
// Background sync — warm the SQLite cache from /desktop/cache-warmup
// --------------------------------------------------------------------------
async function runBackgroundSync() {
  if (!connectivityMonitor || !connectivityMonitor.isOnline) return;
  try {
    const url = `http://localhost:${config.backendPort}/desktop/cache-warmup`;
    const resp = await fetch(url, { signal: AbortSignal.timeout(30_000) });
    if (!resp.ok) return;
    const data = await resp.json();

    if (data.snapshot) {
      cacheLayer.set(config.cacheKeys.snapshot, data.snapshot, config.cacheTtl.snapshot);
      // Build analytics data from the snapshot and cache it too
      const analyticsData = buildAnalyticsFromSnapshot(data.snapshot);
      cacheLayer.set(config.cacheKeys.analytics, analyticsData, config.cacheTtl.analytics);
    }
    if (data.bike_stations) {
      cacheLayer.set(config.cacheKeys.bikeStations, data.bike_stations, config.cacheTtl.bikeStations);
    }
    if (data.bus_stops) {
      cacheLayer.set(config.cacheKeys.busStops, data.bus_stops, config.cacheTtl.busStops);
    }

    log.info('Background sync complete');
  } catch (err) {
    log.warn('Background sync failed:', err.message);
  }
}

// Mirror of Python analytics.py _build_chart_data so Node can cache analytics
function buildAnalyticsFromSnapshot(snapshot) {
  const aq = (snapshot.airquality || {});
  const pollutants = aq.pollutants || {};
  const aqKeys = ['pm2_5', 'pm10', 'nitrogen_dioxide', 'carbon_monoxide', 'ozone', 'sulphur_dioxide'];
  const aqLabels = ['PM2.5', 'PM10', 'NO\u2082', 'CO', 'O\u2083', 'SO\u2082'];
  const aqValues = aqKeys.map(k => Math.round((pollutants[k] || 0) * 100) / 100);

  const bikes = snapshot.bikes || {};
  const bikeValues = [
    bikes.available_bikes || 0,
    bikes.available_docks || 0,
    bikes.stations_reporting || 0,
  ];

  const traffic = snapshot.traffic || {};
  const byCat = traffic.incidents_by_category || {};
  const trafficLabels = Object.keys(byCat).length ? Object.keys(byCat) : ['No Incidents'];
  const trafficValues = Object.keys(byCat).length ? Object.values(byCat) : [0];

  return {
    air_quality_chart: { labels: aqLabels, values: aqValues },
    bike_chart: { labels: ['Available Bikes', 'Empty Docks', 'Stations Reporting'], values: bikeValues },
    traffic_chart: { labels: trafficLabels, values: trafficValues },
    timestamp: snapshot.timestamp || null,
  };
}

// --------------------------------------------------------------------------
// Inject overlay into every page after load
// --------------------------------------------------------------------------
function injectOverlay(webContents) {
  // Inject leaflet.offline if available (for map tile caching)
  if (fs.existsSync(leafletOfflinePath)) {
    try {
      const leafletOfflineCode = fs.readFileSync(leafletOfflinePath, 'utf8');
      webContents.executeJavaScript(leafletOfflineCode).catch(() => {});
    } catch (err) {
      log.warn('Could not inject leaflet.offline:', err.message);
    }
  }

  // Inject the desktop overlay (offline banner, fetch intercept, tile swap)
  if (fs.existsSync(overlayPath)) {
    try {
      const overlayCode = fs.readFileSync(overlayPath, 'utf8');
      webContents.executeJavaScript(overlayCode).catch(() => {});
    } catch (err) {
      log.warn('Could not inject desktop overlay:', err.message);
    }
  }
}

// --------------------------------------------------------------------------
// Create the main browser window
// --------------------------------------------------------------------------
function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Dublin City Dashboard',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  win.webContents.on('did-finish-load', () => {
    injectOverlay(win.webContents);
  });

  win.on('closed', () => { win = null; });

  return win;
}

// --------------------------------------------------------------------------
// Probe a URL — resolves true if it returns any non-5xx response
// --------------------------------------------------------------------------
async function probeUrl(url, timeoutMs = 5000) {
  try {
    const resp = await fetch(url, {
      signal: AbortSignal.timeout(timeoutMs),
      redirect: 'manual',
    });
    return resp.status === 0 || resp.status < 500;
  } catch (_) {
    return false;
  }
}

// --------------------------------------------------------------------------
<<<<<<< Updated upstream
// Wire up the connectivity monitor (shared between cloud and local modes)
// --------------------------------------------------------------------------
function startConnectivityMonitor(healthUrl) {
  connectivityMonitor = new ConnectivityMonitor(healthUrl, config.connectivityPollIntervalMs);
  connectivityMonitor.on('offline', ({ cachedAt }) => {
    log.warn('Connectivity lost — entering offline mode');
    if (win) win.webContents.send('connectivity:change', { online: false, cachedAt });
    if (trayManager) trayManager.setStatus('offline');
  });
  connectivityMonitor.on('online', () => {
    log.info('Connectivity restored — returning to online mode');
    if (win) win.webContents.send('connectivity:change', { online: true });
    if (trayManager) trayManager.setStatus('online');
    runBackgroundSync();
  });
  connectivityMonitor.start();
=======
// Send an IPC message after the next page load completes
// --------------------------------------------------------------------------
function sendAfterLoad(webContents, channel, payload) {
  webContents.once('did-finish-load', () => webContents.send(channel, payload));
>>>>>>> Stashed changes
}

// --------------------------------------------------------------------------
// App lifecycle
// --------------------------------------------------------------------------
app.whenReady().then(async () => {
  log.info('App starting...');

  // Initialise SQLite cache
  const dbPath = path.join(app.getPath('userData'), config.dbFileName);
  cacheLayer = await CacheLayer.create(dbPath);
  log.info('Cache database opened at', dbPath);

  // Initialise and register IPC handlers
  registerIpcHandlers(ipcMain, cacheLayer);

  processManager = new ProcessManager(config);

  const cloudReachable = config.cloudUrl && await probeUrl(config.cloudUrl);
<<<<<<< Updated upstream

  if (cloudReachable) {
    // -----------------------------------------------------------------------
    // CLOUD MODE — load cloud frontend instantly, warm cache in background
    // -----------------------------------------------------------------------
    log.info('Cloud reachable — loading cloud frontend');
    win = createWindow();
    win.loadURL(config.cloudUrl);

    // Start local backend silently in background for cache warming only.
    // Failures are non-fatal — offline cache just won't be refreshed.
    processManager.startBackend()
      .then(() => {
        log.info('Background backend ready — starting cache sync');
        runBackgroundSync();
        syncTimer = setInterval(runBackgroundSync, config.backgroundSyncIntervalMs);
      })
      .catch(err => log.warn('Background backend unavailable (cache warming skipped):', err.message));

    startConnectivityMonitor(`${config.cloudUrl}/health`);
=======
  const localFrontendUrl = `http://127.0.0.1:${config.frontendPort}`;

  win = createWindow();

  if (cloudReachable) {
    // -----------------------------------------------------------------------
    // CLOUD MODE — load cloud URL instantly, start local processes in background
    // for cache warming and mid-session offline fallback.
    // -----------------------------------------------------------------------
    log.info('Cloud reachable — loading cloud frontend');
    win.loadURL(config.cloudUrl);

    let localReady = false;

    processManager.startBackend()
      .then(() => {
        runBackgroundSync();
        syncTimer = setInterval(runBackgroundSync, config.backgroundSyncIntervalMs);
        return processManager.startFrontend();
      })
      .then(() => {
        localReady = true;
        log.info('Local processes ready — offline fallback available');
        // If we already went offline while waiting, switch now
        if (connectivityMonitor && !connectivityMonitor.isOnline && win) {
          win.loadURL(localFrontendUrl);
          sendAfterLoad(win.webContents, 'connectivity:change', {
            online: false, cachedAt: Date.now(),
          });
        }
      })
      .catch(err => log.warn('Background local processes unavailable:', err.message));

    connectivityMonitor = new ConnectivityMonitor(
      `${config.cloudUrl}/health`,
      config.connectivityPollIntervalMs
    );
    connectivityMonitor.on('offline', ({ cachedAt }) => {
      log.warn('Cloud unreachable — entering offline mode');
      if (trayManager) trayManager.setStatus('offline');
      if (localReady && win) {
        // Switch to local frontend; notify after it loads
        win.loadURL(localFrontendUrl);
        sendAfterLoad(win.webContents, 'connectivity:change', { online: false, cachedAt });
      } else {
        // Local not ready yet — overlay on current page handles it
        if (win) win.webContents.send('connectivity:change', { online: false, cachedAt });
      }
    });
    connectivityMonitor.on('online', () => {
      log.info('Cloud reachable again — switching back to cloud frontend');
      if (trayManager) trayManager.setStatus('online');
      if (win) {
        win.loadURL(config.cloudUrl);
        sendAfterLoad(win.webContents, 'connectivity:change', { online: true });
      }
      runBackgroundSync();
    });
>>>>>>> Stashed changes

  } else {
    // -----------------------------------------------------------------------
    // LOCAL MODE — start Flask processes then load local frontend
    // -----------------------------------------------------------------------
    log.info('Cloud unreachable — starting local Flask processes');
    try {
      await processManager.startBackend();
      log.info('Backend process ready on port', config.backendPort);
      await processManager.startFrontend();
      log.info('Frontend process ready on port', config.frontendPort);
    } catch (err) {
      log.error('Failed to start Flask processes:', err.message);
      dialog.showErrorBox(
        'Startup Error',
        `Could not start the application server:\n\n${err.message}\n\nPlease check the logs at ${log.transports.file.getFile().path}`
      );
      app.quit();
      return;
    }

<<<<<<< Updated upstream
    win = createWindow();
    win.loadURL(`http://localhost:${config.frontendPort}`);

    startConnectivityMonitor(`http://127.0.0.1:${config.backendPort}/health`);
=======
    win.loadURL(localFrontendUrl);

    connectivityMonitor = new ConnectivityMonitor(
      `http://127.0.0.1:${config.backendPort}/health`,
      config.connectivityPollIntervalMs
    );
    connectivityMonitor.on('offline', ({ cachedAt }) => {
      log.warn('Backend unreachable — entering offline mode');
      if (win) win.webContents.send('connectivity:change', { online: false, cachedAt });
      if (trayManager) trayManager.setStatus('offline');
    });
    connectivityMonitor.on('online', () => {
      log.info('Backend reachable — returning to online mode');
      if (win) win.webContents.send('connectivity:change', { online: true });
      if (trayManager) trayManager.setStatus('online');
      runBackgroundSync();
    });
>>>>>>> Stashed changes

    await runBackgroundSync();
    syncTimer = setInterval(runBackgroundSync, config.backgroundSyncIntervalMs);
  }

<<<<<<< Updated upstream
=======
  connectivityMonitor.start();

>>>>>>> Stashed changes
  // Tray icon (optional — silently skipped if no display or icon is missing)
  try {
    trayManager = new TrayManager(config, win, () => runBackgroundSync());
    trayManager.create();
  } catch (err) {
    log.warn('Tray icon unavailable (this is non-fatal):', err.message);
    trayManager = null;
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      win = createWindow();
<<<<<<< Updated upstream
      const url = cloudReachable ? config.cloudUrl : `http://localhost:${config.frontendPort}`;
=======
      const url = (cloudReachable && connectivityMonitor.isOnline)
        ? config.cloudUrl
        : localFrontendUrl;
>>>>>>> Stashed changes
      win.loadURL(url);
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  log.info('App shutting down');
  if (syncTimer) clearInterval(syncTimer);
  if (connectivityMonitor) connectivityMonitor.stop();
  if (trayManager) trayManager.destroy();
  if (processManager) processManager.stopAll();
  if (cacheLayer) cacheLayer.close();
});
