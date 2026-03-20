/**
 * desktop-overlay.js
 *
 * Injected by the Electron main process into every page after load.
 * Responsible for:
 *   1. Listening for connectivity change events from the main process
 *   2. Showing / hiding an offline status banner
 *   3. Intercepting fetch() calls when offline and returning SQLite cached data
 *   4. Swapping the Leaflet tile layer to an offline-capable version (leaflet.offline)
 *
 * This script does NOT import any modules — it runs in the existing page
 * context and communicates with the main process via window.electronAPI
 * (exposed by preload.js via contextBridge).
 */
(function () {
  'use strict';

  // Guard against double-injection on navigation
  if (window.__desktopOverlayLoaded) return;
  window.__desktopOverlayLoaded = true;

  // --------------------------------------------------------------------------
  // State
  // --------------------------------------------------------------------------
  var _offline = false;
  var _currentMode = null;
  var _cachedAt = null;
  var _origFetch = window.fetch.bind(window);
  var _unsubscribe = null;

  // Cache keys must match config/app.config.js cacheKeys
  var CACHE_KEYS = {
    snapshot:     'snapshot:dublin:5',
    bikeStations: 'bikes:stations',
    busStops:     'buses:stops',
    analytics:    'analytics:data',
  };

  // --------------------------------------------------------------------------
  // Banner UI
  // --------------------------------------------------------------------------
  var _banner = null;

  function _createBanner() {
    if (_banner) return;
    _banner = document.createElement('div');
    _banner.id = 'electron-offline-banner';
    Object.assign(_banner.style, {
      position:        'fixed',
      bottom:          '0',
      left:            '0',
      right:           '0',
      zIndex:          '99999',
      background:      '#b45309',
      color:           '#fff',
      padding:         '8px 16px',
      fontSize:        '13px',
      fontFamily:      'system-ui, sans-serif',
      display:         'flex',
      alignItems:      'center',
      justifyContent:  'space-between',
      gap:             '12px',
      boxShadow:       '0 -2px 4px rgba(0,0,0,0.3)',
    });

    var msgSpan = document.createElement('span');
    msgSpan.id = 'electron-offline-msg';

    var retryBtn = document.createElement('button');
    retryBtn.textContent = 'Retry';
    Object.assign(retryBtn.style, {
      background:   'rgba(255,255,255,0.2)',
      color:        '#fff',
      border:       '1px solid rgba(255,255,255,0.5)',
      borderRadius: '4px',
      padding:      '3px 10px',
      cursor:       'pointer',
      fontSize:     '12px',
    });
    retryBtn.addEventListener('click', function () {
      window.location.reload();
    });

    _banner.appendChild(msgSpan);
    _banner.appendChild(retryBtn);
    document.body.insertBefore(_banner, document.body.firstChild);
  }

  function _showBanner(cachedAt) {
    _createBanner();
    var timeStr = cachedAt ? new Date(cachedAt).toLocaleTimeString() : 'unknown';
    document.getElementById('electron-offline-msg').textContent =
      '\u26A0\uFE0F Offline \u2014 showing data cached at ' + timeStr +
      '. Map tiles require prior browsing to be available offline.';
    _banner.style.display = 'flex';
  }

  function _hideBanner() {
    if (_banner) _banner.style.display = 'none';
  }

  // --------------------------------------------------------------------------
  // Recommendations builder (mirrors Python overview.py _build_recommendations)
  // --------------------------------------------------------------------------
  function _buildRecommendations(bikes, traffic, airquality) {
    var recs = [];

    if (traffic) {
      var level = (traffic.congestion_level || 'low').toLowerCase();
      if (level === 'high') {
        recs.push({ title: 'High Traffic Congestion', description: 'Significant traffic delays detected. Consider public transport.', priority: 'High', source: 'traffic' });
      } else if (level === 'medium') {
        recs.push({ title: 'Moderate Traffic Congestion', description: 'Some congestion. Allow extra travel time if driving.', priority: 'Medium', source: 'traffic' });
      }
      var total = traffic.total_incidents || 0;
      if (total > 10) {
        recs.push({ title: total + ' Active Traffic Incidents', description: 'Multiple incidents reported. Check live traffic before travelling.', priority: 'Medium', source: 'traffic' });
      }
    }

    if (bikes) {
      var available = bikes.available_bikes || 0;
      if (available < 10) {
        recs.push({ title: 'Low Bike Availability', description: 'Only ' + available + ' bikes available. Consider alternative transport.', priority: 'High', source: 'bikes' });
      } else if (available > 100) {
        recs.push({ title: 'Good Bike Availability', description: available + ' bikes available across the city.', priority: 'Low', source: 'bikes' });
      }
    }

    if (airquality) {
      var aqi = airquality.aqi_value;
      if (aqi != null) {
        if (aqi > 100) {
          recs.push({ title: 'Poor Air Quality', description: 'AQI is ' + aqi + '. Sensitive groups should avoid prolonged outdoor activity.', priority: 'High', source: 'air_quality' });
        } else if (aqi > 50) {
          recs.push({ title: 'Moderate Air Quality', description: 'AQI is ' + aqi + '. Generally acceptable.', priority: 'Medium', source: 'air_quality' });
        }
      }
    }

    if (!recs.length) {
      recs.push({ title: 'Offline Mode', description: 'Showing cached city data. Live updates resume when connectivity is restored.', priority: 'Low', source: 'system' });
    }
    return recs;
  }

  // --------------------------------------------------------------------------
  // Build /dashboard/data response from SQLite cache
  // --------------------------------------------------------------------------
  async function _buildDashboardData() {
    var snapshotEntry    = await window.electronAPI.getCachedData(CACHE_KEYS.snapshot);
    var stationsEntry    = await window.electronAPI.getCachedData(CACHE_KEYS.bikeStations);
    var busStopsEntry    = await window.electronAPI.getCachedData(CACHE_KEYS.busStops);

    var snapshot     = snapshotEntry  ? JSON.parse(snapshotEntry.data_json)  : {};
    var bikeStations = stationsEntry  ? JSON.parse(stationsEntry.data_json)  : [];
    var busStops     = busStopsEntry  ? JSON.parse(busStopsEntry.data_json)  : [];

    // Rebuild aggregate bikes metric from station data (more accurate than snapshot)
    var bikes = null;
    if (bikeStations.length > 0) {
      bikes = {
        available_bikes:   bikeStations.reduce(function (s, x) { return s + (x.free_bikes  || 0); }, 0),
        available_docks:   bikeStations.reduce(function (s, x) { return s + (x.empty_slots || 0); }, 0),
        stations_reporting: bikeStations.length,
      };
    } else if (snapshot.bikes) {
      bikes = snapshot.bikes;
    }

    // Mark all source statuses as "cached"
    var sourceStatus = {};
    var orig = snapshot.source_status || {};
    Object.keys(orig).forEach(function (k) { sourceStatus[k] = 'cached'; });

    return {
      timestamp:     snapshot.timestamp || null,
      source_status: sourceStatus,
      bikes:         bikes,
      traffic:       snapshot.traffic    || null,
      airquality:    snapshot.airquality || null,
      tours:         snapshot.tours      || null,
      bike_stations: bikeStations,
      bus_stops:     busStops,
      recommendations: _buildRecommendations(bikes, snapshot.traffic, snapshot.airquality),
      error:         null,
    };
  }

  // --------------------------------------------------------------------------
  // Build /dashboard/analytics/data response from SQLite cache
  // --------------------------------------------------------------------------
  async function _buildAnalyticsData() {
    var entry = await window.electronAPI.getCachedData(CACHE_KEYS.analytics);
    if (entry) {
      return JSON.parse(entry.data_json);
    }
    // Fallback: derive from snapshot
    var snapshotEntry = await window.electronAPI.getCachedData(CACHE_KEYS.snapshot);
    var snapshot = snapshotEntry ? JSON.parse(snapshotEntry.data_json) : {};

    var aq = (snapshot.airquality || {});
    var pollutants = aq.pollutants || {};
    var aqKeys   = ['pm2_5', 'pm10', 'nitrogen_dioxide', 'carbon_monoxide', 'ozone', 'sulphur_dioxide'];
    var aqLabels = ['PM2.5', 'PM10', 'NO\u2082', 'CO', 'O\u2083', 'SO\u2082'];
    var aqValues = aqKeys.map(function (k) { return Math.round((pollutants[k] || 0) * 100) / 100; });

    var bikes = snapshot.bikes || {};
    var byCat = (snapshot.traffic || {}).incidents_by_category || {};
    var trafficLabels = Object.keys(byCat).length ? Object.keys(byCat) : ['No Incidents'];
    var trafficValues = Object.keys(byCat).length ? Object.values(byCat) : [0];

    return {
      air_quality_chart: { labels: aqLabels, values: aqValues },
      bike_chart: { labels: ['Available Bikes', 'Empty Docks', 'Stations Reporting'], values: [bikes.available_bikes || 0, bikes.available_docks || 0, bikes.stations_reporting || 0] },
      traffic_chart:     { labels: trafficLabels, values: trafficValues },
      timestamp:         snapshot.timestamp || null,
      error:             null,
    };
  }

  // --------------------------------------------------------------------------
  // Determine cache key / handler for a given URL
  // --------------------------------------------------------------------------
  function _getUrlType(url) {
    var pathname = String(url).split('?')[0].replace(/^https?:\/\/[^/]+/, '');
    if (pathname === '/dashboard/data')          return 'dashboard';
    if (pathname === '/dashboard/analytics/data') return 'analytics';
    if (pathname === '/buses/stops')             return 'busStops';
    if (pathname === '/bikes/stations')          return 'bikeStations';
    return null;
  }

  // --------------------------------------------------------------------------
  // Cache seed — populate the current page with cached data immediately,
  // so the user sees something useful before the real fetch completes.
  // --------------------------------------------------------------------------
  async function _initCacheSeed() {
    var onDashboard      = document.getElementById('kpi-bikes') !== null;
    var onAnalytics      = document.getElementById('airQualityChart') !== null;
    var onRecommendations = document.getElementById('rec-cards-container') !== null && !onDashboard;

    if (onDashboard) {
      var data = await _buildDashboardData();
      if (!data.bikes && !data.traffic && !data.airquality) return; // cache empty

      var setKpi = function (id, value) {
        var el = document.getElementById(id);
        if (el && value != null) el.textContent = value;
      };
      if (data.bikes) {
        setKpi('kpi-bikes', data.bikes.available_bikes);
      }
      if (data.traffic) {
        var cong = data.traffic.congestion_level || '';
        setKpi('kpi-traffic', cong.charAt(0).toUpperCase() + cong.slice(1));
        setKpi('kpi-incidents', data.traffic.total_incidents);
      }
      if (data.airquality) {
        var aqi = data.airquality.aqi_value;
        setKpi('kpi-aqi', aqi != null ? Math.round(aqi * 10) / 10 : '\u2014');
      }
      if (data.tours) {
        setKpi('kpi-tours', data.tours.total_attractions);
      }
      if (data.timestamp) {
        var tsEl = document.getElementById('last-updated');
        if (tsEl) tsEl.textContent = 'Updated: ' + new Date(data.timestamp).toLocaleTimeString();
      }
      if (window._mapRefresh) window._mapRefresh(data);
      if (window._recStripRefresh) window._recStripRefresh(data.recommendations);
    }

    if (onAnalytics && window.initCharts) {
      var analyticsData = await _buildAnalyticsData();
      if (analyticsData && analyticsData.air_quality_chart) {
        window.initCharts(analyticsData);
      }
    }

    if (onRecommendations) {
      var dashData = await _buildDashboardData();
      if (dashData.bikes || dashData.traffic || dashData.airquality) {
        if (window._recPageRender) {
          window._recPageRender(dashData.recommendations, dashData.timestamp, null);
        }
      }
    }
  }

  // --------------------------------------------------------------------------
  // Fetch interceptor
  // --------------------------------------------------------------------------
  window.fetch = async function (url, options) {
    if (!_offline) return _origFetch(url, options);

    var urlType = _getUrlType(url);
    if (!urlType) return _origFetch(url, options);

    var data = null;
    try {
      if (urlType === 'dashboard') {
        data = await _buildDashboardData();
      } else if (urlType === 'analytics') {
        data = await _buildAnalyticsData();
      } else if (urlType === 'busStops') {
        var entry = await window.electronAPI.getCachedData(CACHE_KEYS.busStops);
        data = entry ? JSON.parse(entry.data_json) : [];
      } else if (urlType === 'bikeStations') {
        var entry = await window.electronAPI.getCachedData(CACHE_KEYS.bikeStations);
        data = entry ? JSON.parse(entry.data_json) : [];
      }
    } catch (_) {
      // If cache lookup fails, fall through to the real fetch
    }

    if (data !== null) {
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return _origFetch(url, options);
  };

  // --------------------------------------------------------------------------
  // Leaflet tile layer swap (uses window._leafletMap set by map.js)
  // --------------------------------------------------------------------------
  function _swapTileLayer(map) {
    if (!window.L || !window.L.tileLayer || !window.L.tileLayer.offline) return;

    // Remove existing tile layers
    map.eachLayer(function (layer) {
      if (layer instanceof window.L.TileLayer) map.removeLayer(layer);
    });

    // Replace with offline-capable layer
    window.L.tileLayer.offline('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
      subdomains: 'abc',
    }).addTo(map);
  }

  function _initTileCaching() {
    // Wait for both the Leaflet map and leaflet.offline to be available
    if (window._leafletMap && window.L && window.L.tileLayer && window.L.tileLayer.offline) {
      _swapTileLayer(window._leafletMap);
      return;
    }
    // Retry for up to 10 seconds (page may still be initialising)
    var attempts = 0;
    var interval = setInterval(function () {
      attempts++;
      if (window._leafletMap && window.L && window.L.tileLayer && window.L.tileLayer.offline) {
        clearInterval(interval);
        _swapTileLayer(window._leafletMap);
      } else if (attempts >= 50) {
        clearInterval(interval); // give up after 10s
      }
    }, 200);
  }

  // --------------------------------------------------------------------------
  // Connectivity change handler
  // --------------------------------------------------------------------------
  function _onConnectivityChange(status) {
    var wasOffline  = _offline;
    var newMode     = status.mode || (status.online ? 'cloud' : 'offline');
    _offline        = newMode === 'offline';
    _cachedAt       = status.cachedAt || _cachedAt;
    var modeChanged = _currentMode !== null && _currentMode !== newMode;
    _currentMode    = newMode;

    if (_offline) {
      _showBanner(_cachedAt);
    } else {
      _hideBanner();
      // Refresh when recovering from offline OR when mode changes between online states
      if (wasOffline || modeChanged) {
        if (typeof window._dashboardRefresh === 'function') window._dashboardRefresh();
        if (typeof window._analyticsRefresh === 'function') window._analyticsRefresh();
      }
    }
  }

  // --------------------------------------------------------------------------
  // Initialise
  // --------------------------------------------------------------------------

  // Subscribe to connectivity events from main process
  if (window.electronAPI) {
    _unsubscribe = window.electronAPI.onConnectivityChange(_onConnectivityChange);
    _initTileCaching();
    // Seed the page immediately with cached data so the user sees something
    // before the real network fetch completes (~10s).
    _initCacheSeed().catch(function () {});
  }

  // Clean up listeners if the page unloads (e.g. navigation within SPA)
  window.addEventListener('beforeunload', function () {
    if (_unsubscribe) _unsubscribe();
  });

}());
