import requests
import math


def get_location_from_user():
    """Prompt user for location and convert to coordinates using Nominatim."""
    location_input = input("Enter your location (address, city, or place): ").strip()

    if not location_input:
        print("No location provided. Using Dublin city center as default.")
        return {
            "latitude": 53.3498,
            "longitude": -6.2603,
            "city": "Dublin",
            "country": "Ireland",
            "display_name": "Dublin, Ireland",
        }

    # Use Nominatim geocoding API
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": location_input, "format": "json", "limit": 1}
    headers = {"User-Agent": "WaterQualityApp/1.0"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data:
            result = data[0]
            return {
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
                "city": result.get("display_name", "").split(",")[0],
                "country": result.get("display_name", "").split(",")[-1].strip(),
                "display_name": result["display_name"],
            }
        else:
            print(f"Location '{location_input}' not found. Using Dublin city center.")
            return {
                "latitude": 53.3498,
                "longitude": -6.2603,
                "city": "Dublin",
                "country": "Ireland",
                "display_name": "Dublin, Ireland",
            }
    except Exception as e:
        print(f"Error geocoding location: {e}")
        print("Using Dublin city center as fallback.")
        return {
            "latitude": 53.3498,
            "longitude": -6.2603,
            "city": "Dublin",
            "country": "Ireland",
            "display_name": "Dublin, Ireland",
        }


def irish_grid_to_lat_lon(easting, northing):
    """
    Convert Irish Grid coordinates to WGS84 latitude/longitude.
    Uses approximate conversion formula.
    """
    # Irish Grid origin
    E0 = 200000.0
    N0 = 250000.0
    F0 = 1.000035
    lat0 = math.radians(53.5)
    lon0 = math.radians(-8.0)

    # WGS84 parameters
    a = 6378137.0  # semi-major axis
    b = 6356752.314245  # semi-minor axis
    e2 = (a * a - b * b) / (a * a)

    # Compute lat/lon (simplified conversion)
    dN = northing - N0
    dE = easting - E0

    lat = lat0 + (dN / (a * F0))
    lon = lon0 + (dE / (a * F0 * math.cos(lat0)))

    return math.degrees(lat), math.degrees(lon)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates using Haversine."""
    R = 6371  # Earth's radius in km
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def get_all_bathing_locations():
    """Fetch all bathing water locations from EPA Ireland API."""
    url = "https://data.epa.ie/bw/api/v1/locations"
    all_locations = []
    page = 1
    per_page = 100

    try:
        print("Fetching bathing water locations from EPA Ireland...\n")

        while True:
            params = {"page": page, "per_page": per_page}

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Use "list" key instead of "results"
            locations = data.get("list", [])
            if not locations:
                break

            all_locations.extend(locations)

            # Check if there are more pages using "count"
            total_count = data.get("count", 0)
            if len(all_locations) >= total_count:
                break

            page += 1

        print(f"Retrieved {len(all_locations)} bathing water locations\n")
        return all_locations

    except requests.exceptions.RequestException as e:
        print(f"Error fetching bathing locations: {e}")
        return None


def get_measurement_for_location(location_id):
    """Fetch the most recent measurement for a specific location."""
    url = "https://data.epa.ie/bw/api/v1/measurements"

    try:
        params = {"location_id": location_id, "per_page": 1}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Use "list" key instead of "results"
        results = data.get("list", [])
        if results:
            return results[0]
        return None

    except Exception as e:
        return None


def get_active_alerts():
    """Fetch active water quality alerts."""
    url = "https://data.epa.ie/bw/api/v1/alerts"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Use "list" key instead of "results"
        return data.get("list", [])
    except Exception as e:
        print(f"Could not fetch alerts: {e}")
        return []


def find_closest_locations(your_latitude, your_longitude, max_results=5):
    """Find the closest bathing water locations to your position."""
    locations = get_all_bathing_locations()

    if not locations:
        print("Could not fetch bathing water locations")
        return None

    locations_with_distance = []

    for location in locations:
        # Get Irish Grid coordinates
        easting = location.get("easting")
        northing = location.get("northing")

        if easting is None or northing is None:
            continue

        # Convert to lat/lon
        lat, lon = irish_grid_to_lat_lon(easting, northing)

        distance = calculate_distance(your_latitude, your_longitude, lat, lon)

        locations_with_distance.append(
            {
                "name": location.get("beach_name", "Unknown"),
                "location_id": location.get("location_id"),
                "latitude": lat,
                "longitude": lon,
                "county": location.get("county_name", "Unknown"),
                "distance_km": distance,
                "classification": location.get("year1_annual_water_quality_classification", "Unknown"),
                "is_blue_flag": location.get("is_blue_flag", "No"),
                "has_lifeguard": location.get("has_lifeguard", "No"),
            }
        )

    # Sort by distance
    locations_with_distance.sort(key=lambda x: x["distance_km"])

    # Return top results
    return locations_with_distance[:max_results]


def display_closest_location(location, your_location):
    """Display the closest bathing water location."""
    if not location:
        return

    print("\n" + "=" * 80)
    print("CLOSEST BATHING WATER LOCATION")
    print("=" * 80)
    print(f"Your Location: {your_location['display_name']}")
    print(f"Your GPS: {your_location['latitude']:.4f}, {your_location['longitude']:.4f}")
    print("-" * 80)
    print(f"Beach: {location['name']}")
    print(f"County: {location['county']}")
    print(f"Distance: {location['distance_km']:.2f} km")
    print(f"GPS: {location['latitude']:.4f}, {location['longitude']:.4f}")
    print(f"Water Quality: {location['classification']}")
    print(f"Blue Flag: {location['is_blue_flag']}")
    print(f"Lifeguard: {location['has_lifeguard']}")

    # Try to get latest measurement
    measurement = get_measurement_for_location(location["location_id"])

    if measurement:
        print("\nLATEST WATER QUALITY MEASUREMENT:")
        print(f"   Date: {measurement.get('monitoring_date', 'N/A')}")
        print(f"   Result: {measurement.get('result', 'N/A')}")
    else:
        print("\nNo recent measurements available")

    print("=" * 80 + "\n")


def display_nearby_locations(your_location, locations, radius_km=50):
    """Display all nearby bathing water locations within radius."""
    if not locations:
        print("No locations found")
        return

    nearby = [loc for loc in locations if loc["distance_km"] <= radius_km]

    print("\n" + "=" * 80)
    print(f"BATHING WATER LOCATIONS WITHIN {radius_km} KM")
    print("=" * 80)
    print(f"Your Location: {your_location['display_name']}")
    print(f"GPS: {your_location['latitude']:.4f}, {your_location['longitude']:.4f}\n")

    if not nearby:
        print(f"No bathing water locations found within {radius_km} km")
        print("=" * 80 + "\n")
        return

    print(f"Found {len(nearby)} location(s):\n")

    for i, location in enumerate(nearby, 1):
        print(f"{i}. {location['name']:<40} | {location['distance_km']:>6.2f} km | {location['county']}")
        print(f"   Quality: {location['classification']:<20} | Blue Flag: {location['is_blue_flag']}")
        print()

    print("=" * 80 + "\n")
    return nearby


def display_alerts(alerts):
    """Display active water quality alerts."""
    if not alerts:
        print("✓ No active water quality alerts\n")
        return

    print("\n" + "=" * 80)
    print("⚠ ACTIVE WATER QUALITY ALERTS")
    print("=" * 80)
    print(f"Total Alerts: {len(alerts)}\n")

    for i, alert in enumerate(alerts, 1):
        print(f"{i}. {alert.get('location_name', 'Unknown Location')}")
        print(f"   Alert Type: {alert.get('incident_type', 'N/A')}")
        print(f"   Status: {alert.get('status', 'N/A')}")
        print(f"   Date: {alert.get('date_reported', 'N/A')}")
        print()

    print("=" * 80 + "\n")


# Main execution
if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("█ IRELAND BATHING WATER QUALITY CHECKER")
    print("█ Find water quality information near your location")
    print("█ Data from EPA Ireland")
    print("█" * 80 + "\n")

    your_location = get_location_from_user()
    print(f"\nUsing location: {your_location['display_name']}")
    print(f"GPS: {your_location['latitude']:.4f}, {your_location['longitude']:.4f}\n")

    # Find closest locations
    print("Finding closest bathing water locations...\n")
    closest_locations = find_closest_locations(your_location["latitude"], your_location["longitude"], max_results=10)

    if closest_locations:
        # Display closest location with details
        display_closest_location(closest_locations[0], your_location)

        # Display all nearby locations (within 50km)
        display_nearby_locations(your_location, closest_locations, radius_km=50)
    else:
        print("No bathing water locations found\n")

    # Check for active alerts
    print("Checking for active water quality alerts...\n")
    alerts = get_active_alerts()
    display_alerts(alerts)
