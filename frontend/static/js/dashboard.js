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
  }

  /* ---- Fetch and refresh charts ---- */

  function fetchAndUpdateCharts() {
    if (!isVisible()) return;
    fetch("/dashboard/analytics/data")
      .then(function (r) { return r.json(); })
      .then(function (data) { initCharts(data); })
      .catch(function () {});
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
    }

    if (onAnalytics) {
      fetchAndUpdateCharts();
      setInterval(fetchAndUpdateCharts, REFRESH_INTERVAL);
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
