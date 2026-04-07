# Group 9 — Sustainable City Management: Semester 2 Deliverables

**Module:** CS7CS3 Advanced Software Engineering  
**Team:** Group 9  
**Contributors:** Oisin Power, Darragh Hassett, Ciarán O'Malley, Parker Kavanagh, Aoife Walshe

---

## Table of Contents
1. [Technical Architecture Description](#1-technical-architecture-description)
2. [Functional Architecture Description](#2-functional-architecture-description)
3. [Detailed System Structure Models](#3-detailed-system-structure-models)
4. [Detailed System Behavioural Models](#4-detailed-system-behavioural-models)
5. [Project Diary](#5-project-diary)
6. [Compile and Deployment Instructions](#6-compile-and-deployment-instructions)

---

## 1. Technical Architecture Description

### Diagram

```mermaid
graph TB
    subgraph Client["Client Layer"]
        Browser["Web Browser"]
    end

    subgraph FE["Frontend Service (Flask + Jinja2)"]
        FEApp["Flask App\n(frontend/app.py)"]
        Auth["Auth Blueprint\n(/login, /users)"]
        Overview["Overview Blueprint\n(/dashboard)"]
        Analytics["Analytics Blueprint\n(/dashboard/analytics)"]
        Routing_UI["Routing Blueprint\n(/dashboard/routing)"]
        Recs["Recommendations Blueprint\n(/dashboard/recommendations)"]
        Templates["Jinja2 Templates\n+ Leaflet.js + Chart.js"]
    end

    subgraph BE["Backend API Service (Flask)"]
        BEApp["Flask App\n(backend/app.py)"]

        subgraph Endpoints["API Endpoints (Blueprints)"]
            EP_bikes["/bikes"]
            EP_traffic["/traffic"]
            EP_air["/airquality"]
            EP_buses["/buses/stops"]
            EP_tours["/tours"]
            EP_snap["/snapshot"]
            EP_route["/routing/calculate"]
            EP_auth["/auth/*"]
            EP_health["/health"]
            EP_eff["/efficiency"]
        end

        subgraph SVC["Services Layer"]
            SnapSvc["SnapshotService\n(ThreadPoolExecutor)"]
        end

        subgraph Adapters["Adapters Layer"]
            BikesAdp["BikesAdapter"]
            TrafficAdp["TrafficAdapter"]
            AirAdp["AirQualityAdapter"]
            BusAdp["BusAdapter (GTFS)"]
            TourAdp["TourAdapter"]
            RoutesAdp["RoutesAdapter"]
        end

        subgraph Analytics["Analytics Layer"]
            TrafficAn["traffic_analytics"]
            AirAn["airquality_analytics"]
            BikeAn["bike_analytics"]
            BusAn["bus_analytics"]
        end

        subgraph Fallback["Fallback / Cache Layer"]
            Cache["AdapterCache\n(in-memory + Firestore)"]
            BikePred["BikesPredictior\n(sklearn RF)"]
            TrafficPred["TrafficPredictor\n(SUMO histogram)"]
        end

        subgraph LocalNet["Dublin Network Module"]
            NetParser["network_parser\n(DCC.net.xml)"]
            Router["DublinRouter\n(Dijkstra)"]
            TripPred["TrafficPredictor\n(all_trips.csv)"]
        end

        subgraph Models["Domain Models"]
            MobSnap["MobilitySnapshot"]
            BikeM["BikeMetrics"]
            TrafficM["TrafficMetrics"]
            AirM["AirQualitySnapshot"]
            BusM["BusMetrics"]
            TourM["AttractionMetrics"]
            RouteM["RouteRecommendation"]
        end
    end

    subgraph External["External APIs"]
        CityBikes["CityBikes API\n(api.citybik.es)"]
        TomTom["TomTom Traffic API"]
        OpenMeteo["Open-Meteo\n(Air Quality + Weather)"]
        Overpass["OSM Overpass API\n(Tourism)"]
        GoogleRoutes["Google Routes API v2"]
        GoogleGeo["Google Geocoding API"]
    end

    subgraph Persist["Persistence"]
        Firestore["Cloud Firestore\n(cache persistence)"]
        GTFS["GTFS CSVs\n(bus data)"]
        UsersJSON["users.json\n(auth)"]
        MLArtifact["bikes_model.joblib\n(ML artifact)"]
        SUMONet["DCC.net.xml\n(SUMO network)"]
        Trips["all_trips.csv\n(500k trips)"]
    end

    subgraph Infra["Infrastructure (GCP)"]
        CloudBuild["Cloud Build\n(CI/CD)"]
        GKE["GKE Cluster\n(Kubernetes)"]
        GitHub["GitHub Actions\n(PR tests)"]
    end

    Browser --> FEApp
    FEApp --> Auth
    FEApp --> Overview
    FEApp --> Analytics
    FEApp --> Routing_UI
    FEApp --> Recs
    FEApp --> Templates

    FEApp -->|HTTP REST| BEApp
    Overview -->|"/snapshot, /bikes/stations, /buses/stops"| BEApp
    Analytics -->|"/airquality, /traffic, /bikes, /buses"| BEApp
    Routing_UI -->|"/routing/calculate"| BEApp
    Recs -->|"/snapshot"| BEApp

    BEApp --> Endpoints
    EP_snap --> SnapSvc
    EP_bikes --> BikesAdp
    EP_traffic --> TrafficAdp
    EP_air --> AirAdp
    EP_buses --> BusAdp
    EP_tours --> TourAdp
    EP_route --> RoutesAdp

    SnapSvc --> BikesAdp
    SnapSvc --> TrafficAdp
    SnapSvc --> AirAdp
    SnapSvc --> BusAdp
    SnapSvc --> TourAdp

    BikesAdp -->|"resolve_with_cache"| Cache
    TrafficAdp -->|"resolve_with_cache"| Cache
    AirAdp -->|"resolve_with_cache"| Cache

    Cache -->|"on miss"| BikePred
    Cache -->|"on miss"| TrafficPred

    BikesAdp --> CityBikes
    TrafficAdp --> TomTom
    AirAdp --> OpenMeteo
    TourAdp --> Overpass
    RoutesAdp --> GoogleRoutes
    RoutesAdp --> GoogleGeo

    BusAdp --> GTFS
    EP_auth --> UsersJSON
    BikePred --> MLArtifact
    Cache <-->|"optional"| Firestore

    Router --> NetParser
    NetParser --> SUMONet
    TripPred --> Trips

    SnapSvc --> Analytics
    Analytics --> Models
    Adapters --> Models

    CloudBuild --> GKE
    GitHub --> CloudBuild
```

### Changes from Thin Slice

The thin slice architecture (Semester 1) established the adapter pattern, core models, and GKE deployment. Semester 2 additions include:

- **Frontend Service**: A complete Flask/Jinja2 dashboard was added with Leaflet.js maps, Chart.js analytics, and a multi-stop route planner — this is an entirely new service not present in the thin slice.
- **Dublin Network Module** (`backend/dublin_network/`): Renamed and extended from a prototype traffic model. Now includes full SUMO network parsing (`DCC.net.xml`, 115K lines), Dijkstra-based local routing, and a 500k-trip historical predictor as a fully offline fallback.
- **ML Layer** (`backend/ml/`): A scikit-learn RandomForest model for bike availability prediction was added, trained on historical Dublin Bikes station data with optional weather integration.
- **Bus Analytics**: A comprehensive GTFS-based bus module was added (`BusAdapter`, `bus_analytics`), parsing stop times to compute wait times, top-served stops, and importance scores — absent from the thin slice.
- **Fallback/Cache Layer**: The `AdapterCache` was extended with Firestore-backed persistence (optional) to survive Cloud Run/GKE pod restarts.
- **Auth Module**: User login, role-based access (admin/user), and user management endpoints were added.
- **Efficiency Endpoint**: A new `/efficiency` endpoint for transport emissions calculations.

---

## 2. Functional Architecture Description

### Diagram

```mermaid
graph LR
    subgraph Users["Actors"]
        CityUser["City Dashboard User\n(viewer)"]
        AdminUser["Admin User\n(management)"]
    end

    subgraph Functions["Core Functions"]
        subgraph Monitoring["City Monitoring"]
            F1["View Live Map\n(bikes, buses, incidents)"]
            F2["Check Air Quality"]
            F3["View Traffic Incidents"]
            F4["Browse Attractions"]
        end

        subgraph Analytics["Analytics & Insights"]
            F5["Analyse Bike Availability\n(trends, predictions)"]
            F6["Analyse Bus Wait Times\n(top stops, GTFS)"]
            F7["Analyse Traffic Patterns\n(category, severity)"]
            F8["Correlations & Alerts"]
        end

        subgraph Planning["Journey Planning"]
            F9["Plan Multi-Stop Route\n(driving/cycling/transit)"]
            F10["Optimise Stop Order\n(TSP)"]
            F11["Local Offline Routing\n(fallback, SUMO network)"]
        end

        subgraph Resilience["Data Resilience"]
            F12["Live API Fetch\n(CityBikes, TomTom, etc.)"]
            F13["Serve Cached Data\n(memory + Firestore)"]
            F14["ML Prediction Fallback\n(bikes model, trip histogram)"]
        end

        subgraph Admin["Administration"]
            F15["Login / Logout"]
            F16["Manage Users\n(create, delete, role)"]
            F17["Health Check\n(/health)"]
        end
    end

    subgraph Data["Data Sources"]
        DS1["CityBikes API\n(real-time)"]
        DS2["TomTom Traffic API\n(real-time)"]
        DS3["Open-Meteo\n(air quality + weather)"]
        DS4["OSM Overpass API\n(tourism)"]
        DS5["Google Routes API\n(routing)"]
        DS6["GTFS CSVs\n(bus schedule)"]
        DS7["SUMO DCC.net.xml\n(road network)"]
        DS8["Historical Bike CSVs\n(ML training)"]
    end

    CityUser --> F1
    CityUser --> F2
    CityUser --> F3
    CityUser --> F4
    CityUser --> F5
    CityUser --> F6
    CityUser --> F7
    CityUser --> F8
    CityUser --> F9
    CityUser --> F10
    CityUser --> F15

    AdminUser --> F15
    AdminUser --> F16
    AdminUser --> F17
    AdminUser --> F1
    AdminUser --> F5

    F1 --> F12
    F2 --> F12
    F3 --> F12
    F4 --> F12
    F5 --> F12
    F6 --> F12

    F12 -->|"success"| DS1
    F12 -->|"success"| DS2
    F12 -->|"success"| DS3
    F12 -->|"success"| DS4
    F12 -->|"fail → fallback"| F13
    F13 -->|"expired → fallback"| F14

    F9 --> DS5
    F11 --> DS7
    F9 -->|"Google unavailable"| F11

    F6 --> DS6
    F14 --> DS8
    F14 -->|"traffic"| DS7
```

### Changes from Thin Slice

The functional architecture is largely consistent with the thin slice design. The key additions are:

- **Journey Planning** functions (F9–F11) were implemented in full, including TSP-based stop optimisation and the offline SUMO routing fallback.
- **Bus Analytics** (F6) was promoted from a placeholder to a fully working function backed by GTFS data.
- **ML Prediction Fallback** (F14) was implemented and integrated into the resilience chain.
- **Administration** (F15–F17) was added: login, user management, and health checks.
- The **Data Resilience** chain (F12 → F13 → F14) now completes the three-tier fallback that was only partially designed in the thin slice.

---

## 3. Detailed System Structure Models

### 3.1 Core Domain Model (UML Class Diagram)

```mermaid
classDiagram
    class MobilitySnapshot {
        +timestamp: datetime
        +location: str
        +source_status: dict
        +bikes: BikeMetrics
        +buses: BusMetrics
        +traffic: TrafficMetrics
        +airquality: AirQualitySnapshot
        +population: dict
        +tours: AttractionMetrics
        +alerts: list
        +recommendations: list
    }

    class BikeMetrics {
        +available_bikes: int
        +available_docks: int
        +stations_reporting: int
        +stations: list~StationMetrics~
    }

    class StationMetrics {
        +name: str
        +free_bikes: int
        +empty_slots: int
        +total_spaces: int
        +availability_percent: float
        +latitude: float
        +longitude: float
    }

    class TrafficMetrics {
        +congestion_level: str
        +incidents: list~TrafficIncident~
        +incidents_by_category: dict
        +total_delay_minutes: float
        +incident_count: int
    }

    class TrafficIncident {
        +category: str
        +severity: int
        +from_location: str
        +to_location: str
        +delay_minutes: float
        +latitude: float
        +longitude: float
    }

    class AirQualitySnapshot {
        +location: str
        +timestamp: datetime
        +metrics: AirQualityMetrics
        +level: str
    }

    class AirQualityMetrics {
        +aqi_value: float
        +pollutants: PollutantLevels
    }

    class PollutantLevels {
        +pm2_5: float
        +pm10: float
        +no2: float
        +co: float
        +o3: float
        +so2: float
    }

    class BusMetrics {
        +stops: list~BusStop~
        +routes: list~BusRoute~
        +stop_frequencies: dict
        +wait_time_summary: dict
        +top_served_stops: list
    }

    class BusStop {
        +stop_id: str
        +name: str
        +lat: float
        +longitude: float
    }

    class BusRoute {
        +route_id: str
        +route_name: str
        +stops: list~BusStop~
    }

    class AttractionMetrics {
        +attractions: list~Attraction~
        +total_count: int
        +by_type: dict
    }

    class Attraction {
        +name: str
        +type: str
        +latitude: float
        +longitude: float
        +wheelchair_accessible: bool
        +tags: dict
    }

    class RouteRecommendation {
        +start: str
        +end: str
        +transport_mode: str
        +waypoints: list
        +multi_stop_data: MultiStopRoute
        +duration_seconds: int
        +distance_meters: int
    }

    class MultiStopRoute {
        +optimal_route_order: list~str~
        +legs: list~RouteLeg~
        +total_duration_seconds: int
        +total_distance_meters: int
    }

    class RouteLeg {
        +start: str
        +end: str
        +duration_seconds: int
        +distance_meters: int
        +polyline: str
    }

    MobilitySnapshot "1" --> "0..1" BikeMetrics
    MobilitySnapshot "1" --> "0..1" TrafficMetrics
    MobilitySnapshot "1" --> "0..1" AirQualitySnapshot
    MobilitySnapshot "1" --> "0..1" BusMetrics
    MobilitySnapshot "1" --> "0..1" AttractionMetrics
    BikeMetrics "1" --> "0..*" StationMetrics
    TrafficMetrics "1" --> "0..*" TrafficIncident
    AirQualitySnapshot "1" --> "1" AirQualityMetrics
    AirQualityMetrics "1" --> "1" PollutantLevels
    BusMetrics "1" --> "0..*" BusStop
    BusMetrics "1" --> "0..*" BusRoute
    BusRoute "1" --> "0..*" BusStop
    AttractionMetrics "1" --> "0..*" Attraction
    RouteRecommendation "1" --> "1" MultiStopRoute
    MultiStopRoute "1" --> "1..*" RouteLeg
```

### 3.2 Adapter Layer (UML Class Diagram)

```mermaid
classDiagram
    class DataAdapter {
        <<abstract>>
        +source_name() str
        +fetch(**kwargs) any
    }

    class BikesAdapter {
        -BASE_URL: str
        +source_name() str
        +fetch(location) BikeMetrics
    }

    class BikeStationsAdapter {
        +source_name() str
        +fetch(radius_km, lat, lon) list~StationMetrics~
    }

    class TrafficAdapter {
        -API_KEY: str
        -BASE_URL: str
        +source_name() str
        +fetch(location, radius_km) TrafficMetrics
    }

    class AirQualityAdapter {
        -BASE_URL: str
        +source_name() str
        +fetch(lat, lon) AirQualitySnapshot
    }

    class TourAdapter {
        -OVERPASS_URL: str
        +source_name() str
        +fetch(radius_km) AttractionMetrics
    }

    class RoutesAdapter {
        -GEOCODING_URL: str
        -ROUTES_URL: str
        -API_KEY: str
        +source_name() str
        +fetch(stops, mode, optimize, type) RouteRecommendation
        -geocode(address) tuple~float,float~
        -tsp_optimize(stops, locked) list
    }

    class BusAdapter {
        -_METRICS_CACHE: dict
        -GTFS_DIR: str
        +source_name() str
        +fetch(radius_km, lat, lon) BusMetrics
        -load_stops() DataFrame
        -load_stop_times() DataFrame
    }

    DataAdapter <|-- BikesAdapter
    DataAdapter <|-- BikeStationsAdapter
    DataAdapter <|-- TrafficAdapter
    DataAdapter <|-- AirQualityAdapter
    DataAdapter <|-- TourAdapter
    DataAdapter <|-- RoutesAdapter
    DataAdapter <|-- BusAdapter
```

### 3.3 Services, Fallback and ML (UML Class Diagram)

```mermaid
classDiagram
    class SnapshotService {
        +build_snapshot(adapter_specs, lat, lon) MobilitySnapshot
        -_fetch_one(spec) partial_snapshot
        -_merge(partials) MobilitySnapshot
        -_run_analytics(snapshot) MobilitySnapshot
    }

    class AdapterCallSpec {
        +adapter: DataAdapter
        +kwargs: dict
    }

    class AdapterCache {
        -_cache: dict
        -_db: Firestore
        +fetch_with_fallback(adapter, **kwargs) tuple
        +get(key) any
        +set(key, value, ttl) void
        +invalidate(key) void
    }

    class Predictor {
        <<abstract>>
        +predict(**kwargs) any
    }

    class BikesPredictior {
        -_model: RandomForestRegressor
        -_model_path: str
        +predict(hour, day_of_week, weather) BikeMetrics
        -_load_model() void
    }

    class BikesStationPredictor {
        -_models: dict
        +predict(station_id, hour, day_of_week) StationMetrics
    }

    class TrafficPredictor {
        -_trip_histogram: dict
        -_all_trips_path: str
        +predict(hour, day_of_week) TrafficMetrics
        -_build_histogram() void
    }

    class DublinNetworkParser {
        -_network: DublinNetwork
        +get_network() DublinNetwork
        -parse_xml(path) DublinNetwork
    }

    class DublinRouter {
        -_network: DublinNetwork
        -CONGESTION_FACTOR: float
        +route(from_lat, from_lon, to_lat, to_lon, apply_traffic) dict
        -dijkstra(source, target) list
    }

    SnapshotService "1" --> "1..*" AdapterCallSpec
    AdapterCallSpec "1" --> "1" DataAdapter
    SnapshotService ..> AdapterCache : uses
    AdapterCache ..> Predictor : fallback to
    Predictor <|-- BikesPredictior
    Predictor <|-- BikesStationPredictor
    Predictor <|-- TrafficPredictor
    DublinRouter --> DublinNetworkParser
    TrafficPredictor ..> DublinNetworkParser : uses network data
```

---

## 4. Detailed System Behavioural Models

### 4.1 Sequence Diagram: GET /snapshot (Multi-Domain Request)

```mermaid
sequenceDiagram
    actor User as Browser / FE Dashboard
    participant FE as Frontend (overview.py)
    participant BE as Backend /snapshot
    participant SS as SnapshotService
    participant Cache as AdapterCache
    participant BikesAdp as BikesAdapter
    participant TrafficAdp as TrafficAdapter
    participant CityBikes as CityBikes API
    participant TomTom as TomTom API
    participant Pred as BikesPredictior

    User->>FE: GET /dashboard
    FE->>BE: GET /snapshot?include=bikes,traffic&lat=53.35&lon=-6.27
    BE->>SS: build_snapshot([BikesSpec, TrafficSpec], lat, lon)

    par Concurrent fetch via ThreadPoolExecutor
        SS->>Cache: fetch_with_fallback(BikesAdapter)
        Cache->>BikesAdp: fetch(location="dublin")
        BikesAdp->>CityBikes: GET /v2/networks/dublinbikes
        alt Live API success
            CityBikes-->>BikesAdp: Station JSON
            BikesAdp-->>Cache: BikeMetrics
            Cache-->>SS: (BikeMetrics, "live")
        else API failure
            CityBikes-->>BikesAdp: Error / Timeout
            Cache->>Cache: get("bikes")
            alt Cache hit
                Cache-->>SS: (CachedBikeMetrics, "cached")
            else Cache miss
                Cache->>Pred: predict(hour, day_of_week)
                Pred-->>Cache: BikeMetrics (predicted)
                Cache-->>SS: (BikeMetrics, "predicted")
            end
        end

    and
        SS->>Cache: fetch_with_fallback(TrafficAdapter)
        Cache->>TrafficAdp: fetch(radius_km=5.0)
        TrafficAdp->>TomTom: GET /traffic/services/5/incidentDetails
        alt Live API success
            TomTom-->>TrafficAdp: Incident JSON
            TrafficAdp-->>Cache: TrafficMetrics
            Cache-->>SS: (TrafficMetrics, "live")
        else API failure / no key
            Cache->>Cache: get("traffic")
            Cache-->>SS: (CachedTrafficMetrics, "cached")
        end
    end

    SS->>SS: merge(partial_snapshots) → MobilitySnapshot
    SS->>SS: run_analytics(snapshot)\n  - build_traffic_metrics()\n  - overall_air_quality_level()
    SS-->>BE: MobilitySnapshot {source_status:{bikes:"live", traffic:"cached"}}
    BE-->>FE: 200 OK + MobilitySnapshot JSON
    FE->>FE: Render Leaflet map markers\n+ Jinja2 template
    FE-->>User: Dashboard HTML
```

### 4.2 Sequence Diagram: POST /routing/calculate (Multi-Stop Route)

```mermaid
sequenceDiagram
    actor User as Browser (routing.html)
    participant FE as Frontend /dashboard/routing
    participant BE as Backend /routing/calculate
    participant RA as RoutesAdapter
    participant Geo as Google Geocoding API
    participant Routes as Google Routes API v2
    participant DubRtr as DublinRouter (fallback)

    User->>FE: Submit stops [A, B, C], mode=cycling, optimize=true
    FE->>BE: GET /routing/calculate?stops[]=A&stops[]=B&stops[]=C&optimize=true&mode=cycling

    BE->>RA: fetch(stops=["A","B","C"], optimize=True, mode="cycling")

    loop Geocode each stop
        RA->>Geo: GET /geocode/json?address=A
        Geo-->>RA: {lat, lon}
    end

    RA->>RA: tsp_optimize(stops, locked=[]) → optimal_order=[A,C,B]

    RA->>Routes: POST /v2:computeRoutes\n{origin:A, destination:B, intermediates:[C], travelMode:BICYCLE}
    alt Google Routes success
        Routes-->>RA: Route legs JSON (polylines, durations)
        RA-->>BE: RouteRecommendation {multi_stop_data, legs, duration, distance}
    else Google API unavailable / no key
        RA-->>BE: raise AdapterError
        BE->>DubRtr: route(from_lat, from_lon, to_lat, to_lon)
        DubRtr->>DubRtr: Dijkstra on DCC.net.xml\napply traffic weights
        DubRtr-->>BE: local route dict
        BE-->>BE: wrap as RouteRecommendation
    end

    BE-->>FE: 200 OK + RouteRecommendation JSON
    FE->>FE: Draw polyline on Leaflet map\nShow leg durations + distances
    FE-->>User: Route displayed
```

### 4.3 Sequence Diagram: User Login

```mermaid
sequenceDiagram
    actor User as Browser
    participant FE as Frontend /login
    participant FEAuth as Frontend auth.py
    participant BE as Backend /auth/login
    participant UsersJSON as users.json

    User->>FE: GET /login
    FE-->>User: Login form (login.html)

    User->>FEAuth: POST /login {username, password}
    FEAuth->>BE: POST /auth/login {username, password}
    BE->>UsersJSON: load users
    BE->>BE: check_password_hash(stored_hash, password)
    alt Valid credentials
        BE-->>FEAuth: 200 {role: "admin" | "user"}
        FEAuth->>FEAuth: session["user"] = username\nsession["role"] = role
        FEAuth-->>User: 302 Redirect /dashboard
    else Invalid credentials
        BE-->>FEAuth: 401 Unauthorized
        FEAuth-->>User: Login form + error message
    end
```

### 4.4 State Diagram: Adapter Data Freshness

```mermaid
stateDiagram-v2
    [*] --> Idle

    Idle --> Fetching : API request received

    Fetching --> Live : External API call succeeds
    Fetching --> CacheLookup : External API call fails / timeout

    Live --> Cached : Write result to in-memory cache
    Cached --> [*] : Return data (source_status = "live")

    CacheLookup --> CacheHit : Cache entry found and not expired
    CacheLookup --> CacheMiss : Cache entry absent or expired

    CacheHit --> [*] : Return data (source_status = "cached")

    CacheMiss --> Predicting : Predictor available
    CacheMiss --> Failed : No predictor configured

    Predicting --> [*] : Return data (source_status = "predicted")
    Failed --> [*] : Return null (source_status = "failed")
```

### 4.5 State Diagram: User Session

```mermaid
stateDiagram-v2
    [*] --> Unauthenticated

    Unauthenticated --> Authenticating : Visit /login, submit credentials
    Authenticating --> Authenticated : Valid credentials (role=user/admin)
    Authenticating --> Unauthenticated : Invalid credentials (401)

    Authenticated --> ViewingDashboard : GET /dashboard
    Authenticated --> ViewingAnalytics : GET /dashboard/analytics
    Authenticated --> PlanningRoute : GET /dashboard/routing
    Authenticated --> ViewingRecs : GET /dashboard/recommendations

    ViewingDashboard --> Authenticated : Navigate
    ViewingAnalytics --> Authenticated : Navigate
    PlanningRoute --> Authenticated : Navigate
    ViewingRecs --> Authenticated : Navigate

    Authenticated --> AdminPanel : GET /users (role=admin only)
    AdminPanel --> Authenticated : Navigate

    Authenticated --> Unauthenticated : POST /logout (session cleared)
    Unauthenticated --> [*]
```

---

## 5. Project Diary

### 5.1 Project Approach

The project followed a **Kanban-style agile workflow** tracked on a JIRA board (`KAN-*` ticket numbering). Development was organised into feature branches (one branch per JIRA ticket), with squash-merge pull requests into `main`. All PRs required at least one code review before merging.

Code quality was enforced automatically via pre-commit hooks (Black autoformatter + pycodestyle PEP8 checks), GitHub Actions CI on every PR, and a smoke test suite (`smoke_test.ps1`).

The architecture was designed around the **Adapter Pattern**: each external data source is encapsulated behind a `DataAdapter` interface, allowing independent development, mocking, and testing of each integration. A unified `MobilitySnapshot` model allowed all domain teams to work in parallel without blocking each other.

### 5.2 Labour Division

| Team Member | Primary Responsibilities |
|---|---|
| **Darragh Hassett** | GTFS bus adapter, bus analytics, cloud deployment (GKE, Cloud Build, Kubernetes), snapshot service wiring, auth |
| **Oisin Power** | Dublin Network module (SUMO routing, traffic prediction), ML bike model, frontend overview/analytics, bug fixes |
| **Ciarán O'Malley** | Traffic adapter, air quality adapter, analytics layer, API contract validation |
| **Parker Kavanagh** | Routes adapter (Google Maps, TSP optimisation), routing frontend, efficiency endpoint |
| **Aoife Walshe** | Tour adapter, bike adapter & analytics, recommendations, fallback caching, ML integration |

### 5.3 Time Estimates vs Actual Time

| Ticket | Feature | Estimated | Actual | Notes |
|---|---|---|---|---|
| KAN-41/43/46 | Core adapters (bikes, traffic, airquality, tour) | 3 days | 4 days | External API shape differences required model rework |
| KAN-52/53/54 | SnapshotService + GKE cluster deployment | 2 days | 4 days | Cloud Build + Kubernetes config took significant iteration |
| KAN-55/58 | Flask blueprint wiring, health endpoint | 1 day | 1 day | On target |
| KAN-59/61 | FastAPI → Flask migration, caching layer | 1.5 days | 2 days | Framework change required re-testing all endpoints |
| KAN-62 | Module path standardisation (import fixes) | 0.5 days | 1 day | Cloud Run import resolution was non-trivial |
| KAN-66/67 | Frontend Flask app + Jinja2 dashboard | 3 days | 5 days | Leaflet map integration and Jinja2 data wiring more complex than expected |
| KAN-71 | SUMO offline routing (Dublin Network module) | 3 days | 4 days | DCC.net.xml coordinate conversion and Dijkstra tuning |
| KAN-73 | Bikes ML model (RandomForest + weather) | 2 days | 2.5 days | Feature engineering for weather slightly underestimated |
| KAN-75 | Bus analytics (GTFS wait times, importance) | 2 days | 3 days | GTFS file filtering and cache invalidation took extra time |
| KAN-76 | Recommendations + optimisations | 1.5 days | 1.5 days | On target |
| KAN-78 | Efficiency routing mechanism | 1.5 days | 2 days | Integration with Google Routes required extra auth handling |
| KAN-82/83/84 | Bug fixes, test coverage 84% → 91%, executable | 2 days | 2.5 days | Edge cases in SUMO coordinate conversion |
| User Login (KAN) | Auth module (login, user management) | 1 day | 1.5 days | Session management + admin role checking |

**Total estimated:** ~25 days (team-aggregate)  
**Total actual:** ~34 days (team-aggregate)

### 5.4 Impact of and Response to Inaccurate Estimates

**Cloud deployment complexity (KAN-52/53):** GKE deployment took twice as long as estimated. The team had underestimated the iteration cycles needed for Kubernetes manifest tuning, image naming, and Cloud Build pipeline configuration. In response, a dedicated `cloudbuild.yaml` and separate `k8s/` directory were established with clear ownership (Darragh), preventing others from being blocked.

**Frontend (KAN-66/67):** The Jinja2 dashboard took 5 days vs 3 estimated. Leaflet.js marker rendering with live API data, template component decomposition, and session-aware navigation were each more involved than anticipated. The response was to scope the frontend to server-side rendering only (no React/SPA), which reduced complexity and allowed faster iteration, at the cost of some interactivity.

**SUMO routing (KAN-71):** The SUMO coordinate conversion from local SUMO space to WGS-84 required careful derivation of the linear interpolation formula from the `DCC.net.xml` `convBoundary` and `origBoundary` attributes. This was not anticipated at planning time and added roughly a day of work.

**Module import paths (KAN-62):** Cloud Run's Python path resolution differed from local development. The fix (standardising all imports to relative package paths and ensuring correct working directory) was straightforward but took a full day of diagnosis. This led to the addition of a `localStart.ps1` script to enforce consistent startup conditions.

**Estimation pattern:** Across the project, infrastructure/integration tasks were consistently underestimated by ~50%, while pure Python feature work was estimated accurately. Future iterations would allocate a 1.5× buffer for any task involving external API integration, cloud deployment, or cross-service wiring.

---

## 6. Compile and Deployment Instructions

### 6.1 Prerequisites

- Python 3.12+
- Git
- (Optional) Docker
- (Optional) Google Cloud SDK (`gcloud`) for GKE deployment
- API keys: `TOMTOM_API_KEY`, `GOOGLE_MAPS_API_KEY` (set as environment variables)

### 6.2 Local Development Setup

#### Clone the repository

```bash
git clone https://github.com/CS7CS3-Group-9/CS7CS3-ASE-Group9.git
cd CS7CS3-ASE-Group9
```

#### Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

#### Install frontend dependencies

```bash
pip install -r frontend/requirements.txt
```

#### One-time pre-commit setup (for contributors)

```bash
pip install pre-commit pycodestyle
python -m pre_commit install
```

### 6.3 Running the Backend API

From the repository root:

```bash
# Minimal local run (no Firestore, no paid APIs)
export ENABLE_FIRESTORE=false
python -m flask --app backend.app:create_app --debug run --port 5000
```

With optional API keys:

```bash
export TOMTOM_API_KEY=your_key_here
export GOOGLE_MAPS_API_KEY=your_key_here
export ENABLE_FIRESTORE=false
python -m flask --app backend.app:create_app --debug run --port 5000
```

With ML bike prediction:

```bash
export BIKES_MODEL_PATH=backend/ml/artifacts/bikes_model.joblib
export WEATHER_FORECAST_PATH=data/historical/weather_forecast.csv
python -m flask --app backend.app:create_app --debug run --port 5000
```

Windows (PowerShell via `localStart.ps1`):

```powershell
.\localStart.ps1
```

Backend is available at: `http://127.0.0.1:5000`

### 6.4 Running the Frontend Dashboard

```bash
export BACKEND_API_URL=http://localhost:5000
export FLASK_DEBUG=true
python -m flask --app frontend.app:create_app --debug run --port 8080
```

Dashboard is available at: `http://127.0.0.1:8080`

### 6.5 Running Tests

#### Backend unit and integration tests

```bash
pytest backend/ -v
```

#### Dublin Network module tests (82 tests)

```bash
pytest backend/dublin_network/tests/ -v
```

#### All tests with coverage report

```bash
pytest backend/ --cov=backend --cov-report=term-missing
```

#### Smoke tests (requires running API)

```powershell
.\smoke_test.ps1
# or
powershell -ExecutionPolicy Bypass -File .\smoke_test.ps1
```

### 6.6 Training the Bikes ML Model

```bash
python backend/ml/train_bikes_model.py \
  --input data/historical/dublin-bikes_station_status_042025.csv \
  --weather data/historical/weather_forecast.csv
```

The trained artifact is saved to `backend/ml/artifacts/bikes_model.joblib`.

### 6.7 Docker Build

#### Backend

```bash
docker build -t sustainable-city-backend ./backend
docker run -p 5000:5000 \
  -e ENABLE_FIRESTORE=false \
  -e TOMTOM_API_KEY=your_key \
  -e GOOGLE_MAPS_API_KEY=your_key \
  sustainable-city-backend
```

#### Frontend

```bash
docker build -t sustainable-city-frontend ./frontend
docker run -p 8080:8080 \
  -e BACKEND_API_URL=http://host.docker.internal:5000 \
  sustainable-city-frontend
```

### 6.8 GKE / Cloud Deployment

Deployment is automated via Cloud Build on push to `main`:

```bash
gcloud builds submit --config cloudbuild.yaml
```

Kubernetes manifests are in `k8s/`. To apply manually:

```bash
kubectl apply -f k8s/backend-deployment.yaml
```

### 6.9 Key Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TOMTOM_API_KEY` | No | — | TomTom Traffic Incidents API key |
| `GOOGLE_MAPS_API_KEY` | No | — | Google Geocoding + Routes API key |
| `ENABLE_FIRESTORE` | No | `false` | Enable Firestore cache persistence |
| `BIKES_MODEL_PATH` | No | — | Path to trained bikes joblib artifact |
| `FORCE_BIKES_PREDICTION` | No | `0` | `1` to skip live API, use ML only |
| `WEATHER_FORECAST_PATH` | No | — | CSV with weather features for ML |
| `WEATHER_AUTO_REFRESH` | No | `true` | Auto-refresh weather forecast cache |
| `WEATHER_REFRESH_HOURS` | No | `24` | Hours between weather cache refreshes |
| `BACKEND_API_URL` | Yes (FE) | — | Frontend → Backend base URL |
| `SECRET_KEY` | No | random | Flask session secret key |
| `FLASK_DEBUG` | No | `false` | Enable Flask debug mode |
| `REFRESH_INTERVAL` | No | `60` | Dashboard auto-refresh interval (seconds) |

### 6.10 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health + adapter status |
| GET | `/snapshot` | Multi-domain unified snapshot |
| GET | `/bikes` | Real-time bike availability |
| GET | `/bikes/stations` | Per-station bike data |
| GET | `/traffic` | Live traffic incidents |
| GET | `/airquality` | Air quality + pollutant levels |
| GET | `/buses/stops` | Bus stops + GTFS wait times |
| GET | `/tours` | Tourism attractions |
| GET | `/routing/calculate` | Multi-stop route planning |
| GET | `/efficiency` | Transport emissions calculations |
| POST | `/auth/login` | Authenticate user |
| GET | `/auth/users` | List users (admin) |
| POST | `/auth/users` | Create user (admin) |
| POST | `/auth/users/delete` | Delete user (admin) |
