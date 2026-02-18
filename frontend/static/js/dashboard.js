/* Dashboard data fetching, KPI updates, and Chart.js initialisation */
/* global Chart */

(function () {
  "use strict";

  var REFRESH_INTERVAL = window.REFRESH_INTERVAL || 60000;
  var charts = {};

  /* ---- KPI helpers ---- */

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

  /* ---- Fetch dashboard data and update KPIs ---- */

  function fetchDashboardData() {
    fetch("/dashboard/data")
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
      })
      .catch(function (err) {
        showErrorBanner(err.message);
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
    fetch("/dashboard/analytics/data")
      .then(function (r) { return r.json(); })
      .then(function (data) { initCharts(data); })
      .catch(function () {});
  }

  /* ---- Initialise on DOM ready ---- */

  function init() {
    var onDashboard = document.getElementById("kpi-bikes") !== null;
    var onAnalytics = document.getElementById("airQualityChart") !== null;

    if (onDashboard) {
      fetchDashboardData();
      setInterval(fetchDashboardData, REFRESH_INTERVAL);
    }

    if (onAnalytics) {
      setInterval(fetchAndUpdateCharts, REFRESH_INTERVAL);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* Export for analytics page inline call */
  window.initCharts = initCharts;
})();
