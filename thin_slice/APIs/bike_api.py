import json
import math
import requests


def find_closest_station(your_latitude, your_longitude):
    """Find the closest bike station to your current location."""
    stations = get_all_stations()
    if not stations:
        print("❌ Could not fetch stations")
        return None

    stations_with_distance = []
    for station in stations:
        distance = calculate_distance(
            your_latitude, your_longitude, station["latitude"], station["longitude"]
        )
        stations_with_distance.append(
            {
                "name": station["name"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "free_bikes": station["free_bikes"],
                "empty_slots": station["empty_slots"],
                "total_spaces": station["extra"]["slots"],
                "distance_km": distance,
            }
        )

    stations_with_distance.sort(key=lambda x: x["distance_km"])
    return stations_with_distance[0]


def display_closest_station(station, your_location):
    """Display the closest station information."""
    if not station:
        return

    print("\n" + "=" * 60)
    print("📍 CLOSEST BIKE STATION TO YOU")
    print("=" * 60)
    print(f"Your Location: {your_location['city']}, " f"{your_location['country']}")
    print(
        f"Your GPS: {your_location['latitude']: .4f}, "
        f"{your_location['longitude']: .4f}"
    )
    print("-" * 60)
    print(f"🚲 Station: {station['name']}")
    print(f"📏 Distance: {station['distance_km']: .2f} km")
    print(f"🧭 GPS: {station['latitude']: .4f}, {station['longitude']: .4f}")
    print(f"🚴 Bikes Available: {station['free_bikes']}")
    print(f"📭 Empty Spaces: {station['empty_slots']}")
    print(f"🅿️  Total Spaces: {station['total_spaces']}")

    availability = (
        station["free_bikes"] / station["total_spaces"] * 100
        if station["total_spaces"] > 0
        else 0
    )
    print(f"📊 Availability: {availability: .1f}%")
    print("=" * 60 + "\n")


def list_nearby_stations(your_latitude, your_longitude, radius_km=1.0):
    """List all stations within a certain radius of your location."""
    stations = get_all_stations()
    if not stations:
        print("❌ Could not fetch stations")
        return

    nearby = []
    for station in stations:
        distance = calculate_distance(
            your_latitude, your_longitude, station["latitude"], station["longitude"]
        )
        if distance <= radius_km:
            nearby.append(
                {
                    "name": station["name"],
                    "distance_km": distance,
                    "free_bikes": station["free_bikes"],
                    "total_spaces": station["extra"]["slots"],
                }
            )

    nearby.sort(key=lambda x: x["distance_km"])
    print(f"\n📍 STATIONS WITHIN {radius_km} KM OF YOU\n")
    print(f"Found {len(nearby)} stations: \n")

    for i, station in enumerate(nearby, 1):
        print(
            f"{i}. {station['name']: <45} | "
            f"{station['distance_km']: .2f} km | "
            f"Bikes: {station['free_bikes']: >2}"
        )

    print()
    return nearby


def list_all_stations():
    """List all Dublin Bikes stations with availability."""
    print("\n🚲 ALL DUBLIN BIKES STATIONS\n")
    stations = get_all_stations()
    if not stations:
        print("❌ Could not fetch stations")
        return

    print(f"Total Stations: {len(stations)}\n")
    for i, station in enumerate(stations, 1):
        print(
            f"{i}. {station['name']: <50} | "
            f"Bikes: {station['free_bikes']: >2} | "
            f"Spaces: {station['extra']['slots']: >2}"
        )
    print()


def get_current_location():
    """Detect your current location using IP geolocation."""
    response = requests.get("http://ip-api.com/json/")
    data = response.json()
    return {
        "latitude": data["lat"],
        "longitude": data["lon"],
        "city": data["city"],
        "country": data["country"],
    }


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates using Haversine."""
    R = 6371  # Earth's radius in km
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


def get_all_stations():
    """Fetch all Dublin Bike stations and their availability."""
    url = "https://api.citybik.es/v2/networks/dublinbikes"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["network"]["stations"]
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching stations: {e}")
        return None


def find_station_by_name(station_name):
    """Find a specific station by name and show bike availability."""
    stations = get_all_stations()
    if not stations:
        print("❌ Could not fetch stations")
        return None

    for station in stations:
        if station_name.lower() in station["name"].lower():
            return station

    print(f"❌ Station '{station_name}' not found")
    return None


def display_station_info(station):
    """Display station information in a nice format."""
    if not station:
        return

    print("\n" + "=" * 60)
    print(f"🚲 STATION: {station['name']}")
    print("=" * 60)
    print(f"📍 Location: {station['latitude']}, {station['longitude']}")
    print(f"🅿️  Total Spaces: {station['extra']['slots']}")
    print(f"🚴 Bikes Available: {station['free_bikes']}")
    print(f"📭 Empty Spaces: {station['empty_slots']}")

    total_spaces = station["extra"]["slots"]
    availability = station["free_bikes"] / total_spaces * 100 if total_spaces > 0 else 0
    print(f"📊 Availability: {availability: .1f}%")
    print("=" * 60 + "\n")

    return {
        "name": station["name"],
        "bikes_available": station["free_bikes"],
        "total_spaces": total_spaces,
        "empty_spaces": station["empty_slots"],
        "availability_percent": round(availability, 1),
        "latitude": station["latitude"],
        "longitude": station["longitude"],
    }


# Main execution
if __name__ == "__main__":
    print("\n" + "█" * 60)
    print("█ DUBLIN BIKES API TEST")
    print("█ Find closest bike station to your location")
    print("█" * 60 + "\n")

    print("🌍 Getting your current location...\n")
    your_location = get_current_location()
    print(f"📍 You are in: {your_location['city']}, " f"{your_location['country']}")
    print(
        f"   GPS: {your_location['latitude']: .4f}, "
        f"{your_location['longitude']: .4f}\n"
    )

    print("🔍 Finding closest bike station...\n")
    closest = find_closest_station(
        your_location["latitude"], your_location["longitude"]
    )
    display_closest_station(closest, your_location)

    print("📍 Stations within 1km of you:\n")
    list_nearby_stations(
        your_location["latitude"], your_location["longitude"], radius_km=5
    )
