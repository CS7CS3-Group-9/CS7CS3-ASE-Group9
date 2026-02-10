import os
import json
import requests

# ---- CONFIG ----
API_KEY = "apiKey"
# ----------------


def geocode_address(address):
    """Convert address -> (lat, lng) using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": API_KEY}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError(f"Geocoding failed: {data.get('status')}")
    loc = data["results"][0]["geometry"]["location"]
    return (loc["lat"], loc["lng"])


def get_route_from_google(origin, destination, travel_mode="DRIVE"):
    """Call Google Routes API and return route object."""
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
    }
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": travel_mode,
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "routes" not in data or not data["routes"]:
        raise RuntimeError(f"No routes found")
    return data["routes"][0]


def parse_input(value):
    """Determine whether value is 'lat,lng' or an address. Returns (lat, lng)."""
    value = value.strip()
    # Try coordinates
    if "," in value:
        parts = value.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                return (lat, lng)
            except ValueError:
                pass
    # Otherwise treat as address
    return geocode_address(value)


def main():
    # Get origin
    origin_input = input("Enter origin: ").strip()

    # Get destination
    destination_input = input("Enter destination: ").strip()

    try:
        # Parse inputs
        origin_coord = parse_input(origin_input)
        destination_coord = parse_input(destination_input)

        # Get route
        route = get_route_from_google(origin_coord, destination_coord)

        # Build JSON response
        result = {
            "origin": {
                "input": origin_input,
                "coordinates": {"lat": origin_coord[0], "lng": origin_coord[1]},
            },
            "destination": {
                "input": destination_input,
                "coordinates": {
                    "lat": destination_coord[0],
                    "lng": destination_coord[1],
                },
            },
            "distance_meters": route.get("distanceMeters"),
            "duration": route.get("duration"),
            "encoded_polyline": route["polyline"]["encodedPolyline"],
        }

        # Print JSON
        print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e)}
        print(json.dumps(error_result, indent=2))


if __name__ == "__main__":
    main()
