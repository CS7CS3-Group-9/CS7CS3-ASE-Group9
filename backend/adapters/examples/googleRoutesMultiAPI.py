import os
import json
import requests
from itertools import permutations

# ---- CONFIG ----
API_KEY = "apiKey"  # Replace with your actual key
# ----------------


def geocode_address(address):
    """Convert address -> (lat, lng) using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": API_KEY}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError(f"Geocoding failed for '{address}': {data.get('status')}")
    loc = data["results"][0]["geometry"]["location"]
    return (loc["lat"], loc["lng"])


def parse_input(value):
    """Determine whether value is 'lat,lng' or an address. Returns (lat, lng)."""
    value = value.strip()
    if "," in value:
        parts = value.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                return (lat, lng)
            except ValueError:
                pass
    return geocode_address(value)


def get_single_route(origin, destination, travel_mode="DRIVE"):
    """Get route between two points using Routes API."""
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
    }
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": travel_mode,
        "routingPreference": "TRAFFIC_AWARE",
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    if "routes" not in data or not data["routes"]:
        return None, None

    route = data["routes"][0]
    duration_str = route.get("duration", "0s")
    distance = route.get("distanceMeters", 0)

    # Parse duration
    if duration_str.endswith("s"):
        seconds = int(duration_str[:-1])
    else:
        seconds = 0

    return seconds, distance


def build_time_matrix(locations):
    """Build time matrix by calling Routes API for each pair."""
    n = len(locations)
    times = [[0] * n for _ in range(n)]
    distances = [[0] * n for _ in range(n)]

    total_calls = n * (n - 1)
    current_call = 0

    for i in range(n):
        for j in range(n):
            if i != j:
                current_call += 1
                print(f"  Calculating route {current_call}/{total_calls}...", end="\r")
                duration, distance = get_single_route(locations[i], locations[j])
                times[i][j] = duration if duration else 999999
                distances[i][j] = distance if distance else 0

    print()  # New line after progress
    return times, distances


def find_optimal_route(times, num_locations, start_index=0):
    """Find the optimal route visiting all locations starting from start_index."""
    if num_locations <= 1:
        return [0], 0

    other_indices = [i for i in range(num_locations) if i != start_index]

    best_route = None
    best_time = float("inf")

    for perm in permutations(other_indices):
        route = [start_index] + list(perm)
        total_time = 0

        for i in range(len(route) - 1):
            total_time += times[route[i]][route[i + 1]]

        if total_time < best_time:
            best_time = total_time
            best_route = route

    return best_route, best_time


def format_duration(seconds):
    """Convert seconds to human-readable format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def main():
    print("=== Multi-Stop Route Optimizer ===")
    print("Enter locations one per line. Type 'done' when finished.")
    print("(First location will be the starting point)\n")

    location_inputs = []
    i = 1
    while True:
        prompt = f"Location {i}: "
        user_input = input(prompt).strip()
        if user_input.lower() == "done":
            break
        if user_input:
            location_inputs.append(user_input)
            i += 1

    if len(location_inputs) < 2:
        print(json.dumps({"error": "Need at least 2 locations"}, indent=2))
        return

    if len(location_inputs) > 8:
        print(
            json.dumps(
                {"error": "Maximum 8 locations supported (too many API calls otherwise)"},
                indent=2,
            )
        )
        return

    try:
        # Geocode all locations
        print("\nGeocoding locations...")
        locations = []
        location_data = []
        for addr in location_inputs:
            coords = parse_input(addr)
            locations.append(coords)
            location_data.append({"input": addr, "coordinates": {"lat": coords[0], "lng": coords[1]}})
            print(f"  Got: {addr}")

        # Build time matrix using individual route calls
        print("\nCalculating routes with traffic...")
        times, distances = build_time_matrix(locations)

        # Find optimal route
        print("Finding optimal route...\n")
        optimal_route, total_time = find_optimal_route(times, len(locations), start_index=0)

        # Calculate total distance
        total_distance = 0
        for i in range(len(optimal_route) - 1):
            from_idx = optimal_route[i]
            to_idx = optimal_route[i + 1]
            total_distance += distances[from_idx][to_idx]

        # Build leg details
        legs = []
        for i in range(len(optimal_route) - 1):
            from_idx = optimal_route[i]
            to_idx = optimal_route[i + 1]
            leg_time = times[from_idx][to_idx]
            leg_distance = distances[from_idx][to_idx]
            legs.append(
                {
                    "from": location_inputs[from_idx],
                    "to": location_inputs[to_idx],
                    "duration_seconds": leg_time,
                    "duration_formatted": format_duration(leg_time),
                    "distance_meters": leg_distance,
                    "distance_km": round(leg_distance / 1000, 1),
                }
            )

        # Build result
        result = {
            "optimal_route_order": [location_inputs[i] for i in optimal_route],
            "total_duration_seconds": total_time,
            "total_duration_formatted": format_duration(total_time),
            "total_distance_km": round(total_distance / 1000, 1),
            "number_of_stops": len(location_inputs),
            "legs": legs,
        }

        print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e)}
        print(json.dumps(error_result, indent=2))


if __name__ == "__main__":
    main()
