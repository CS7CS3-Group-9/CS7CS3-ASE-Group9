# Dublin City Dashboard

A real-time sustainable city management platform for Dublin. The system provides live data on bikes, buses, traffic, air quality, tours, and route planning through three components:

- **Backend** — Python Flask REST API, deployed on GKE
- **Frontend** — Python Flask web dashboard, deployed on GKE
- **Desktop App** — Windows desktop client (PyWebView) with offline caching

### Prerequisites
- Python 3.12+
- Dependencies (install once from repo root): `pip install -r requirements.txt`
Live deployment: http://ase-citydash-board.duckdns.org

---

## Architecture

```
Browser / Desktop App
        │
        ▼
Frontend (Flask, port 8080)   ←── session auth
        │
        ▼
Backend (Flask, port 5000)    ←── REST API
        │
        ├── Dublin Bikes API
        ├── TomTom Traffic API
        ├── OpenAQ Air Quality
        ├── Google Maps / TomTom Routing
        └── Firebase Firestore (optional)
```

The desktop app adds a local caching proxy (port 8080) in front of the cloud — the PyWebView window always loads from `localhost:8080`. The proxy forwards to the cloud when online and serves SQLite-cached responses when offline.

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.12
- Dependencies installed in separate venvs for backend and frontend

### One-command startup (PowerShell)

```powershell
.\localStart.ps1
```

This starts the backend on port 5000 and the frontend on port 8080.

### Manual startup

**Backend:**
```powershell
pip install -r backend/requirements.txt
$env:ENABLE_FIRESTORE="false"
$env:GOOGLE_MAPS_API_KEY="<your-key>"
$env:TOMTOM_API_KEY="<your-key>"
$env:BIKES_MODEL_PATH="backend\ml\artifacts\bikes_model.joblib"
python -m flask --app backend.app:create_app --debug run --port 5000
```

**Frontend (separate terminal):**
```powershell
pip install -r frontend/requirements.txt
$env:BACKEND_API_URL="http://localhost:5000"
$env:DASHBOARD_USERS_FILE="frontend/users.json"
$env:SECRET_KEY="change-me"
python -m flask --app frontend.app:create_app --debug run --port 8080
```

Then open http://localhost:8080. Default credentials are in `frontend/users.json`.

---

## Desktop App

The desktop app is a Windows application that wraps the cloud dashboard with offline support.

### Run from source

```powershell
# One-time setup
py -3.12 -m venv desktop\.venv
desktop\.venv\Scripts\activate
pip install -r desktop\requirements.txt

# Run
python -m desktop.app
```

### Build the installer

```powershell
desktop\.venv\Scripts\activate
pip install pyinstaller
pyinstaller desktop.spec
```

Output: `dist\DublinCityDashboard\DublinCityDashboard.exe`

To package as a one-click installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) then:

```powershell
iscc installer.iss
# Output: installer_output\DublinCityDashboard-Setup-1.0.0.exe
```

### Publish a release automatically

Tag the commit with `desktop-v<version>` and push — GitHub Actions builds and publishes the installer to the Releases page automatically:

```bash
git tag desktop-v1.0.1
git push origin desktop-v1.0.1
```

End users download `DublinCityDashboard-Setup-<version>.exe` from the Releases page and run it. No Python required. Works on Windows 10 (version 2004+) and Windows 11.

### How offline mode works

The PyWebView window always loads from `http://localhost:8080` (the local proxy), never directly from the cloud. When the cloud is unreachable:

- HTML, JSON, and static assets are served from a local SQLite cache (`%APPDATA%\DublinCityDashboard\cache.db`)
- OpenStreetMap tiles are served from a tile cache (30-day TTL)
- An amber banner appears at the bottom of the page within 5 seconds
- No page navigation occurs — the app stays on the cached version seamlessly

When connectivity returns the banner disappears and data refreshes within 60 seconds.

---

## Cloud Deployment

### Trigger

Push to the `prod` branch to deploy:

```bash
git push origin <your-branch>:prod
```

GitHub Actions (`.github/workflows/deploy-gke.yml`) builds and pushes Docker images then rolls out to GKE.

### Infrastructure

| Component | Details |
|-----------|---------|
| Platform | Google Kubernetes Engine |
| Project | `ase-city-management` |
| Cluster | `backend-test-cluster` (europe-west1-b) |
| Registry | `europe-west1-docker.pkg.dev/ase-city-management/route-app-repo` |
| Namespace | `default` |

### Required GitHub secrets

| Secret | Description |
|--------|-------------|
| `WIF_PROVIDER` | Workload Identity Federation provider |
| `GCP_SA_EMAIL` | GCP service account email |

### Required GKE secret

Create `api-keys` in the cluster before first deploy:

```bash
kubectl create secret generic api-keys \
  --from-literal=GOOGLE_MAPS_API_KEY=<key> \
  --from-literal=TOMTOM_API_KEY=<key>
```

---

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_FIRESTORE` | `false` | Enable Firebase Firestore |
| `GOOGLE_MAPS_API_KEY` | — | Google Maps API key (routing) |
| `TOMTOM_API_KEY` | — | TomTom API key (routing fallback) |
| `BIKES_MODEL_PATH` | — | Path to trained bikes ML model |
| `FORCE_BIKES_PREDICTION` | — | Set `1` to skip live API and use ML model |
| `WEATHER_FORECAST_PATH` | — | Path to cached weather CSV |
| `BIKES_WEATHER_ADJUSTMENT` | `true` | Apply rain adjustment to bike predictions |
| `WEATHER_AUTO_REFRESH` | `true` | Auto-refresh forecast on startup |
| `PORT` | `8080` | Server port (production) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_API_URL` | `http://localhost:5000` | Backend base URL |
| `SECRET_KEY` | `dev-secret-key-...` | Flask session secret — change in production |
| `DASHBOARD_USERS_FILE` | `frontend/users.json` | Path to users credentials file |
| `DASHBOARD_USERS_JSON` | — | Users as a JSON string (alternative to file) |
| `DESKTOP_TOKEN` | `dublin-dashboard-desktop-v1` | Shared secret for desktop app auth bypass |
| `REFRESH_INTERVAL` | `60` | Dashboard auto-refresh interval (seconds) |
| `PORT` | `8080` | Server port (production) |

### Desktop App

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_URL` | `http://ase-citydash-board.duckdns.org` | Cloud deployment URL |
| `DESKTOP_TOKEN` | `dublin-dashboard-desktop-v1` | Must match frontend `DESKTOP_TOKEN` |
| `PROXY_PORT` | `8080` | Local caching proxy port |
| `BACKEND_PORT` | `5001` | Local backend subprocess port |

> **Security note:** Change `DESKTOP_TOKEN` to a strong random string in production. Set the same value in the cloud deployment env vars and rebuild the desktop app.

---

## API Reference

All domain endpoints return a `MobilitySnapshot` envelope:

```json
{
  "timestamp": "2026-04-08T12:00:00+00:00",
  "location": "dublin",
  "source_status": { "bikes": "live", "traffic": "cached" },
  "bikes": { ... },
  "buses": { ... },
  "traffic": { ... },
  "airquality": { ... },
  "tours": { ... }
}
```

| Endpoint | Description |
|----------|-------------|
| `GET /snapshot` | All domains combined |
| `GET /bikes` | Dublin Bikes availability |
| `GET /bikes/stations` | Per-station bike data |
| `GET /buses/stops` | Bus stop locations |
| `GET /traffic` | Traffic incidents and flow |
| `GET /airquality` | Air quality index and pollutants |
| `GET /tours` | Dublin tour information |
| `GET /routing` | Route calculation |
| `GET /efficiency` | Transportation efficiency metrics |
| `GET /health` | Service health and adapter status |
| `GET /desktop/cache-warmup` | Bulk data for desktop cache seeding |

---

## ML Model (Bike Predictions)

The backend uses a scikit-learn model to predict bike availability when live data is unavailable.

**Train a model:**
```powershell
python backend\ml\train_bikes_model.py \
  --input "data\historical\dublin-bikes_station_status_042025.csv"
```

**With weather data:**
```powershell
python backend\ml\train_bikes_model.py \
  --input "data\historical\dublin-bikes_station_status_042025.csv" \
  --weather "data\historical\weather_forecast.csv"
```

**Refresh the 16-day weather forecast:**
```powershell
python scripts\fetch_weather_forecast.py --output "data\historical\weather_forecast.csv"
```

---

## Testing

**Smoke test** (requires backend running on port 5000):
```powershell
.\smoke_test.ps1
# or with custom URL:
.\smoke_test.ps1 -BaseUrl "http://127.0.0.1:5000"
# if execution policy blocks it:
powershell -ExecutionPolicy Bypass -File .\smoke_test.ps1
```

**Unit tests** run automatically on PRs via `.github/workflows/mergeTests.yml`.

---

## Contributing

### Branch and commit conventions

1. Branch names must reference the Jira ticket: `git checkout -b KAN-13`
2. Commit messages must start with the ticket ID: `git commit -m "KAN-13 Add feature"`
3. Push to your branch, not main: `git push origin KAN-13`
4. Open a PR — at least 1 review required before merging
5. Default merge strategy: **Squash and Merge**

### One-time developer setup (pre-commit hooks)

```powershell
python -m pip install pre-commit pycodestyle
python -m pre_commit install
```

Before every commit, the hook automatically:
- Runs **Black** to format Python code (if changes are made, re-stage and commit again)
- Runs **pycodestyle** to enforce PEP8 compliance
