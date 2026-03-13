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
  function _makeClusterIcon(cluster, style) {
    var count = cluster.getChildCount();
    var size = count < 10 ? 30 : count < 100 ? 38 : 46;
    var radius = style && style.shape === "circle" ? "50%" : (style && style.radius ? style.radius : "0");
    var colour = style && style.colour ? style.colour : "#334155";
    var border = style && style.border ? style.border : "2px solid rgba(255,255,255,.8)";
    return L.divIcon({
      html:
        "<div style='background:" + colour + ";width:" + size + "px;height:" + size +
        "px;line-height:" + size + "px;border-radius:" + radius + ";border:" + border +
        ";color:#fff;text-align:center;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.35)'>" +
        count + "</div>",
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  }

  function _createMarkerLayer(useCluster, clusterStyle) {
    if (useCluster && typeof L.markerClusterGroup === "function") {
      var options = {
        chunkedLoading: true,
        chunkInterval: 200,
        chunkDelay: 50,
        maxClusterRadius: 50,
        removeOutsideVisibleBounds: true,
        animateAddingMarkers: false,
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: false,
      };
      if (clusterStyle) {
        options.iconCreateFunction = function (cluster) {
          return _makeClusterIcon(cluster, clusterStyle);
        };
      }
      return L.markerClusterGroup(options);
    }
    return L.layerGroup();
  }

  function _addMarkers(layer, markers) {
    if (!markers || !markers.length) return;
    if (typeof layer.addLayers === "function") {
      layer.addLayers(markers);
      return;
    }
    markers.forEach(function (marker) {
      layer.addLayer(marker);
    });
  }

  var bikeLayer = _createMarkerLayer(true, { shape: "circle", colour: "#16a34a" }).addTo(map);
  var trafficLayer = _createMarkerLayer(false).addTo(map);
  var tourismLayer = _createMarkerLayer(true).addTo(map);
  var busLayer = _createMarkerLayer(true, { shape: "square", colour: "#2563eb" }).addTo(map);
  var needsBusLayer = _createMarkerLayer(false).addTo(map);
  var needsBikeLayer = _createMarkerLayer(false).addTo(map);

  var _lastData = null;
  var _lastRadius = null;
  var _lastRenderAt = {
    bikes: 0,
    buses: 0,
    tours: 0,
    traffic: 0,
    needs: 0,
  };
  var _staticLayerTtlMs = 5 * 60 * 1000;
  var _trafficTtlMs = 60 * 1000;

  function _inBounds(bounds, lat, lon) {
    if (!bounds) return true;
    return bounds.contains([lat, lon]);
  }

  function _emojiIcon(symbol, size) {
    return L.divIcon({
      html: "<div style='font-size:" + size + "px;line-height:1'>" + symbol + "</div>",
      className: "",
      iconSize: [size + 4, size + 4],
      iconAnchor: [(size + 4) / 2, (size + 4) / 2],
    });
  }

  /* ---- Bike emoji icon ---- */
  var _bikeIcon = _emojiIcon("\uD83D\uDEB2", 22);
  var _bikeDotIcon = _emojiIcon("\uD83D\uDEB2", 16);

  /* ---- Populate bike layer ---- */
  function populateBikes(stations) {
    bikeLayer.clearLayers();
    if (!stations || !stations.length) return;
    var bounds = map.getBounds();
    var fastMode = stations.length > 250;
    var markers = [];
    stations.forEach(function (s) {
      if (!_inBounds(bounds, s.lat, s.lon)) return;
      if (fastMode) {
        markers.push(L.marker([s.lat, s.lon], { icon: _bikeDotIcon }));
        return;
      }
      var marker = L.marker([s.lat, s.lon], { icon: _bikeIcon });
      marker.bindPopup(
        "<strong>" + s.name + "</strong><br>" +
        "<span style='color:#16a34a'>" + s.free_bikes + " bikes</span> &nbsp;|&nbsp; " +
        "<span style='color:#2563eb'>" + s.empty_slots + " docks</span>"
      );
      markers.push(marker);
    });
    _addMarkers(bikeLayer, markers);
  }

  /* ---- Traffic incident colour by severity ---- */
  var _severityColour = {
    "major": "#dc2626",
    "moderate": "#d97706",
    "minor": "#fbbf24",
    "undefined": "#9333ea",
    "unknown": "#6b7280",
  };

  /* ---- Traffic incident colour by category (overrides severity for closures) ---- */
  var _categoryColour = {
    "road closed": "#7c3aed",
    "accident": "#dc2626",
  };

  function _incidentColour(inc) {
    var cat = (inc.category || "").toLowerCase();
    if (_categoryColour[cat]) return _categoryColour[cat];
    return _severityColour[(inc.severity || "").toLowerCase()] || "#6b7280";
  }

  function _incidentEmoji(inc) {
    var cat = (inc.category || "").toLowerCase();
    if (cat.indexOf("road closed") >= 0 || cat.indexOf("closure") >= 0) return "\u26d4"; // ⛔
    if (cat.indexOf("accident") >= 0 || cat.indexOf("collision") >= 0) return "\ud83d\udca5"; // 💥
    if (cat.indexOf("breakdown") >= 0 || cat.indexOf("vehicle") >= 0) return "\ud83d\udd27"; // 🔧
    if (cat.indexOf("roadworks") >= 0 || cat.indexOf("works") >= 0) return "\ud83d\udea7"; // 🚧
    if (cat.indexOf("event") >= 0) return "\ud83c\udfab"; // 🎫
    if (cat.indexOf("flood") >= 0) return "\ud83c\udf0a"; // 🌊
    if (cat.indexOf("weather") >= 0 || cat.indexOf("storm") >= 0) return "\ud83c\udf27"; // 🌧
    var sev = (inc.severity || "").toLowerCase();
    if (sev === "major") return "\ud83d\udd34"; // 🔴
    if (sev === "moderate") return "\ud83d\udfe0"; // 🟠
    if (sev === "minor") return "\ud83d\udfe1"; // 🟡
    return "\u26a0\ufe0f"; // ⚠️
  }

  /* ---- Populate traffic layer — one marker per incident on the actual road ---- */
  function populateTraffic(traffic) {
    trafficLayer.clearLayers();
    if (!traffic) return;

    var incidents = traffic.incidents || [];
    var placed = 0;

    incidents.forEach(function (inc) {
      if (inc.latitude == null || inc.longitude == null) return;

      var label = inc.category || "Incident";

      var icon = L.divIcon({
        html: "<div style='font-size:22px;line-height:1'>"
          + _incidentEmoji(inc) + "</div>",
        className: "",
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      var delayStr = inc.delay_minutes
        ? " &mdash; " + inc.delay_minutes + " min delay"
        : "";

      L.marker([inc.latitude, inc.longitude], { icon: icon })
        .bindPopup(
          "<strong>" + (inc.category || "Incident") + "</strong>" + delayStr + "<br>" +
          (inc.road && inc.road !== "Unknown road" ? "Road: <b>" + inc.road + "</b><br>" : "") +
          (inc.from_location ? "From: " + inc.from_location + "<br>" : "") +
          (inc.to_location ? "To: " + inc.to_location + "<br>" : "") +
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
  var _tourismIcon = _emojiIcon("\uD83C\uDFA1", 22);
  var _tourismDotIcon = _emojiIcon("\uD83C\uDFA1", 16);

  function populateTourism(tours) {
    tourismLayer.clearLayers();
    if (!tours || !tours.attractions) return;
    var bounds = map.getBounds();
    var fastMode = tours.attractions.length > 300;
    var markers = [];
    tours.attractions.forEach(function (a) {
      if (a.latitude == null || a.longitude == null) return;
      if (!_inBounds(bounds, a.latitude, a.longitude)) return;
      var popup =
        "<strong>" + (a.attraction_name || "Attraction") + "</strong><br>" +
        "<em>" + (a.attraction_type || "").replace(/_/g, " ") + "</em>";
      if (fastMode) {
        markers.push(L.marker([a.latitude, a.longitude], { icon: _tourismDotIcon }).bindPopup(popup));
        return;
      }
      var marker = L.marker([a.latitude, a.longitude], { icon: _tourismIcon });
      marker.bindPopup(popup);
      markers.push(marker);
    });
    _addMarkers(tourismLayer, markers);
  }

  /* ---- Populate bus layer ---- */
  var _busIcon = _emojiIcon("\uD83D\uDE8C", 22);
  var _busDotIcon = _emojiIcon("\uD83D\uDE8C", 16);

  function populateBuses(stops) {
    busLayer.clearLayers();
    if (!stops || !stops.length) return;
    var bounds = map.getBounds();
    var fastMode = stops.length > 400;
    var markers = [];
    stops.forEach(function (s) {
      if (!_inBounds(bounds, s.lat, s.lon)) return;
      var popup =
        "<strong>" + s.name + "</strong>" +
        (s.ref ? " <span style='color:#6b7280'>#" + s.ref + "</span>" : "") +
        (s.routes ? "<br><em>" + s.routes + "</em>" : "");
      if (fastMode) {
        markers.push(L.marker([s.lat, s.lon], { icon: _busDotIcon }).bindPopup(popup));
        return;
      }
      var marker = L.marker([s.lat, s.lon], { icon: _busIcon }).bindPopup(popup);
      markers.push(marker);
    });
    _addMarkers(busLayer, markers);
  }

  function populateNeedsBus(areas) {
    needsBusLayer.clearLayers();
    if (!areas || !areas.length) return;
    areas.forEach(function (a) {
      if (a.lat == null || a.lon == null) return;
      var icon = L.divIcon({
        html: "<div style='background:#b91c1c;color:#fff;border-radius:50%;" +
          "width:22px;height:22px;line-height:22px;text-align:center;font-weight:700;" +
          "box-shadow:0 1px 4px rgba(0,0,0,.35)'>!</div>",
        className: "",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      L.marker([a.lat, a.lon], { icon: icon })
        .bindPopup(
          "<strong>" + (a.name || "Needs bus access") + "</strong><br>" +
          "Nearest bus stop: <b>" + Number(a.bus_km || 0).toFixed(1) + " km</b><br>" +
          "Action: add bus stop or extend a route."
        )
        .addTo(needsBusLayer);
    });
  }

  function populateNeedsBike(areas) {
    needsBikeLayer.clearLayers();
    if (!areas || !areas.length) return;
    areas.forEach(function (a) {
      if (a.lat == null || a.lon == null) return;
      var icon = L.divIcon({
        html: "<div style='background:#1d4ed8;color:#fff;border-radius:50%;" +
          "width:22px;height:22px;line-height:22px;text-align:center;font-weight:700;" +
          "box-shadow:0 1px 4px rgba(0,0,0,.35)'>B</div>",
        className: "",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      L.marker([a.lat, a.lon], { icon: icon })
        .bindPopup(
          "<strong>" + (a.name || "Needs bike access") + "</strong><br>" +
          "Nearest bike station: <b>" + Number(a.bike_km || 0).toFixed(1) + " km</b><br>" +
          "Action: add bike station nearby."
        )
        .addTo(needsBikeLayer);
    });
  }

  /* ---- Fetch data and refresh all layers ---- */
  function refreshMap(data) {
    if (!data) return;
    _lastData = data;
    var now = Date.now();
    var radiusKm = window.getDashboardRadiusKm ? Number(window.getDashboardRadiusKm()) : null;
    var radiusChanged = radiusKm !== _lastRadius;
    _lastRadius = radiusKm;

    if (map.hasLayer(bikeLayer)) {
      populateBikes(data.bike_stations || []);
      _lastRenderAt.bikes = now;
    }

    if (map.hasLayer(trafficLayer)) {
      if (radiusChanged || now - _lastRenderAt.traffic > _trafficTtlMs) {
        populateTraffic(data.traffic || null);
        _lastRenderAt.traffic = now;
      }
    }

    if (map.hasLayer(tourismLayer)) {
      if (radiusChanged || now - _lastRenderAt.tours > _staticLayerTtlMs) {
        populateTourism(data.tours || null);
        _lastRenderAt.tours = now;
      }
    }

    if (map.hasLayer(busLayer)) {
      if (radiusChanged || now - _lastRenderAt.buses > _staticLayerTtlMs) {
        populateBuses(data.bus_stops || []);
        _lastRenderAt.buses = now;
      }
    }

    if (map.hasLayer(needsBusLayer) || map.hasLayer(needsBikeLayer)) {
      if (radiusChanged || now - _lastRenderAt.needs > _staticLayerTtlMs) {
        populateNeedsBus(data.needs_bus_areas || []);
        populateNeedsBike(data.needs_bike_areas || []);
        _lastRenderAt.needs = now;
      }
    }
  }

  /* ---- Layer toggle controls ---- */
  function wireToggle(id, layer, onEnable) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", function () {
      if (el.checked) {
        map.addLayer(layer);
        if (onEnable && _lastData) {
          onEnable(_lastData);
        }
      } else {
        map.removeLayer(layer);
      }
    });
    if (!el.checked) {
      map.removeLayer(layer);
    } else if (!map.hasLayer(layer)) {
      map.addLayer(layer);
    }
  }

  wireToggle("toggle-bikes", bikeLayer, function (data) { populateBikes(data.bike_stations || []); });
  wireToggle("toggle-traffic", trafficLayer, function (data) { populateTraffic(data.traffic || null); });
  wireToggle("toggle-tourism", tourismLayer, function (data) { populateTourism(data.tours || null); });
  wireToggle("toggle-buses", busLayer, function (data) { populateBuses(data.bus_stops || []); });
  wireToggle("toggle-needs-bus", needsBusLayer, function (data) { populateNeedsBus(data.needs_bus_areas || []); });
  wireToggle("toggle-needs-bike", needsBikeLayer, function (data) { populateNeedsBike(data.needs_bike_areas || []); });

  /* ---- Boot ---- */
  /* Expose so dashboard.js can trigger a map refresh after KPI update */
  window._mapRefresh = refreshMap;
  window._mapLastData = function () { return _lastData; };
})();
