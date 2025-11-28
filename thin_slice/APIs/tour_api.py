import requests
import math


def get_current_location():
    """Detect your current location automatically."""
    try:
        response = requests.get(
            "http://ip-api.com/json/?fields=status,lat,lon," "city,country,isp,mobile"
        )
        data = response.json()

        if data["status"] == "success":
            return {
                "latitude": data["lat"],
                "longitude": data["lon"],
                "city": data["city"],
                "country": data["country"],
            }
    except Exception as e:
        print(f"Error getting location: {e}")

    # Fallback to Dublin
    return {
        "latitude": 53.3498,
        "longitude": -6.2603,
        "city": "Dublin",
        "country": "Ireland",
    }


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def get_tours_from_api(latitude, longitude):
    """
    Fetch attractions near location using Overpass API (OpenStreetMap).
    Searches for museums, monuments, attractions, and historic sites.
    """
    try:
        print("Searching for attractions near your location...\n")

        # Convert 5km radius to degrees (approximate)
        radius_deg = 0.045  # roughly 5km

        # Overpass API query - simpler format
        overpass_query = f"""
        [out:json];
        (
          node["tourism"="attraction"](around:5000,{latitude},{longitude});
          node["tourism"="museum"](around:5000,{latitude},{longitude});
          node["historic"="monument"](around:5000,{latitude},{longitude});
          node["historic"="castle"](around:5000,{latitude},{longitude});
          way["tourism"="attraction"](around:5000,{latitude},{longitude});
          way["tourism"="museum"](around:5000,{latitude},{longitude});
        );
        out center;
        """

        url = "https://overpass-api.de/api/interpreter"
        response = requests.post(url, data=overpass_query, timeout=30)

        # Check if response is valid
        if response.status_code != 200:
            print(f"API returned status code: {response.status_code}")
            return None

        try:
            data = response.json()
        except:
            print(f"Invalid JSON response from API")
            return None

        elements = data.get("elements", [])

        tours = []
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name", "Unknown")

            # Determine type
            tour_type = "Attraction"
            if tags.get("tourism"):
                tourism_type = tags.get("tourism")
                tour_type = tourism_type.replace("_", " ").title()
            elif tags.get("historic"):
                historic_type = tags.get("historic")
                tour_type = historic_type.replace("_", " ").title()

            # Get coordinates
            lat_detail = None
            lon_detail = None

            if "lat" in element and "lon" in element:
                lat_detail = element["lat"]
                lon_detail = element["lon"]
            elif "center" in element:
                lat_detail = element["center"].get("lat")
                lon_detail = element["center"].get("lon")

            if lat_detail is None or lon_detail is None:
                continue

            dist = calculate_distance(latitude, longitude, lat_detail, lon_detail)

            tours.append(
                {
                    "name": name,
                    "type": tour_type,
                    "latitude": lat_detail,
                    "longitude": lon_detail,
                    "distance_km": round(dist, 2),
                    "price": "Check on-site",
                }
            )

        return tours if tours else None

    except Exception as e:
        print(f"Error fetching from Overpass API: {e}")
        return None


def filter_tours_by_radius(tours, radius_km=2.0):
    """Filter tours to only include those within a certain radius."""
    return [tour for tour in tours if tour["distance_km"] <= radius_km]


def display_tours(your_location, tours, radius_km=2.0):
    """Display tours in a formatted way, filtered by radius."""
    if not tours:
        print("No tours found")
        return

    nearby_tours = filter_tours_by_radius(tours, radius_km)

    print("\n" + "=" * 80)
    print(f"TOURS WITHIN {radius_km} KM OF {your_location['city'].upper()}")
    print("=" * 80)
    print(f"Your Location: {your_location['city']}, " f"{your_location['country']}")
    print(
        f"GPS: {your_location['latitude']: .4f}, "
        f"{your_location['longitude']: .4f}\n"
    )

    if not nearby_tours:
        print(f"No tours found within {radius_km} km")
        print(f"Total tours available: {len(tours)}")
        print("=" * 80 + "\n")
        return

    print(f"Found {len(nearby_tours)} tour(s)" f" within {radius_km} km: \n")
    tours_sorted = sorted(nearby_tours, key=lambda x: x["distance_km"])

    for i, tour in enumerate(tours_sorted, 1):
        print(f"{i}. {tour['name']}")
        print(f"   Type: {tour.get('type', 'N/A')}")
        print(f"   Distance: {tour['distance_km']} km")
        print(f"   Price: {tour.get('price', 'N/A')}")
        print()

    print("=" * 80 + "\n")
    return tours_sorted


def display_closest_tour(your_location, tours):
    """Display the closest tour."""
    if not tours:
        print("No tours found")
        return

    tours_sorted = sorted(tours, key=lambda x: x["distance_km"])
    closest = tours_sorted[0]

    print("\n" + "=" * 80)
    print("CLOSEST TOUR TO YOU")
    print("=" * 80)
    print(f"Your Location: {your_location['city']}, " f"{your_location['country']}")
    print(
        f"Your GPS: {your_location['latitude']: .4f}, "
        f"{your_location['longitude']: .4f}"
    )
    print("-" * 80)
    print(f"Tour Name: {closest['name']}")
    print(f"Type: {closest.get('type', 'N/A')}")
    print(f"Distance: {closest['distance_km']} km away")
    print(f"Price: {closest.get('price', 'N/A')}")
    print(f"GPS: {closest['latitude']: .4f}, {closest['longitude']: .4f}")
    print("=" * 80 + "\n")


# Main execution
if __name__ == "__main__":
    print("\n" + "-" * 80)
    print("TOURIST INFORMATION API TEST")
    print("Find tours and activities near your location")
    print("-" * 80 + "\n")

    your_location = get_current_location()
    print(f"Location: {your_location['city']}, {your_location['country']}")
    print(
        f"   GPS: {your_location['latitude']: .4f}, "
        f"{your_location['longitude']: .4f}\n"
    )

    tours = get_tours_from_api(your_location["latitude"], your_location["longitude"])

    if tours is None:
        print("Failed to fetch tours from API. Exiting.")
    else:
        display_closest_tour(your_location, tours)

        print("Filtering tours by radius...\n")
        display_tours(your_location, tours, radius_km=2.0)

        print("Trying larger radius (5km)...\n")
        display_tours(your_location, tours, radius_km=5.0)
