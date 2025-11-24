"""
Dublin Bus Route 39A Tracker
Uses the GTFS-R API from https://developer.nationaltransport.ie/
"""

import csv
import time
from datetime import datetime

import requests

API_KEY = "1fea1c21bef840e6bf0241e34a41e5d8"  # Replace with your key
BASE_URL = "https://api.nationaltransport.ie/gtfsr/v2"


# -------------------------------------------------------
# 1. Get route_id from route_short_name
# -------------------------------------------------------
def get_route_id_from_short_name(short_name, routes_file="routes.txt"):
    with open(routes_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["route_short_name"].strip().upper() == short_name.upper():
                return row["route_id"]
    return None


# -------------------------------------------------------
# 2. Load routes and parse start/end
# -------------------------------------------------------
def load_routes(routes_file="routes.txt"):
    routes = {}
    with open(routes_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_id = row["route_id"]
            long_name = row.get("route_long_name", "")

            if " - " in long_name:
                start, end = map(str.strip, long_name.split(" - ", 1))
            else:
                start, end = long_name, long_name

            routes[route_id] = {
                "short_name": row.get("route_short_name", ""),
                "start": start,
                "end": end,
            }

    return routes


# -------------------------------------------------------
# 3. Fetch live buses
# -------------------------------------------------------
def get_realtime_active_trips(route_id, routes_dict):
    url = f"{BASE_URL}/TripUpdates?format=json"
    headers = {"x-api-key": API_KEY, "Accept": "application/json"}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    now = int(time.time())
    active = []

    route_info = routes_dict.get(route_id, {})
    start = route_info.get("start", "Unknown")
    end = route_info.get("end", "Unknown")

    for entity in data.get("entity", []):
        trip_update = entity.get("trip_update", {})
        trip = trip_update.get("trip", {})

        if trip.get("route_id") != route_id:
            continue

        stop_updates = trip_update.get("stop_time_update", [])
        if not stop_updates:
            continue

        next_stop = stop_updates[0]

        rt_time = next_stop.get("arrival", {}).get("time") or next_stop.get(
            "departure", {}
        ).get("time")

        if isinstance(rt_time, str):
            try:
                rt_time = int(rt_time)
            except ValueError:
                continue

        if rt_time is None:
            continue

        delay = (
            next_stop.get("arrival", {}).get("delay")
            or next_stop.get("departure", {}).get("delay")
            or 0
        )

        minutes_due = max(0, (rt_time - now) // 60)

        if delay <= 60:
            status = "On Time"
        elif delay <= 180:
            status = "Slight Delay"
        else:
            status = "Late"

        direction_id = trip.get("direction_id")
        if direction_id == 0:
            destination = f"{start} → {end}"
        elif direction_id == 1:
            destination = f"{end} → {start}"
        else:
            destination = "Unknown"

        active.append(
            {
                "route": route_id,
                "destination": destination,
                "rt_time": rt_time,
                "minutes_due": int(minutes_due),
                "delay": delay,
                "status": status,
            }
        )

    return active


# -------------------------------------------------------
# 4. Display bus arrivals
# -------------------------------------------------------
def display_bus_arrivals(route_short, buses):
    print("\n" + "=" * 80)
    print(f"🚌 LIVE BUSES — ROUTE {route_short}")
    print("=" * 80)
    print(f"Current Time: {datetime.now().strftime('%H:%M:%S')}\n")

    if not buses:
        print("❌ No live buses found")
        return

    for i, b in enumerate(buses, start=1):
        icon = (
            "✓"
            if b["status"] == "On Time"
            else ("⚠️" if "Slight" in b["status"] else "❌")
        )

        print(f"{i}. {route_short} → {b['destination']}")
        print(f"   Status: {icon} {b['status']}")
        print(f"   Due in: {b['minutes_due']} min")
        print(f"   Delay: {b['delay']} seconds\n")

    print("=" * 80 + "\n")


# -------------------------------------------------------
# 5. On-time performance analysis
# -------------------------------------------------------
def display_on_time_analysis(route_short, buses):
    if not buses:
        print("❌ No buses to analyze")
        return

    total = len(buses)
    on_time = sum(1 for b in buses if b["status"] == "On Time")
    slight = sum(1 for b in buses if "Slight" in b["status"])
    late = sum(1 for b in buses if "Late" in b["status"])

    on_time_pct = (on_time / total) * 100
    slight_pct = (slight / total) * 100
    late_pct = (late / total) * 100

    print("\n" + "=" * 80)
    print(f"📊 ROUTE {route_short} — LIVE ON-TIME ANALYSIS")
    print("=" * 80)
    print(f"Total buses tracked: {total}")
    print(f"✓ On Time: {on_time} buses ({on_time_pct: .1f}%)")
    print(f"⚠️  Slight Delay: {slight} buses ({slight_pct: .1f}%)")
    print(f"❌ Late: {late} buses ({late_pct: .1f}%)\n")

    if on_time_pct >= 80:
        msg = (
            f"✓ GOOD - Route {route_short} is running well "
            f"({on_time_pct: .1f}% on-time)"
        )
    elif on_time_pct >= 60:
        msg = (
            f"⚠️ FAIR - Route {route_short} has some delays "
            f"({on_time_pct: .1f}% on-time)"
        )
    else:
        msg = (
            f"❌ POOR - Route {route_short} has significant delays "
            f"({on_time_pct: .1f}% on-time)"
        )

    print(msg)
    print("=" * 80 + "\n")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    route_short = "39A"

    print("\n🔍 Loading route_id from routes.txt...\n")
    route_id = get_route_id_from_short_name(route_short)

    if not route_id:
        print(f"❌ Could not find GTFS route_id for route {route_short}")
        exit()

    print(f"✓ Route {route_short} maps to GTFS route_id: {route_id}\n")

    print("🔍 Loading routes and parsing directions...\n")
    routes_dict = load_routes("routes.txt")

    print("📡 Fetching real-time bus updates...\n")

    try:
        buses = get_realtime_active_trips(route_id, routes_dict)
        buses.sort(key=lambda x: x["minutes_due"])
        display_bus_arrivals(route_short, buses)
        display_on_time_analysis(route_short, buses)

    except Exception as e:
        print(f"❌ Error fetching data: {e}")
