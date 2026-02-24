/* Route Planner — Leaflet map + OSRM/Nominatim, multi-stop, per-stop locks, transit */
/* global L */

(function () {
  "use strict";

  /* ---- Map setup ---- */
  var DUBLIN = [53.3498, -6.2603];
  var map = L.map("routing-map").setView(DUBLIN, 12);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  var routeLayer  = L.layerGroup().addTo(map);
  var markerLayer = L.layerGroup().addTo(map);

  /* ---- State ---- */
  var currentMode = "driving";
  var currentType = "quickest";
  var stopCounter = 0;
  var stepsOpen   = false;

  /* ====================================================
     Lock button helpers
     ==================================================== */

  function isLocked(row) {
    return row.dataset.locked === "true";
  }

  function setLocked(row, locked) {
    row.dataset.locked = locked ? "true" : "false";
    var btn = row.querySelector(".btn-lock-stop");
    if (btn) updateLockBtn(btn, locked);
  }

  function updateLockBtn(btn, locked) {
    btn.textContent = locked ? "\uD83D\uDD12" : "\uD83D\uDD13";  // 🔒 / 🔓
    btn.title = locked
      ? "Locked \u2014 this stop stays in place (click to free)"
      : "Free \u2014 can be reordered (click to lock)";
    btn.classList.toggle("is-locked", locked);
  }

  function handleLockToggle(e) {
    var btn = e.currentTarget;
    var row = btn.closest(".stop-row");
    var nowLocked = !isLocked(row);
    setLocked(row, nowLocked);
  }

  /** Wire lock button on a row that has just been created. */
  function wireLockBtn(row) {
    var btn = row.querySelector(".btn-lock-stop");
    if (btn) btn.addEventListener("click", handleLockToggle);
  }

  // Wire lock buttons that already exist in the template (origin + destination rows)
  document.querySelectorAll(".btn-lock-stop").forEach(function (btn) {
    btn.addEventListener("click", handleLockToggle);
  });

  /* ====================================================
     Master optimise toggle
     ==================================================== */

  var optimizeToggle = document.getElementById("optimize-toggle");

  function applyOptimizeToggleUI() {
    var on = optimizeToggle.checked;
    document.querySelectorAll(".btn-lock-stop").forEach(function (btn) {
      btn.style.visibility = on ? "visible" : "hidden";
    });
    var hint = document.querySelector(".optimise-hint");
    if (hint) hint.style.opacity = on ? "1" : "0.35";
  }

  optimizeToggle.addEventListener("change", applyOptimizeToggleUI);
  applyOptimizeToggleUI();   // apply on load

  /* ====================================================
     Mode control
     ==================================================== */

  function updateTimeRowForMode() {
    var arrLabel = document.getElementById("time-arrive-label");
    if (!arrLabel) return;
    if (currentMode === "transit") {
      arrLabel.style.display = "";
    } else {
      arrLabel.style.display = "none";
      // If "Arrive by" was selected, reset to "Leave now"
      var arrRadio = arrLabel.querySelector("input[type='radio']");
      if (arrRadio && arrRadio.checked) {
        document.querySelector("input[name='time-type'][value='now']").checked = true;
        updateTimeInput();
      }
    }
  }

  function updateTimeInput() {
    var selected = document.querySelector("input[name='time-type']:checked");
    var input    = document.getElementById("time-input");
    if (!selected || !input) return;
    input.style.display = selected.value === "now" ? "none" : "block";
  }

  document.querySelectorAll("input[name='time-type']").forEach(function (radio) {
    radio.addEventListener("change", updateTimeInput);
  });

  document.querySelectorAll("#mode-control .seg-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("#mode-control .seg-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      currentMode = btn.dataset.value;
      var pr = document.getElementById("priority-row");
      if (pr) pr.style.display = currentMode === "transit" ? "none" : "";
      updateTimeRowForMode();
    });
  });

  // Initialise time row on load
  updateTimeRowForMode();

  /* ---- Route-type radio cards ---- */
  document.querySelectorAll("input[name='route-type']").forEach(function (radio) {
    radio.addEventListener("change", function () {
      currentType = radio.value;
      document.getElementById("type-quickest").classList.toggle("active", currentType === "quickest");
      document.getElementById("type-eco").classList.toggle("active", currentType === "eco");
    });
  });

  /* ====================================================
     Dynamic stop management
     ==================================================== */

  function allStopRows() {
    return Array.from(document.querySelectorAll("#stops-container .stop-row"));
  }

  function allStopInputs() {
    return Array.from(document.querySelectorAll("#stops-container .stop-input"));
  }

  /** Relabel A, B, C… dots after any add/remove */
  function relabelDots() {
    var rows  = allStopRows();
    var total = rows.length;
    rows.forEach(function (row, idx) {
      var dot = row.querySelector(".stop-dot");
      if (!dot) return;
      dot.textContent = String.fromCharCode(65 + idx);
      dot.className   = "stop-dot";
      if (idx === 0)              dot.classList.add("stop-dot-a");
      else if (idx === total - 1) dot.classList.add("stop-dot-b");
      else                        dot.classList.add("stop-dot-mid");
    });
  }

  function addIntermediateStop() {
    if (allStopInputs().length >= 8) {
      showError("Maximum 8 stops allowed.");
      return;
    }

    stopCounter++;
    var id  = "stop-wp-" + stopCounter;
    var row = document.createElement("div");
    row.className    = "stop-row stop-row-wp";
    row.dataset.role = "waypoint";
    row.dataset.locked = "false";   // intermediate stops are free by default

    row.innerHTML =
      "<span class='stop-dot stop-dot-mid'>C</span>" +
      "<input type='text' id='" + id + "' class='form-input stop-input'" +
      " placeholder='Via \u2014 e.g. St Stephen\u2019s Green'>" +
      "<button class='btn-lock-stop' title='Free \u2014 can be reordered (click to lock)'>\uD83D\uDD13</button>" +
      "<button class='btn-remove-stop' title='Remove stop' aria-label='Remove stop'>&#10005;</button>";

    wireLockBtn(row);

    row.querySelector(".btn-remove-stop").addEventListener("click", function () {
      row.remove();
      relabelDots();
    });

    // Apply current optimise-toggle visibility to the new lock button
    var newLockBtn = row.querySelector(".btn-lock-stop");
    if (newLockBtn) newLockBtn.style.visibility = optimizeToggle.checked ? "visible" : "hidden";

    var dest = document.querySelector("#stops-container [data-role='destination']");
    document.getElementById("stops-container").insertBefore(row, dest);
    relabelDots();
    row.querySelector("input").focus();
  }

  document.getElementById("add-stop-btn").addEventListener("click", addIntermediateStop);

  document.getElementById("stops-container").addEventListener("keydown", function (e) {
    if (e.key === "Enter") document.getElementById("calculate-btn").click();
  });

  /* ---- Steps toggle ---- */
  var stepsToggleBtn = document.getElementById("steps-toggle");
  var stepsList      = document.getElementById("route-steps");

  if (stepsToggleBtn) {
    stepsToggleBtn.addEventListener("click", function () {
      stepsOpen = !stepsOpen;
      stepsList.style.display = stepsOpen ? "block" : "none";
      stepsToggleBtn.textContent = stepsOpen
        ? "Hide turn-by-turn \u25B2"
        : "Show turn-by-turn \u25BC";
    });
  }

  /* ====================================================
     Calculate button
     ==================================================== */
  document.getElementById("calculate-btn").addEventListener("click", function () {
    var rows   = allStopRows();
    var stops  = [];
    var locked = [];

    rows.forEach(function (row) {
      var inp = row.querySelector(".stop-input");
      if (inp && inp.value.trim()) {
        stops.push(inp.value.trim());
        locked.push(isLocked(row));
      }
    });

    if (stops.length < 2) {
      showError("Please enter at least an origin and a destination.");
      return;
    }

    clearError();
    showLoading(true);

    var optimize = optimizeToggle.checked;

    var params = stops
      .map(function (s) { return "stops[]=" + encodeURIComponent(s); })
      .join("&");
    params += "&" + locked
      .map(function (l) { return "locked[]=" + l; })
      .join("&");
    params += "&optimize=" + optimize;
    params += "&mode=" + encodeURIComponent(currentMode);
    params += "&type=" + encodeURIComponent(currentType);

    var timeType  = (document.querySelector("input[name='time-type']:checked") || {}).value || "now";
    var timeValue = (document.getElementById("time-input") || {}).value || "";
    if (timeType === "depart" && timeValue) {
      params += "&dep_time=" + encodeURIComponent(timeValue);
    } else if (timeType === "arrive" && timeValue) {
      params += "&arr_time=" + encodeURIComponent(timeValue);
    }

    fetch("/routing/calculate?" + params)
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, data: d }; });
      })
      .then(function (res) {
        showLoading(false);
        if (!res.ok || res.data.error) {
          if (res.data.transit_unavailable) {
            showTransitUnavailable();
          } else {
            showError(res.data.error || "Routing failed.");
          }
          return;
        }
        renderResult(res.data);
      })
      .catch(function (err) {
        showLoading(false);
        showError("Network error: " + err.message);
      });
  });

  /* ====================================================
     Result rendering
     ==================================================== */

  var MODE_LABEL  = { driving: "Driving", cycling: "Cycling", walking: "Walking", transit: "Transit" };
  var MODE_COLOUR = { driving: "#2563eb", cycling: "#16a34a", walking: "#d97706", transit: "#7c3aed" };

  function renderResult(data) {
    routeLayer.clearLayers();
    markerLayer.clearLayers();

    var route  = data.route;
    var colour = MODE_COLOUR[data.mode] || "#2563eb";

    if (data.is_transit) {
      renderTransit(data, colour);
    } else {
      renderOsrm(data, colour);
    }

    /* Stats panel */
    var distStr = route.distance_km >= 1
      ? route.distance_km + " km"
      : route.distance_meters + " m";
    var durMins = route.duration_minutes;
    var durStr  = durMins >= 60
      ? Math.floor(durMins / 60) + " hr " + (durMins % 60) + " min"
      : durMins + " min";

    var badge = document.getElementById("route-mode-badge");
    badge.textContent = MODE_LABEL[data.mode] || data.mode;
    badge.className   = "route-mode-badge route-mode-badge-" + data.mode;

    document.getElementById("route-stats").innerHTML =
      "<div class='route-stat'>" +
        "<span class='route-stat-val'>" + durStr  + "</span>" +
        "<span class='route-stat-lbl'>Duration</span>" +
      "</div>" +
      "<div class='route-stat'>" +
        "<span class='route-stat-val'>" + distStr + "</span>" +
        "<span class='route-stat-lbl'>Distance</span>" +
      "</div>";

    var ecoEl = document.getElementById("eco-note");
    if (data.eco_note) {
      ecoEl.textContent   = "\uD83C\uDF31 " + data.eco_note;
      ecoEl.style.display = "block";
    } else {
      ecoEl.style.display = "none";
    }

    var reorderEl = document.getElementById("reorder-note");
    if (data.waypoint_order_changed) {
      // Build the before → after summary using stop labels
      var stops   = data.stops || [];
      var letters = stops.map(function (_, i) { return String.fromCharCode(65 + i); });
      reorderEl.textContent   = "\u2728 Stop order was optimised: " + letters.join(" \u2192 ");
      reorderEl.style.display = "block";
    } else {
      reorderEl.style.display = "none";
    }

    document.getElementById("route-summary").style.display = "block";
  }

  /* ---- OSRM (driving / cycling / walking) ---- */
  function renderOsrm(data, colour) {
    var route = data.route;

    if (route.geometry && route.geometry.coordinates) {
      var latlngs = route.geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
      var poly = L.polyline(latlngs, { color: colour, weight: 5, opacity: 0.85 });
      routeLayer.addLayer(poly);
      map.fitBounds(poly.getBounds(), { padding: [40, 40] });
    }

    var stops = data.stops || [data.origin, data.destination].filter(Boolean);
    stops.forEach(function (stop, idx) {
      var letter  = String.fromCharCode(65 + idx);
      var isFirst = idx === 0;
      var isLast  = idx === stops.length - 1;
      var bg = isFirst ? "#16a34a" : isLast ? "#dc2626" : "#7c3aed";
      addMarker(stop, letter, bg);
    });

    document.getElementById("osrm-steps-wrap").style.display   = "block";
    document.getElementById("transit-legs-wrap").style.display = "none";
    document.getElementById("transit-info-note").style.display = "none";

    var stepsEl = document.getElementById("route-steps");
    stepsEl.innerHTML = "";
    (route.steps || []).forEach(function (step) {
      var li   = document.createElement("li");
      li.className = "step-item";
      var dist = step.distance_m >= 1000
        ? (step.distance_m / 1000).toFixed(1) + " km"
        : step.distance_m + " m";
      li.innerHTML =
        "<span class='step-instruction'>" + step.instruction + "</span>" +
        "<span class='step-dist'>" + dist + "</span>";
      stepsEl.appendChild(li);
    });

    stepsOpen = false;
    stepsEl.style.display = "none";
    if (stepsToggleBtn) stepsToggleBtn.textContent = "Show turn-by-turn \u25BC";
  }

  /* ---- Transit ---- */
  var TRANSIT_COLOUR = {
    WALK:   "#6b7280",
    BUS:    "#2563eb",
    TRAM:   "#16a34a",
    RAIL:   "#dc2626",
    SUBWAY: "#7c3aed",
    FERRY:  "#0891b2",
  };
  var TRANSIT_ICON = {
    WALK:   "\uD83D\uDEB6",
    BUS:    "\uD83D\uDE8C",
    TRAM:   "\uD83D\uDE83",
    RAIL:   "\uD83D\uDE82",
    SUBWAY: "\uD83D\uDE87",
    FERRY:  "\u26F4\uFE0F",
  };

  function renderTransit(data, colour) {
    var route  = data.route;
    var legs   = route.legs || [];
    var bounds = [];

    legs.forEach(function (leg) {
      if (!leg.coords || !leg.coords.length) return;
      var legColour = TRANSIT_COLOUR[leg.mode] || colour;
      var isWalk    = leg.mode === "WALK";
      var poly = L.polyline(leg.coords, {
        color:     legColour,
        weight:    isWalk ? 3 : 5,
        opacity:   0.85,
        dashArray: isWalk ? "6 6" : null,
      });
      routeLayer.addLayer(poly);
      var b = poly.getBounds();
      if (b.isValid()) bounds.push(b);
    });

    if (bounds.length) {
      var combined = bounds[0];
      bounds.forEach(function (b) { combined.extend(b); });
      map.fitBounds(combined, { padding: [40, 40] });
    }

    var stops = data.stops || [];
    if (stops.length >= 1) addMarker(stops[0], "A", "#16a34a");
    if (stops.length >= 2) addMarker(stops[stops.length - 1], "B", "#dc2626");

    document.getElementById("osrm-steps-wrap").style.display   = "none";
    document.getElementById("transit-legs-wrap").style.display = "block";

    var infoEl = document.getElementById("transit-info-note");
    infoEl.innerHTML =
      "Transit data may be incomplete for Dublin. For live schedules see " +
      "<a href='https://www.transportforireland.ie/plan-a-journey/' " +
      "target='_blank' rel='noopener'>TFI Journey Planner</a>.";
    infoEl.style.display = "block";

    var legsEl = document.getElementById("transit-legs");
    legsEl.innerHTML = "";
    legs.forEach(function (leg) {
      var icon      = TRANSIT_ICON[leg.mode] || "\uD83D\uDE8C";
      var legColour = TRANSIT_COLOUR[leg.mode] || colour;
      var dur       = leg.duration_s >= 60
        ? Math.round(leg.duration_s / 60) + " min"
        : leg.duration_s + " s";
      var routeName = leg.route_short || leg.route_long || "";

      var div = document.createElement("div");
      div.className = "transit-leg";
      div.style.borderLeftColor = legColour;
      div.innerHTML =
        "<span class='transit-mode-icon'>" + icon + "</span>" +
        "<div class='transit-leg-detail'>" +
          "<span class='transit-leg-label'>" +
            (routeName ? "<strong>" + routeName + "</strong> \u00B7 " : "") +
            esc(leg.from_name) + " \u2192 " + esc(leg.to_name) +
          "</span>" +
          "<span class='transit-leg-dur'>" + dur + "</span>" +
        "</div>";
      legsEl.appendChild(div);
    });
  }

  /* ---- Shared helpers ---- */
  function addMarker(stop, label, bg) {
    var icon = L.divIcon({
      html:
        "<div style='background:" + bg + ";color:#fff;border-radius:50%;" +
        "width:22px;height:22px;display:flex;align-items:center;" +
        "justify-content:center;font-weight:700;font-size:13px;" +
        "border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)'>" +
        label + "</div>",
      className:  "",
      iconAnchor: [11, 11],
    });
    L.marker([stop.lat, stop.lon], { icon: icon })
      .bindPopup("<strong>" + label + "</strong><br>" + stop.name)
      .addTo(markerLayer);
  }

  function esc(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function showError(msg) {
    var el = document.getElementById("route-error");
    el.textContent   = msg;
    el.style.display = "block";
  }

  function showTransitUnavailable() {
    var el = document.getElementById("route-error");
    el.innerHTML =
      "<strong>\uD83D\uDE8C Transit unavailable for Dublin</strong><br>" +
      "Live transit routing isn\u2019t available for this area yet. " +
      "<a href='https://www.transportforireland.ie/plan-a-journey/' " +
      "target='_blank' rel='noopener'>Plan your journey on TFI \u2197</a>" +
      "<br><br>" +
      "<button id='transit-walk-btn' class='btn-transit-fallback'>" +
      "\uD83D\uDEB6 Use walking route instead</button>";
    el.style.display = "block";

    document.getElementById("transit-walk-btn").addEventListener("click", function () {
      // Switch UI to walking mode
      document.querySelectorAll("#mode-control .seg-btn").forEach(function (b) {
        b.classList.remove("active");
        if (b.dataset.value === "walking") b.classList.add("active");
      });
      currentMode = "walking";
      var pr = document.getElementById("priority-row");
      if (pr) pr.style.display = "";
      // Clear error and recalculate
      clearError();
      document.getElementById("calculate-btn").click();
    });
  }

  function clearError() {
    var el = document.getElementById("route-error");
    el.style.display = "none";
    el.innerHTML     = "";
  }

  function showLoading(on) {
    var btn = document.getElementById("calculate-btn");
    btn.disabled    = on;
    btn.textContent = on ? "Calculating\u2026" : "Calculate Route";
  }

})();
