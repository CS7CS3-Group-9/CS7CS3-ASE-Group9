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
let cloudMonitor = null;
let internetMonitor = null;
let trayManager = null;
let syncTimer = null;

// --------------------------------------------------------------------------
// Mode state — updated by monitor events, read by will-navigate + overlay
// --------------------------------------------------------------------------
let cloudOnline    = false;
let internetOnline = false;
let currentMode    = 'offline'; // 'cloud' | 'local' | 'offline'

let localFrontendReady = false;
let localFrontendUrl   = '';

function computeMode(cloud, internet) {
  if (cloud)    return 'cloud';
  if (internet) return 'local';
  return 'offline';
}

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
  if (!internetOnline) return; // no point if we have no internet
  try {
    const url = `http://127.0.0.1:${config.backendPort}/desktop/cache-warmup`;
    const resp = await fetch(url, { signal: AbortSignal.timeout(30_000) });
    if (!resp.ok) return;
    const data = await resp.json();

    if (data.snapshot) {
      cacheLayer.set(config.cacheKeys.snapshot, data.snapshot, config.cacheTtl.snapshot);
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
  if (fs.existsSync(leafletOfflinePath)) {
    try {
      const leafletOfflineCode = fs.readFileSync(leafletOfflinePath, 'utf8');
      webContents.executeJavaScript(leafletOfflineCode).catch(() => {});
    } catch (err) {
      log.warn('Could not inject leaflet.offline:', err.message);
    }
  }

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
// Broadcast current mode to the loaded page
// --------------------------------------------------------------------------
function sendModeToPage() {
  if (!win) return;
  if (currentMode === 'offline') {
    win.webContents.send('connectivity:change', {
      online: false,
      mode: 'offline',
      cachedAt: internetMonitor ? internetMonitor._cachedAt : null,
    });
  } else {
    win.webContents.send('connectivity:change', { online: true, mode: currentMode });
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
    // Re-send current mode so the freshly-loaded page's overlay is up to date.
    // Without this a page navigated to while offline starts with _offline=false.
    setTimeout(() => { sendModeToPage(); }, 300);
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
// Shared mode-change handler — called whenever either monitor fires
// --------------------------------------------------------------------------
function onMonitorChange() {
  const newMode = computeMode(cloudOnline, internetOnline);
  if (newMode === currentMode) return;

  const prevMode = currentMode;
  currentMode = newMode;
  log.info(`Mode transition: ${prevMode} → ${currentMode}`);

  // When cloud goes offline, immediately navigate to local frontend so the
  // user sees live data from local backend rather than the stale cloud page.
  if (prevMode === 'cloud' && newMode === 'local' && localFrontendReady && win) {
    let targetPath = '';
    try {
      const currentUrl  = win.webContents.getURL();
      const cloudOrigin = new URL(config.cloudUrl).origin;
      const parsed      = new URL(currentUrl);
      if (parsed.origin === cloudOrigin && parsed.pathname !== '/') {
        targetPath = parsed.pathname + parsed.search;
      }
    } catch (_) {}
    win.loadURL(localFrontendUrl + targetPath);
    // did-finish-load → sendModeToPage will fire after the new page loads
    if (trayManager) trayManager.setStatus('online');
    runBackgroundSync();
    return;
  }

  sendModeToPage();

  if (currentMode === 'offline') {
    if (trayManager) trayManager.setStatus('offline');
  } else {
    if (trayManager) trayManager.setStatus('online');
    runBackgroundSync(); // refresh cache immediately when connectivity restored
  }
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

  registerIpcHandlers(ipcMain, cacheLayer);

  processManager = new ProcessManager(config);

  // Probe cloud and internet in parallel
  const [cloudReachable, internetReachable] = await Promise.all([
    config.cloudUrl ? probeUrl(config.cloudUrl, 10_000) : Promise.resolve(false),
    probeUrl(config.internetProbeUrl, 5_000),
  ]);

  cloudOnline    = cloudReachable;
  internetOnline = internetReachable;
  currentMode    = computeMode(cloudOnline, internetOnline);
  log.info(`Initial mode: ${currentMode} (cloud=${cloudOnline}, internet=${internetOnline})`);

  localFrontendUrl = `http://127.0.0.1:${config.frontendPort}`;

  win = createWindow();

  // -------------------------------------------------------------------------
  // Navigation intercept — redirect cloud-origin links to local frontend once
  // it's ready, and block cloud navigation entirely when offline.
  // -------------------------------------------------------------------------
  win.webContents.on('will-navigate', (event, url) => {
    if (!config.cloudUrl) return;
    try {
      const cloudOrigin = new URL(config.cloudUrl).origin;
      const target = new URL(url);
      if (target.origin !== cloudOrigin) return; // not a cloud link

      if (currentMode === 'offline') {
        event.preventDefault(); // stay on current page; overlay serves cache
      } else if (localFrontendReady && target.pathname !== '/' && target.pathname !== '') {
        event.preventDefault();
        win.loadURL(localFrontendUrl + target.pathname + target.search);
      }
    } catch (_) {}
  });

  // -------------------------------------------------------------------------
  // Initial page load
  // -------------------------------------------------------------------------
  if (currentMode === 'cloud') {
    // Load cloud URL instantly — local processes start in background
    log.info('Loading cloud frontend');
    win.loadURL(config.cloudUrl);
  }
  // For 'local' and 'offline' modes we wait for local processes before loading

  // -------------------------------------------------------------------------
  // Always start local processes (background for cloud mode, foreground otherwise)
  // -------------------------------------------------------------------------
  const localStartPromise = processManager.startBackend()
    .then(() => {
      log.info('Local backend ready on port', config.backendPort);
      runBackgroundSync();
      syncTimer = setInterval(runBackgroundSync, config.backgroundSyncIntervalMs);
      return processManager.startFrontend();
    })
    .then(() => {
      localFrontendReady = true;
      log.info('Local frontend ready on port', config.frontendPort);
      // If mode already switched to 'local' before processes finished, navigate now
      if (currentMode === 'local' && win) {
        win.loadURL(localFrontendUrl);
      }
    })
    .catch(err => log.warn('Local processes unavailable:', err.message));

  if (currentMode !== 'cloud') {
    // Must wait for local frontend before loading it
    try {
      await localStartPromise;
    } catch (_) {}
    if (localFrontendReady) {
      win.loadURL(localFrontendUrl);
    } else {
      dialog.showErrorBox(
        'Startup Error',
        'Could not start the local application server.\n\nPlease check the logs at ' +
        log.transports.file.getFile().path
      );
      app.quit();
      return;
    }
  }

  // -------------------------------------------------------------------------
  // Connectivity monitors
  // -------------------------------------------------------------------------
  cloudMonitor = new ConnectivityMonitor(
    `${config.cloudUrl}/health`,
    config.connectivityPollIntervalMs
  );
  internetMonitor = new ConnectivityMonitor(
    config.internetProbeUrl,
    config.connectivityPollIntervalMs
  );

  cloudMonitor.on('online',  () => { cloudOnline    = true;  onMonitorChange(); });
  cloudMonitor.on('offline', () => { cloudOnline    = false; onMonitorChange(); });
  internetMonitor.on('online',  () => { internetOnline = true;  onMonitorChange(); });
  internetMonitor.on('offline', () => { internetOnline = false; onMonitorChange(); });

  cloudMonitor.start();
  internetMonitor.start();

  // -------------------------------------------------------------------------
  // Tray icon
  // -------------------------------------------------------------------------
  try {
    trayManager = new TrayManager(config, win, () => runBackgroundSync());
    trayManager.create();
    if (currentMode === 'offline') trayManager.setStatus('offline');
  } catch (err) {
    log.warn('Tray icon unavailable (non-fatal):', err.message);
    trayManager = null;
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      win = createWindow();
      const url = (currentMode === 'cloud' && cloudOnline)
        ? config.cloudUrl
        : localFrontendUrl;
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
  if (cloudMonitor) cloudMonitor.stop();
  if (internetMonitor) internetMonitor.stop();
  if (trayManager) trayManager.destroy();
  if (processManager) processManager.stopAll();
  if (cacheLayer) cacheLayer.close();
});
