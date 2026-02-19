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

  /* ---- Bike station colour by availability % ---- */
  function bikeColour(free, total) {
    if (!total) return "#6b7280";
    var pct = free / total;
    if (pct > 0.5) return "#16a34a";
    if (pct > 0.2) return "#d97706";
    return "#dc2626";
  }

  /* ---- Populate bike layer ---- */
  function populateBikes(stations) {
    bikeLayer.clearLayers();
    if (!stations || !stations.length) return;
    stations.forEach(function (s) {
      var colour = bikeColour(s.free_bikes, s.total);
      var marker = L.circleMarker([s.lat, s.lon], {
        radius: 8,
        fillColor: colour,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.85,
      });
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
  function populateTourism(tours) {
    tourismLayer.clearLayers();
    if (!tours || !tours.attractions) return;
    tours.attractions.forEach(function (a) {
      if (a.latitude == null || a.longitude == null) return;
      var marker = L.marker([a.latitude, a.longitude]);
      marker.bindPopup(
        "<strong>" + (a.attraction_name || "Attraction") + "</strong><br>" +
        "<em>" + (a.attraction_type || "").replace(/_/g, " ") + "</em>"
      );
      tourismLayer.addLayer(marker);
    });
  }

  /* ---- Populate bus layer ---- */
  var _busIcon = L.divIcon({
    html: "<div style='" +
          "background:#1d4ed8;color:#fff;border-radius:3px;" +
          "width:20px;height:20px;display:flex;align-items:center;" +
          "justify-content:center;font-size:11px;font-weight:700;" +
          "box-shadow:0 1px 3px rgba(0,0,0,.4)'>B</div>",
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  function populateBuses(stops) {
    busLayer.clearLayers();
    if (!stops || !stops.length) return;
    stops.forEach(function (s) {
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
    fetch("/dashboard/data")
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
})();
