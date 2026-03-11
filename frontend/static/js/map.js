/* Leaflet.js map initialisation and marker management */
/* global L */

(function () {
  "use strict";

  var DUBLIN = [53.3498, -6.2603];
  var REFRESH_INTERVAL = window.REFRESH_INTERVAL || 60000;

  var map = L.map("map").setView(DUBLIN, 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  /* ---- Layer groups ---- */
  var bikeLayer    = L.layerGroup().addTo(map);
  var trafficLayer = L.layerGroup().addTo(map);
  var tourismLayer = L.layerGroup().addTo(map);
  var busLayer     = L.layerGroup().addTo(map);

  function _toRad(deg) {
    return deg * Math.PI / 180;
  }

  function _distanceKm(aLat, aLon, bLat, bLon) {
    var r = 6371;
    var dLat = _toRad(bLat - aLat);
    var dLon = _toRad(bLon - aLon);
    var lat1 = _toRad(aLat);
    var lat2 = _toRad(bLat);
    var sin1 = Math.sin(dLat / 2);
    var sin2 = Math.sin(dLon / 2);
    var h = sin1 * sin1 + Math.cos(lat1) * Math.cos(lat2) * sin2 * sin2;
    return 2 * r * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function _withinRadiusKm(lat, lon, radiusKm) {
    if (!radiusKm) return true;
    return _distanceKm(DUBLIN[0], DUBLIN[1], lat, lon) <= radiusKm;
  }

  /* ---- Bike emoji icon ---- */
  var _bikeIcon = L.divIcon({
    html: "<div style='font-size:18px;line-height:1'>\uD83D\uDEB2</div>",
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  /* ---- Populate bike layer ---- */
  function populateBikes(stations) {
    bikeLayer.clearLayers();
    if (!stations || !stations.length) return;
    var radiusKm = window.getDashboardRadiusKm ? Number(window.getDashboardRadiusKm()) : null;
    stations.forEach(function (s) {
      if (!_withinRadiusKm(s.lat, s.lon, radiusKm)) return;
      var marker = L.marker([s.lat, s.lon], { icon: _bikeIcon });
      marker.bindPopup(
        "<strong>" + s.name + "</strong><br>" +
        "<span style='color:#16a34a'>" + s.free_bikes + " bikes</span> &nbsp;|&nbsp; " +
        "<span style='color:#2563eb'>" + s.empty_slots + " docks</span>"
      );
      bikeLayer.addLayer(marker);
    });
  }

  /* ---- Traffic incident colour by severity ---- */
  var _severityColour = {
    "major":     "#dc2626",
    "moderate":  "#d97706",
    "minor":     "#fbbf24",
    "undefined": "#9333ea",
    "unknown":   "#6b7280",
  };

  /* ---- Traffic incident colour by category (overrides severity for closures) ---- */
  var _categoryColour = {
    "road closed": "#7c3aed",
    "accident":    "#dc2626",
  };

  function _incidentColour(inc) {
    var cat = (inc.category || "").toLowerCase();
    if (_categoryColour[cat]) return _categoryColour[cat];
    return _severityColour[(inc.severity || "").toLowerCase()] || "#6b7280";
  }

  /* ---- Populate traffic layer — one marker per incident on the actual road ---- */
  function populateTraffic(traffic) {
    trafficLayer.clearLayers();
    if (!traffic) return;

    var incidents = traffic.incidents || [];
    var placed = 0;

    incidents.forEach(function (inc) {
      if (inc.latitude == null || inc.longitude == null) return;

      var colour = _incidentColour(inc);
      var label = inc.category || "Incident";

      var icon = L.divIcon({
        html: "<div style='" +
              "background:" + colour + ";" +
              "color:#fff;border-radius:4px;padding:2px 6px;" +
              "font-size:11px;font-weight:700;white-space:nowrap;" +
              "box-shadow:0 1px 3px rgba(0,0,0,.4);line-height:1.4'" +
              ">" + label + "</div>",
        className: "",
        iconAnchor: [0, 8],
      });

      var delayStr = inc.delay_minutes
        ? " &mdash; " + inc.delay_minutes + " min delay"
        : "";

      L.marker([inc.latitude, inc.longitude], { icon: icon })
        .bindPopup(
          "<strong>" + (inc.category || "Incident") + "</strong>" + delayStr + "<br>" +
          (inc.road && inc.road !== "Unknown road" ? "Road: <b>" + inc.road + "</b><br>" : "") +
          (inc.from_location ? "From: " + inc.from_location + "<br>" : "") +
          (inc.to_location   ? "To: "   + inc.to_location   + "<br>" : "") +
          "Severity: <b>" + (inc.severity || "—") + "</b><br>" +
          (inc.description && inc.description !== "No description"
            ? "<em>" + inc.description + "</em>" : "")
        )
        .addTo(trafficLayer);
      placed++;
    });

    /* If no incidents have coordinates (e.g. flat/test data), fall back to a
       single summary badge at Dublin centre so the layer isn't empty. */
    if (placed === 0 && traffic.total_incidents > 0) {
      var cong = (traffic.congestion_level || "low").toLowerCase();
      var summaryColour = cong === "high" ? "#dc2626" : cong === "medium" ? "#d97706" : "#16a34a";
      var summaryIcon = L.divIcon({
        html: "<div style='background:" + summaryColour + ";color:#fff;border-radius:6px;" +
              "padding:3px 8px;font-size:12px;font-weight:700;white-space:nowrap;" +
              "box-shadow:0 1px 4px rgba(0,0,0,.3)'>" +
              cong.charAt(0).toUpperCase() + cong.slice(1) +
              " &mdash; " + traffic.total_incidents + " incidents</div>",
        className: "",
        iconAnchor: [60, 12],
      });
      L.marker(DUBLIN, { icon: summaryIcon })
        .bindPopup(
          "<strong>Traffic Summary</strong><br>" +
          "Congestion: <b>" + (traffic.congestion_level || "—") + "</b><br>" +
          "Incidents: <b>" + (traffic.total_incidents || 0) + "</b>"
        )
        .addTo(trafficLayer);
    }
  }

  /* ---- Populate tourism layer ---- */
  var _tourismIcon = L.divIcon({
    html: "<div style='font-size:18px;line-height:1'>\uD83C\uDFA1</div>",
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  function populateTourism(tours) {
    tourismLayer.clearLayers();
    if (!tours || !tours.attractions) return;
    tours.attractions.forEach(function (a) {
      if (a.latitude == null || a.longitude == null) return;
      var marker = L.marker([a.latitude, a.longitude], { icon: _tourismIcon });
      marker.bindPopup(
        "<strong>" + (a.attraction_name || "Attraction") + "</strong><br>" +
        "<em>" + (a.attraction_type || "").replace(/_/g, " ") + "</em>"
      );
      tourismLayer.addLayer(marker);
    });
  }

  /* ---- Populate bus layer ---- */
  var _busIcon = L.divIcon({
    html: "<div style='font-size:18px;line-height:1'>\uD83D\uDE8C</div>",
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  function populateBuses(stops) {
    busLayer.clearLayers();
    if (!stops || !stops.length) return;
    var radiusKm = window.getDashboardRadiusKm ? Number(window.getDashboardRadiusKm()) : null;
    stops.forEach(function (s) {
      if (!_withinRadiusKm(s.lat, s.lon, radiusKm)) return;
      var popup =
        "<strong>" + s.name + "</strong>" +
        (s.ref ? " <span style='color:#6b7280'>#" + s.ref + "</span>" : "") +
        (s.routes ? "<br><em>" + s.routes + "</em>" : "");
      L.marker([s.lat, s.lon], { icon: _busIcon })
        .bindPopup(popup)
        .addTo(busLayer);
    });
  }

  /* ---- Fetch data and refresh all layers ---- */
  function refreshMap(data) {
    populateBikes(data.bike_stations || []);
    populateTraffic(data.traffic || null);
    populateTourism(data.tours || null);
    populateBuses(data.bus_stops || []);
  }

  function fetchAndRefresh() {
    var radiusKm = window.getDashboardRadiusKm ? window.getDashboardRadiusKm() : null;
    var url = radiusKm ? "/dashboard/data?radius_km=" + encodeURIComponent(radiusKm) : "/dashboard/data";
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(refreshMap)
      .catch(function () {});
  }

  /* ---- Layer toggle controls ---- */
  function wireToggle(id, layer) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", function () {
      if (el.checked) {
        map.addLayer(layer);
      } else {
        map.removeLayer(layer);
      }
    });
  }

  wireToggle("toggle-bikes",   bikeLayer);
  wireToggle("toggle-traffic", trafficLayer);
  wireToggle("toggle-tourism", tourismLayer);
  wireToggle("toggle-buses",   busLayer);

  /* ---- Boot ---- */
  fetchAndRefresh();
  setInterval(fetchAndRefresh, REFRESH_INTERVAL);

  /* Expose so dashboard.js can trigger a map refresh after KPI update */
  window._mapRefresh = refreshMap;

  /* Expose map instance for desktop app tile-layer swap (desktop-overlay.js) */
  window._leafletMap = map;
})();
