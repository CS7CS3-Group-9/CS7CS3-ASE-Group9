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

  // Start Flask processes
  processManager = new ProcessManager(config);
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

  // Create the browser window
  win = createWindow();
  win.loadURL(`http://localhost:${config.frontendPort}`);

  // Start connectivity monitor
  connectivityMonitor = new ConnectivityMonitor(config.backendPort, config.connectivityPollIntervalMs);
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
  connectivityMonitor.start();

  // Tray icon (optional — silently skipped if no display or icon is missing)
  try {
    trayManager = new TrayManager(config, win, () => runBackgroundSync());
    trayManager.create();
  } catch (err) {
    log.warn('Tray icon unavailable (this is non-fatal):', err.message);
    trayManager = null;
  }

  // Run initial background sync
  await runBackgroundSync();

  // Schedule periodic background sync
  syncTimer = setInterval(runBackgroundSync, config.backgroundSyncIntervalMs);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      win = createWindow();
      win.loadURL(`http://localhost:${config.frontendPort}`);
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
