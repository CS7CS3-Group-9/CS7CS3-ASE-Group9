# Dublin City Dashboard — Desktop App

A cross-platform (Windows, macOS, Linux) desktop client for the Dublin Sustainable City Management Dashboard, built with [Electron](https://www.electronjs.org/).

The existing Flask web UI runs unchanged inside an Electron `BrowserWindow`. The app manages the backend and frontend as local processes and provides offline data caching via SQLite so the dashboard remains usable without an internet connection.

---

## Architecture

```
Electron main process
  ├── processManager  – spawns Python backend (port 5001) and frontend (port 5002)
  ├── cacheLayer      – SQLite cache via better-sqlite3
  ├── connectivityMonitor – polls GET /health every 30 s
  ├── ipcHandlers     – bridges renderer ↔ main via ipcMain
  └── trayManager     – system tray icon with connectivity indicator

Electron renderer (Chromium)
  └── loads http://localhost:5002 (existing Flask frontend, unchanged)
      └── desktop-overlay.js (injected)
          ├── offline banner UI
          ├── fetch() interceptor → returns SQLite cached data
          └── Leaflet tile layer swap → offline tile caching via leaflet.offline
```

---

## Development Setup

### Prerequisites

- **Node.js 20 LTS** — [nodejs.org](https://nodejs.org)
- **Python 3.10+** — [python.org](https://python.org)
- Install backend and frontend Python dependencies:

```bash
# From repo root
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### Install Electron dependencies

```bash
cd desktop
npm install
```

> `npm install` automatically runs `electron-rebuild` via the `postinstall` script, which compiles `better-sqlite3` against the correct Electron ABI.

### Run in development

```bash
cd desktop
npm start
```

The app will:
1. Start the Flask backend on port 5001 (auto-increments if busy)
2. Start the Flask frontend on port 5002
3. Open the dashboard in a `BrowserWindow`

### API Keys

The routing feature requires a Google Maps API key. Set it in your environment before starting:

```bash
export GOOGLE_MAPS_API_KEY=your-key-here
npm start
```

---

## Building Installers

### Step 1 — Build PyInstaller binaries

PyInstaller must be run **on the target platform** (Windows on Windows, macOS on macOS, etc.).

```bash
# From repo root — install PyInstaller first
pip install pyinstaller

# Build backend binary
pyinstaller desktop/pyinstaller/backend.spec \
  --distpath desktop/dist \
  --workpath desktop/build/pyinstaller

# Build frontend binary
pyinstaller desktop/pyinstaller/frontend.spec \
  --distpath desktop/dist \
  --workpath desktop/build/pyinstaller
```

This produces:
- `desktop/dist/backend-server` (or `.exe` on Windows)
- `desktop/dist/frontend-server` (or `.exe` on Windows)

### Step 2 — Build the Electron installer

```bash
cd desktop

# All platforms (requires correct OS)
npm run build

# Platform-specific
npm run build:win      # NSIS installer (.exe)
npm run build:mac      # DMG (.dmg)
npm run build:linux    # AppImage (.AppImage)
```

Output is in `desktop/build/`.

---

## Offline Behaviour

| Feature | Online | Offline |
|---------|--------|---------|
| Dashboard KPIs | Live data | SQLite cached snapshot (up to 2 min stale) |
| Map markers | Live bike/bus/traffic data | Cached markers from SQLite |
| Map tiles | OSM tile servers | IndexedDB cache (tiles saved while browsing) |
| Analytics charts | Live | Cached chart data |
| Recommendations | Live | Rebuilt from cached snapshot |
| Route planner | Full Google Routing | Last 10 routes replayed; "requires internet" otherwise |

The offline banner shows the timestamp of the last cached data refresh. Tiles are cached automatically as you pan/zoom the map — the more you browse while online, the more complete the offline map coverage.

---

## Directory Structure

```
desktop/
├── package.json              Electron app manifest and electron-builder config
├── config/
│   └── app.config.js         Ports, TTLs, cache keys
├── src/
│   ├── main/
│   │   ├── main.js           App entry point
│   │   ├── processManager.js Python subprocess lifecycle
│   │   ├── cacheLayer.js     SQLite cache (better-sqlite3)
│   │   ├── connectivityMonitor.js  Health polling
│   │   ├── ipcHandlers.js    IPC bridge
│   │   └── trayManager.js    System tray
│   ├── preload/
│   │   └── preload.js        contextBridge → window.electronAPI
│   └── renderer/
│       └── desktop-overlay.js  Offline banner + fetch intercept + tile swap
├── pyinstaller/
│   ├── backend.spec          PyInstaller config for Flask backend
│   └── frontend.spec         PyInstaller config for Flask frontend
├── assets/
│   ├── icon.png              App icon (512×512, replace with your own)
│   ├── icon.ico              Windows icon
│   └── tray-icon.png         System tray icon (22×22)
└── src/__tests__/
    ├── cacheLayer.test.js
    ├── connectivityMonitor.test.js
    └── processManager.test.js
```

---

## Tests

```bash
cd desktop
npm test
```

---

## Known Limitations

- **Map tiles on first offline use**: Tiles are cached lazily as you browse. If you have not browsed the map while online, tiles will be missing offline. Pan and zoom around Dublin while online to seed the cache.
- **Routing offline**: The route planner requires Google Geocoding and Routes API access. Offline, only previously calculated routes (last 10) can be replayed.
- **PyInstaller + Firestore**: Desktop mode always sets `ENABLE_FIRESTORE=false`. The Firestore/Firebase Admin SDK is excluded from the PyInstaller build.
- **Code signing**: For Windows distribution, configure `win.certificateFile` in `package.json` to avoid antivirus false positives on PyInstaller binaries.
