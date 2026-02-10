import json
import requests

# ---- CONFIG ----
API_KEY = "apiKey"  # Get free key at https://developer.tomtom.com
# ----------------


def geocode_address(address):
    """Convert address -> (lat, lng) using TomTom Search API."""
    url = "https://api.tomtom.com/search/2/geocode/{}.json".format(address)
    params = {"key": API_KEY, "limit": 1}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("results"):
        raise RuntimeError(f"Geocoding failed for '{address}'")

    pos = data["results"][0]["position"]
    return (pos["lat"], pos["lon"])


def get_traffic_incidents(lat, lng, radius_km=10):
    """Get traffic incidents within a radius of a point using TomTom Traffic API."""

    # Calculate bounding box from center point and radius
    # Rough approximation: 1 degree lat ≈ 111km, 1 degree lng ≈ 111km * cos(lat)
    import math

    lat_offset = radius_km / 111.0
    lng_offset = radius_km / (111.0 * math.cos(math.radians(lat)))

    min_lat = lat - lat_offset
    max_lat = lat + lat_offset
    min_lng = lng - lng_offset
    max_lng = lng + lng_offset

    # TomTom Incident Details API
    url = "https://api.tomtom.com/traffic/services/5/incidentDetails"

    params = {
        "key": API_KEY,
        "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}",
        "fields": "{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,"
        "events{description,code},startTime,endTime,from,to,length,delay,roadNumbers}}}",
        "language": "en-GB",
        "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",  # All incident types
        "timeValidityFilter": "present",
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    return data.get("incidents", [])


def get_incident_category_name(category):
    """Convert TomTom incident category code to human-readable name."""
    categories = {
        0: "Unknown",
        1: "Accident",
        2: "Fog",
        3: "Dangerous Conditions",
        4: "Rain",
        5: "Ice",
        6: "Jam",
        7: "Lane Closed",
        8: "Road Closed",
        9: "Road Works",
        10: "Wind",
        11: "Flooding",
        14: "Broken Down Vehicle",
    }
    return categories.get(category, "Unknown")


def get_magnitude_name(magnitude):
    """Convert magnitude code to human-readable severity."""
    magnitudes = {0: "Unknown", 1: "Minor", 2: "Moderate", 3: "Major", 4: "Undefined"}
    return magnitudes.get(magnitude, "Unknown")


def format_incidents(incidents):
    """Format incidents into a clean list."""
    formatted = []

    for incident in incidents:
        props = incident.get("properties", {})

        # Get event descriptions
        events = props.get("events", [])
        descriptions = [e.get("description", "") for e in events if e.get("description")]

        formatted_incident = {
            "category": get_incident_category_name(props.get("iconCategory", 0)),
            "severity": get_magnitude_name(props.get("magnitudeOfDelay", 0)),
            "description": (" | ".join(descriptions) if descriptions else "No description"),
            "from": props.get("from", "Unknown"),
            "to": props.get("to", "Unknown"),
            "road": (", ".join(props.get("roadNumbers", [])) if props.get("roadNumbers") else "Unknown road"),
            "length_meters": props.get("length", 0),
            "delay_seconds": props.get("delay", 0),
            "delay_minutes": (round(props.get("delay", 0) / 60, 1) if props.get("delay") else 0),
        }

        formatted.append(formatted_incident)

    return formatted


def main():
    print("=== TomTom Traffic Incidents ===\n")

    location_input = input("Enter location (city, address, or lat,lng): ").strip()

    radius_input = input("Search radius in km (default 10): ").strip()
    radius_km = float(radius_input) if radius_input else 10.0

    try:
        # Parse location
        if "," in location_input:
            parts = location_input.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                except ValueError:
                    lat, lng = geocode_address(location_input)
            else:
                lat, lng = geocode_address(location_input)
        else:
            print(f"\nGeocoding '{location_input}'...")
            lat, lng = geocode_address(location_input)

        print(f"Searching for incidents near ({lat}, {lng})...\n")

        # Get incidents
        incidents = get_traffic_incidents(lat, lng, radius_km)

        if not incidents:
            result = {
                "location": location_input,
                "coordinates": {"lat": lat, "lng": lng},
                "radius_km": radius_km,
                "total_incidents": 0,
                "message": "No traffic incidents found in this area",
                "incidents": [],
            }
        else:
            formatted = format_incidents(incidents)

            # Sort by severity (major first)
            severity_order = {
                "Major": 0,
                "Moderate": 1,
                "Minor": 2,
                "Unknown": 3,
                "Undefined": 4,
            }
            formatted.sort(key=lambda x: severity_order.get(x["severity"], 5))

            # Count by category
            category_counts = {}
            for inc in formatted:
                cat = inc["category"]
                category_counts[cat] = category_counts.get(cat, 0) + 1

            result = {
                "location": location_input,
                "coordinates": {"lat": lat, "lng": lng},
                "radius_km": radius_km,
                "total_incidents": len(formatted),
                "summary": category_counts,
                "incidents": formatted,
            }

        print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e)}
        print(json.dumps(error_result, indent=2))


if __name__ == "__main__":
    main()
