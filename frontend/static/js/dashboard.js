/* Dashboard data fetching, KPI updates, and Chart.js initialisation */
/* global Chart */

(function () {
  "use strict";

  var REFRESH_INTERVAL = window.REFRESH_INTERVAL || 60000;
  var charts = {};
  var MAP_LOADING_MIN_MS = 350;
  var mapLoadingSince = 0;
  var mapLoadingTimer = null;

  function isVisible() {
    return document.visibilityState !== "hidden";
  }

  /* ---- KPI helpers ---- */

  function getRadiusKm() {
    var input = document.getElementById("radius-km");
    if (!input) return null;
    var value = Number(input.value);
    if (!Number.isFinite(value)) return null;
    if (value < 1) value = 1;
    if (value > 50) value = 50;
    input.value = Math.round(value);
    return input.value;
  }

  function dashboardDataUrl() {
    var radiusKm = getRadiusKm();
    return radiusKm ? "/dashboard/data?radius_km=" + encodeURIComponent(radiusKm) : "/dashboard/data";
  }

  function updateRadiusQueryParam() {
    var radiusKm = getRadiusKm();
    if (!radiusKm) return;
    var url = new URL(window.location.href);
    url.searchParams.set("radius_km", radiusKm);
    window.history.replaceState({}, "", url.toString());
  }

  function setKpi(id, value) {
    var el = document.getElementById(id);
    if (el && value != null) el.textContent = value;
  }

  function updateLastUpdated(ts) {
    var el = document.getElementById("last-updated");
    if (el && ts) {
      var d = new Date(ts);
      el.textContent = "Updated: " + d.toLocaleTimeString();
    }
  }

  function showErrorBanner(msg) {
    var existing = document.getElementById("js-error-banner");
    if (existing) return;
    var banner = document.createElement("div");
    banner.id = "js-error-banner";
    banner.className = "alert alert-warning";
    banner.textContent = "\u26A0 Could not refresh data: " + msg;
    var main = document.querySelector(".main-content");
    if (main) main.prepend(banner);
  }

  function clearErrorBanner() {
    var banner = document.getElementById("js-error-banner");
    if (banner) banner.remove();
  }

  function setMapLoading(isLoading) {
    var el = document.getElementById("map-loading");
    if (!el) return;
    if (isLoading) {
      if (mapLoadingTimer) {
        clearTimeout(mapLoadingTimer);
        mapLoadingTimer = null;
      }
      mapLoadingSince = Date.now();
      el.classList.add("is-visible");
    } else {
      var elapsed = Date.now() - mapLoadingSince;
      var delay = Math.max(0, MAP_LOADING_MIN_MS - elapsed);
      mapLoadingTimer = setTimeout(function () {
        el.classList.remove("is-visible");
        mapLoadingTimer = null;
      }, delay);
    }
  }

  /* ---- Fetch dashboard data and update KPIs ---- */

  function fetchDashboardData(showLoading) {
    if (!isVisible()) return;
    if (showLoading) setMapLoading(true);
    fetch(dashboardDataUrl())
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        clearErrorBanner();
        if (data.bikes) {
          setKpi("kpi-bikes", data.bikes.available_bikes);
        }
        if (data.traffic) {
          var cong = data.traffic.congestion_level || "";
          setKpi("kpi-traffic", cong.charAt(0).toUpperCase() + cong.slice(1));
          setKpi("kpi-incidents", data.traffic.total_incidents);
        }
        if (data.airquality) {
          var aqi = data.airquality.aqi_value;
          setKpi("kpi-aqi", aqi != null ? Math.round(aqi * 10) / 10 : "\u2014");
        }
        if (data.tours) {
          setKpi("kpi-tours", data.tours.total_attractions);
        }
        updateLastUpdated(data.timestamp);

        if (window._mapRefresh && typeof window._mapRefresh === "function") {
          window._mapRefresh(data);
        }
        if (window._recStripRefresh && typeof window._recStripRefresh === "function") {
          window._recStripRefresh(data.recommendations);
        }
      })
      .catch(function (err) {
        showErrorBanner(err.message);
      })
      .then(function () {
        if (showLoading) setMapLoading(false);
      });
  }

  /* ---- Chart.js initialisation ---- */

  function initCharts(data) {
    initBusHeatMap(data);
    initBikeHeatMap(data);
    if (typeof Chart === "undefined") return;

    var PALETTE = [
      "#2563eb","#16a34a","#d97706","#dc2626",
      "#9333ea","#0891b2","#ea580c","#65a30d"
    ];

    /* Air quality bar chart */
    var aqEl = document.getElementById("airQualityChart");
    if (aqEl && data.air_quality_chart) {
      var aqd = data.air_quality_chart;
      if (charts.airQuality) charts.airQuality.destroy();
      charts.airQuality = new Chart(aqEl, {
        type: "bar",
        data: {
          labels: aqd.labels,
          datasets: [{
            label: "Concentration",
            data: aqd.values,
            backgroundColor: PALETTE.slice(0, aqd.labels.length),
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "µg/m³" } } }
        }
      });
    }

    /* Bike bar chart */
    var bikeEl = document.getElementById("bikeChart");
    if (bikeEl && data.bike_chart) {
      var bkd = data.bike_chart;
      if (charts.bike) charts.bike.destroy();
      charts.bike = new Chart(bikeEl, {
        type: "bar",
        data: {
          labels: bkd.labels,
          datasets: [{
            label: "Count",
            data: bkd.values,
            backgroundColor: ["#16a34a", "#2563eb", "#9333ea"],
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    /* Traffic doughnut chart */
    var tfEl = document.getElementById("trafficChart");
    if (tfEl && data.traffic_chart) {
      var tfd = data.traffic_chart;
      if (charts.traffic) charts.traffic.destroy();
      charts.traffic = new Chart(tfEl, {
        type: "doughnut",
        data: {
          labels: tfd.labels,
          datasets: [{
            data: tfd.values,
            backgroundColor: PALETTE.slice(0, tfd.labels.length),
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { position: "bottom" } },
          cutout: "60%"
        }
      });
    }

    /* Buses per stop bar chart */
    var busEl = document.getElementById("busChart");
    if (busEl && data.bus_chart) {
      var bsd = data.bus_chart;
      if (charts.bus) charts.bus.destroy();
      charts.bus = new Chart(busEl, {
        type: "bar",
        data: {
          labels: bsd.labels,
          datasets: [{
            label: "Buses per stop",
            data: bsd.values,
            backgroundColor: PALETTE.slice(0, bsd.labels.length),
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "Buses" } } }
        }
      });
    }

    /* Best wait times bar chart */
    var bestEl = document.getElementById("busWaitBestChart");
    if (bestEl && data.bus_wait_best_chart) {
      var bbest = data.bus_wait_best_chart;
      if (charts.busWaitBest) charts.busWaitBest.destroy();
      charts.busWaitBest = new Chart(bestEl, {
        type: "bar",
        data: {
          labels: bbest.labels,
          datasets: [{
            label: "Best avg wait (min)",
            data: bbest.values,
            backgroundColor: "#16a34a",
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "Minutes" } } }
        }
      });
    }

    /* Worst wait times bar chart */
    var worstEl = document.getElementById("busWaitWorstChart");
    if (worstEl && data.bus_wait_worst_chart) {
      var bworst = data.bus_wait_worst_chart;
      if (charts.busWaitWorst) charts.busWaitWorst.destroy();
      charts.busWaitWorst = new Chart(worstEl, {
        type: "bar",
        data: {
          labels: bworst.labels,
          datasets: [{
            label: "Worst avg wait (min)",
            data: bworst.values,
            backgroundColor: "#dc2626",
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "Minutes" } } }
        }
      });
    }

    /* Importance histogram chart */
    var impHistEl = document.getElementById("busImportanceHistChart");
    if (impHistEl && data.bus_importance_hist_chart) {
      var imph = data.bus_importance_hist_chart;
      var _impHistLen = document.getElementById("imp-hist-len");
      if (_impHistLen) _impHistLen.textContent = String((imph.values || []).length);
      var _impHistSize = document.getElementById("imp-hist-size");
      if (_impHistSize) _impHistSize.textContent = impHistEl.width + "x" + impHistEl.height;
      if (charts.busImportanceHist) charts.busImportanceHist.destroy();
      charts.busImportanceHist = new Chart(impHistEl, {
        type: "bar",
        data: {
          labels: imph.labels,
          datasets: [{
            label: "Stops",
            data: imph.values,
            backgroundColor: "#0ea5e9",
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { title: { display: true, text: "Importance score bucket" } },
            y: { beginAtZero: true, title: { display: true, text: "Stops" } }
          }
        }
      });
    }

  }

  /* ---- Fetch and refresh charts ---- */

  function fetchAndUpdateCharts() {
    if (!isVisible()) return;
    fetch("/dashboard/analytics/data")
      .then(function (r) { return r.json(); })
      .then(function (data) { initCharts(data); })
      .catch(function () {});
  }

  /* ---- Analytics bus heat map ---- */
  var analyticsMap = null;
  var analyticsLayer = null;
  var analyticsBikeMap = null;
  var analyticsBikeLayer = null;

  function initBusHeatMap(data) {
    if (typeof L === "undefined") return;
    var el = document.getElementById("analytics-map");
    if (!el) return;

    if (!analyticsMap) {
      analyticsMap = L.map("analytics-map").setView([53.3498, -6.2603], 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(analyticsMap);
      analyticsLayer = L.layerGroup().addTo(analyticsMap);
    }

    var points = (data && data.bus_heatmap) ? data.bus_heatmap : [];
    analyticsLayer.clearLayers();
    if (!points.length) return;

    var max = points.reduce(function (m, p) { return p.count > m ? p.count : m; }, 0);
    points.forEach(function (p) {
      if (p.lat == null || p.lon == null) return;
      var ratio = max ? Math.sqrt(p.count / max) : 0;
      var radius = 4 + ratio * 12;
      var color = ratio >= 0.66 ? "#dc2626" : ratio >= 0.33 ? "#d97706" : "#16a34a";
      L.circleMarker([p.lat, p.lon], {
        radius: radius,
        color: color,
        fillColor: color,
        fillOpacity: 0.6,
        weight: 1,
      })
        .bindPopup("<strong>" + (p.name || "Bus Stop") + "</strong><br>Trips: <b>" + p.count + "</b>")
        .addTo(analyticsLayer);
    });
  }

  /* ---- Analytics bike availability heat map ---- */
  function initBikeHeatMap(data) {
    if (typeof L === "undefined") return;
    var el = document.getElementById("analytics-bike-map");
    if (!el) return;

    if (!analyticsBikeMap) {
      analyticsBikeMap = L.map("analytics-bike-map").setView([53.3498, -6.2603], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(analyticsBikeMap);
      analyticsBikeLayer = L.layerGroup().addTo(analyticsBikeMap);
    }

    var points = (data && data.bike_heatmap) ? data.bike_heatmap : [];
    analyticsBikeLayer.clearLayers();
    if (!points.length) return;

    points.forEach(function (p) {
      if (p.lat == null || p.lon == null) return;
      var availability = Number(p.availability);
      if (!Number.isFinite(availability)) return;
      var intensity = Math.max(0, Math.min(1, 1 - availability));
      var radius = 60 + intensity * 200;
      var opacity = 0.12 + intensity * 0.45;
      var color = "#16a34a";
      if (availability <= 0.2) {
        color = "#dc2626";
      } else if (availability <= 0.6) {
        color = "#f97316";
      }
      L.circle([p.lat, p.lon], {
        radius: radius,
        color: color,
        weight: 1,
        fillColor: color,
        fillOpacity: opacity,
      })
        .bindPopup(
          "<strong>" + (p.name || "Station") + "</strong><br>" +
          "Bikes: <b>" + Math.round(p.free_bikes || 0) + "</b> / " + Math.round(p.total || 0)
        )
        .addTo(analyticsBikeLayer);
    });
  }

  /* ---- Analytics filters ---- */
  function wireAnalyticsFilters() {
    var filters = Array.prototype.slice.call(document.querySelectorAll("[data-analytics-filter]"));
    if (!filters.length) return;

    function applyFilters() {
      var enabled = {};
      filters.forEach(function (f) { enabled[f.dataset.analyticsFilter] = f.checked; });
      var cards = document.querySelectorAll("[data-analytics-group]");
      cards.forEach(function (card) {
        var group = card.dataset.analyticsGroup;
        var show = enabled[group] !== false;
        card.style.display = show ? "" : "none";
      });
      if (analyticsMap) {
        setTimeout(function () { analyticsMap.invalidateSize(); }, 50);
      }
      if (analyticsBikeMap) {
        setTimeout(function () { analyticsBikeMap.invalidateSize(); }, 50);
      }
    }

    filters.forEach(function (f) { f.addEventListener("change", applyFilters); });
    applyFilters();
  }

  /* ---- Initialise on DOM ready ---- */

  function init() {
    var onDashboard = document.getElementById("kpi-bikes") !== null;
    var onAnalytics = document.getElementById("airQualityChart") !== null;
    var radiusInput = document.getElementById("radius-km");
    var radiusApply = document.getElementById("radius-apply");

    if (onDashboard) {
      fetchDashboardData(true);
      setInterval(fetchDashboardData, REFRESH_INTERVAL);
      window._dashboardRefresh = function () { fetchDashboardData(false); };
    }

    if (onAnalytics) {
      fetchAndUpdateCharts();
      setInterval(fetchAndUpdateCharts, REFRESH_INTERVAL);
      window._analyticsRefresh = fetchAndUpdateCharts;
      wireAnalyticsFilters();
    }

    if (radiusInput && radiusApply) {
      radiusApply.addEventListener("click", function () {
        updateRadiusQueryParam();
        fetchDashboardData(true);
      });
      radiusInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          updateRadiusQueryParam();
          fetchDashboardData(true);
        }
      });
    }

  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* Export for analytics page inline call */
  window.initCharts = initCharts;
  window.getDashboardRadiusKm = getRadiusKm;
})();
