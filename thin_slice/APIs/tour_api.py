import requests
import math


def get_current_location():
    """Detect your current location automatically."""
    try:
        response = requests.get(
            "http://ip-api.com/json/?fields=status,lat,lon,"
            "city,country,isp,mobile"
        )
        data = response.json()

        if data["status"] == "success":
            return {
                "latitude": data["lat"],
                "longitude": data["lon"],
                "city": data["city"],
                "country": data["country"]
            }
    except Exception as e:
        print(f"❌ Error getting location: {e}")

    # Fallback to Dublin
    return {
        "latitude": 53.3498,
        "longitude": -6.2603,
        "city": "Dublin",
        "country": "Ireland"
    }


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad)
         * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def get_tours_from_api(latitude, longitude):
    """
    Fetch tours near location using Open Trip Map API.
    This is a free alternative to Viator, GetYourGuide, or Klook.
    """
    try:
        print("🔍 Searching for tours near your location...\n")

        url = "https://api.opentripmap.com/core/sqmapper/json"
        params = {
            "radius": 5000,  # 5km radius
            "lon": longitude,
            "lat": latitude,
            "limit": 10
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        attractions = data.get("features", [])

        tours = []
        for attraction in attractions:
            props = attraction.get("properties", {})
            geom = attraction.get("geometry", {})
            coords = geom.get("coordinates", [0, 0])

            distance = calculate_distance(latitude, longitude,
                                          coords[1], coords[0])

            tours.append({
                "name": props.get("name", "Unknown"),
                "type": (
                    props.get("kinds", "").split(",")[0]
                    if props.get("kinds") else "Attraction"
                ),
                "latitude": coords[1],
                "longitude": coords[0],
                "distance_km": round(distance, 2),
                "price": "Check on-site"
            })

        return tours

    except Exception as e:
        print(f"⚠️  Could not fetch from Open Trip Map: {e}")
        return get_sample_tours(latitude, longitude)


def get_sample_tours(latitude, longitude):
    """
    Return sample tour data for Dublin area.
    Used as fallback if API fails.
    """
    sample_tours = [
        {
            "name": "Guinness Storehouse Tour",
            "type": "Brewery Tour",
            "latitude": 53.3415,
            "longitude": -6.2775,
            "price": "€20.50",
            "duration": "2 hours"
        },
        {
            "name": "Dublin Historical Walking Tour",
            "type": "Walking Tour",
            "latitude": 53.3441,
            "longitude": -6.2635,
            "price": "€15.00",
            "duration": "2.5 hours"
        },
        {
            "name": "Temple Bar Food Tour",
            "type": "Food Tour",
            "latitude": 53.3438,
            "longitude": -6.2800,
            "price": "€45.00",
            "duration": "3 hours"
        },
        {
            "name": "Cliffs of Moher Day Trip",
            "type": "Day Tour",
            "latitude": 52.9736,
            "longitude": -9.7477,
            "price": "€55.00",
            "duration": "9 hours"
        },
        {
            "name": "Trinity College & Book of Kells Tour",
            "type": "Historical Tour",
            "latitude": 53.3434,
            "longitude": -6.2575,
            "price": "€18.50",
            "duration": "1.5 hours"
        },
        {
            "name": "Dublin Pub Crawl",
            "type": "Pub Tour",
            "latitude": 53.3498,
            "longitude": -6.2603,
            "price": "€12.00",
            "duration": "3 hours"
        }
    ]

    for tour in sample_tours:
        distance = calculate_distance(
            latitude, longitude,
            tour["latitude"], tour["longitude"])
        tour["distance_km"] = round(distance, 2)

    return sample_tours


def filter_tours_by_radius(tours, radius_km=2.0):
    """Filter tours to only include those within a certain radius."""
    return [tour for tour in tours if tour["distance_km"] <= radius_km]


def display_tours(your_location, tours, radius_km=2.0):
    """Display tours in a formatted way, filtered by radius."""
    if not tours:
        print("❌ No tours found")
        return

    nearby_tours = filter_tours_by_radius(tours, radius_km)

    print("\n" + "=" * 80)
    print(f"🎫 TOURS WITHIN {radius_km} KM OF {your_location['city'].upper()}")
    print("=" * 80)
    print(f"Your Location: {your_location['city']}, "
          f"{your_location['country']}")
    print(f"GPS: {your_location['latitude']: .4f}, "
          f"{your_location['longitude']: .4f}\n")

    if not nearby_tours:
        print(f"❌ No tours found within {radius_km} km")
        print(f"Total tours available: {len(tours)}")
        print("=" * 80 + "\n")
        return

    print(f"✓ Found {len(nearby_tours)} tour(s)"
          f" within {radius_km} km: \n")
    tours_sorted = sorted(nearby_tours, key=lambda x: x["distance_km"])

    for i, tour in enumerate(tours_sorted, 1):
        print(f"{i}. {tour['name']}")
        print(f"   Type: {tour.get('type', 'N/A')}")
        print(f"   Distance: {tour['distance_km']} km")
        print(f"   Price: {tour.get('price', 'N/A')}")
        if "duration" in tour:
            print(f"   Duration: {tour['duration']}")
        print()

    print("=" * 80 + "\n")
    return tours_sorted


def display_closest_tour(your_location, tours):
    """Display the closest tour."""
    if not tours:
        print("❌ No tours found")
        return

    tours_sorted = sorted(tours, key=lambda x: x["distance_km"])
    closest = tours_sorted[0]

    print("\n" + "=" * 80)
    print("🎫 CLOSEST TOUR TO YOU")
    print("=" * 80)
    print(f"Your Location: {your_location['city']}, "
          f"{your_location['country']}")
    print(f"Your GPS: {your_location['latitude']: .4f}, "
          f"{your_location['longitude']: .4f}")
    print("-" * 80)
    print(f"Tour Name: {closest['name']}")
    print(f"Type: {closest.get('type', 'N/A')}")
    print(f"Distance: {closest['distance_km']} km away")
    print(f"Price: {closest.get('price', 'N/A')}")
    if "duration" in closest:
        print(f"Duration: {closest['duration']}")
    print(f"GPS: {closest['latitude']: .4f}, {closest['longitude']: .4f}")
    print("=" * 80 + "\n")


# Main execution
if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("█ TOURIST INFORMATION API TEST")
    print("█ Find tours and activities near your location")
    print("█" * 80 + "\n")

    your_location = get_current_location()
    print(f"📍 Location: {your_location['city']}, {your_location['country']}")
    print(f"   GPS: {your_location['latitude']: .4f}, "
          f"{your_location['longitude']: .4f}\n")

    tours = get_sample_tours(
        your_location["latitude"],
        your_location["longitude"]
    )

    display_closest_tour(your_location, tours)

    print("📍 Filtering tours by radius...\n")
    display_tours(your_location, tours, radius_km=2.0)

    print("📍 Trying larger radius (5km)...\n")
    display_tours(your_location, tours, radius_km=5.0)
