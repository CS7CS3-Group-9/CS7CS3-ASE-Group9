import os
import datetime
from flask import Flask, render_template, jsonify, request
import requests
import folium
import polyline
import firebase_admin
from firebase_admin import credentials, firestore

# ---- CONFIG ----
API_KEY = os.environ.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")
FIRESTORE_COLLECTION = "routes"
# ----------------

app = Flask(__name__)

firebase_admin.initialize_app()
db = firestore.client()


def geocode_address(address):
    """Convert address -> (lat, lng) using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": API_KEY}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError(f"Geocoding failed: {data.get('status')}, {data}")
    loc = data["results"][0]["geometry"]["location"]
    return (loc["lat"], loc["lng"])


def get_route_from_google(origin, destination, travel_mode="DRIVE"):
    """Call Google Routes API and return route object."""
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
    }
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": travel_mode
    }
    resp = requests.post(url, headers=headers, json=payload)
    # Debug prints (helpful while developing)
    print("=== GOOGLE ROUTES API RESPONSE ===")
    print("Status code:", resp.status_code)
    print(resp.text)
    print("==================================")
    resp.raise_for_status()
    data = resp.json()
    if "routes" not in data or not data["routes"]:
        raise RuntimeError(f"No routes found: {data}")
    return data["routes"][0]


def plot_route(origin, destination, encoded_polyline, out_path="route_map.html"):
    """Create a folium map and save to file (route_map.html by default)."""
    route_points = polyline.decode(encoded_polyline)
    midpoint = [(origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2]
    m = folium.Map(location=midpoint, zoom_start=8)
    folium.PolyLine(route_points, weight=4, opacity=0.8).add_to(m)
    folium.Marker(origin, tooltip="Origin", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(destination, tooltip="Destination", icon=folium.Icon(color="red")).add_to(m)
    m.save(out_path)


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


def save_route_record(origin_input, destination_input, origin_coord, destination_coord, distance_m, duration):
    """Save the route request details to Firestore."""
    try:
        doc = {
            "origin_input": origin_input,
            "destination_input": destination_input,
            "origin_coord": {"lat": origin_coord[0], "lng": origin_coord[1]},
            "destination_coord": {"lat": destination_coord[0], "lng": destination_coord[1]},
            "distance_m": distance_m,
            "duration": duration,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        ref = db.collection(FIRESTORE_COLLECTION).add(doc)
        print("Saved route to Firestore, id:", ref[1].id if len(ref) > 1 else ref)
    except Exception as e:
        print("Error saving to Firestore:", e)


def get_previous_requests(limit=20):
    """Return recent route documents from Firestore (most recent first)."""
    try:
        docs = (
            db.collection(FIRESTORE_COLLECTION)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        results = []
        for d in docs:
            item = d.to_dict()
            item["id"] = d.id
            results.append(item)
        return results
    except Exception as e:
        print("Error fetching history:", e)
        return []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_route", methods=["POST"])
def get_route_endpoint():
    """
    Body: { origin: "<string>", destination: "<string>" }
    origin/destination can be "lat,lng" or an address string.
    """
    try:
        data = request.get_json()
        origin_input = data.get("origin", "")
        destination_input = data.get("destination", "")

        if not origin_input or not destination_input:
            return jsonify({"error": "origin and destination required"}), 400

        # Parse inputs to lat/lng
        origin_coord = parse_input(origin_input)
        destination_coord = parse_input(destination_input)

        # Get the route from Google
        route = get_route_from_google(origin_coord, destination_coord)
        encoded_poly = route["polyline"]["encodedPolyline"]
        distance_m = route.get("distanceMeters")
        duration = route.get("duration")

        # Plot route and save map
        plot_route(origin_coord, destination_coord, encoded_poly)

        # Save to Firestore (best-effort)
        try:
            save_route_record(origin_input, destination_input, origin_coord, destination_coord, distance_m, duration)
        except Exception as e:
            print("Firestore save failed:", e)

        return jsonify({
            "distance_m": distance_m,
            "duration": duration,
            "map_url": "/route_map"
        })
    except requests.HTTPError as e:
        return jsonify({"error": "Upstream HTTP error", "details": str(e)}), 502
    except Exception as e:
        print("Internal error in get_route_endpoint:", e)
        return jsonify({"error": "internal_server_error", "details": str(e)}), 500


@app.route("/route_map")
def show_map():
    """Return the generated route_map.html"""
    if not os.path.exists("route_map.html"):
        return "Map not generated yet.", 404
    with open("route_map.html", "r", encoding="utf-8") as f:
        return f.read()


@app.route("/history", methods=["GET"])
def history_endpoint():
    """Return last 20 route requests from Firestore (as JSON)."""
    try:
        previous = get_previous_requests(limit=20)
        return jsonify(previous)
    except Exception as e:
        print("History endpoint error:", e)
        return jsonify({"error": "failed to fetch history", "details": str(e)}), 500


if __name__ == "__main__":
    # Helpful startup info
    print("Starting app. Make sure GOOGLE_API_KEY and GOOGLE_APPLICATION_CREDENTIALS are set.")
    app.run(host="0.0.0.0", port=5000, debug=True)
