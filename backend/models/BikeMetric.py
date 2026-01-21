from mobility_snapshot import MobilitySnapshot
import requests
import math

DUBLIN_AREAS = {
    "city_center": {"lat": 53.3498, "lon": -6.2603, "radius_km": 0.5},
    "temple_bar": {"lat": 53.3441, "lon": -6.2660, "radius_km": 0.3},
    "south_side": {"lat": 53.3315, "lon": -6.2595, "radius_km": 1.0},
    "north_side": {"lat": 53.3576, "lon": -6.2452, "radius_km": 1.0},
    "docklands": {"lat": 53.3454, "lon": -6.2290, "radius_km": 0.8},
    "ballsbridge": {"lat": 53.3281, "lon": -6.2210, "radius_km": 0.7},
    "ranelagh": {"lat": 53.3230, "lon": -6.2732, "radius_km": 0.6},
}


class StationMetrics:
    def __init__(self, name, free_bikes, empty_slots, total_spaces):
        self.name = name
        self.free_bikes = free_bikes
        self.empty_slots = empty_slots
        self.total_spaces = total_spaces
        self.availability_percent = (free_bikes / total_spaces * 100) if total_spaces > 0 else 0

    def __repr__(self):
        return (
            f"StationMetrics(name={self.name}, bikes={self.free_bikes}, "
            f"slots={self.empty_slots}, total={self.total_spaces}, "
            f"availability={self.availability_percent: .1f}%)"
        )


class BikeMetrics:
    def __init__(self, available_bikes, available_docks, stations_reporting):
        self.available_bikes = available_bikes
        self.available_docks = available_docks
        self.stations_reporting = stations_reporting

    def __repr__(self):
        return (
            f"BikeMetrics(bikes={self.available_bikes}, "
            f"docks={self.available_docks}, "
            f"stations={self.stations_reporting})"
        )


def get_station_metrics(station):
    """Get metrics for a single station."""
    return StationMetrics(
        name=station["name"],
        free_bikes=station["free_bikes"],
        empty_slots=station["empty_slots"],
        total_spaces=station["total_spaces"],
    )


def calculate_area_metrics(station_metrics_list):
    """Calculate aggregated BikeMetrics from a list of StationMetrics."""
    if not station_metrics_list:
        return BikeMetrics(0, 0, 0)

    total_bikes = sum(sm.free_bikes for sm in station_metrics_list)
    total_docks = sum(sm.empty_slots for sm in station_metrics_list)
    stations_reporting = len(station_metrics_list)

    return BikeMetrics(total_bikes, total_docks, stations_reporting)


def find_stations_in_area(area_name, return_metrics=False):
    """Find stations in an area. If return_metrics=True, returns StationMetrics objects."""
    area = DUBLIN_AREAS[area_name]
    stations = get_all_stations()

    if not stations:
        print("Could not fetch stations")
        return None

    nearby = []
    for station in stations:
        distance = calculate_distance(area["lat"], area["lon"], station["latitude"], station["longitude"])
        if distance <= area["radius_km"]:
            nearby.append(
                {
                    "name": station["name"],
                    "free_bikes": station["free_bikes"],
                    "empty_slots": station["empty_slots"],
                    "total_spaces": station["extra"]["slots"],
                    "latitude": station["latitude"],
                    "longitude": station["longitude"],
                }
            )

    nearby.sort(key=lambda x: x["free_bikes"], reverse=True)

    if return_metrics:
        station_metrics = [get_station_metrics(station) for station in nearby]
        area_metrics = calculate_area_metrics(station_metrics)
        return {"station_metrics": station_metrics, "area_metrics": area_metrics, "stations": nearby}

    return nearby


def get_all_stations():
    """Fetch all Dublin Bike stations and their availability."""
    url = "https://api.citybik.es/v2/networks/dublinbikes"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["network"]["stations"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching stations: {e}")
        return None


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


def find_closest_station(your_latitude, your_longitude):
    """Find the closest bike station to your current location."""
    stations = get_all_stations()
    if not stations:
        print("Could not fetch stations")
        return None

    stations_with_distance = []
    for station in stations:
        distance = calculate_distance(your_latitude, your_longitude, station["latitude"], station["longitude"])
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


def display_area_stations(area_name, result):
    """Display all stations in an area with availability and metrics."""
    if not result or not result["stations"]:
        print(f"\nNo stations found in {area_name}")
        return

    area_display = area_name.replace("_", " ").title()
    print("\n" + "=" * 90)
    print(f"DUBLIN BIKES IN {area_display.upper()}")
    print("=" * 90)
    print(f"Found {len(result['stations'])} stations\n")

    # Display area metrics summary
    area_metrics = result["area_metrics"]
    print(f"AREA METRICS: ")
    print(f"  Total Bikes Available: {area_metrics.available_bikes}")
    print(f"  Total Empty Slots: {area_metrics.available_docks}")
    print(f"  Stations Reporting: {area_metrics.stations_reporting}\n")

    # Display individual stations with their metrics
    for i, station_metric in enumerate(result["station_metrics"], 1):
        print(
            f"{i}. {station_metric.name: <50} | "
            f"Bikes: {station_metric.free_bikes: >2} | "
            f"Slots: {station_metric.empty_slots: >2} | "
            f"Total: {station_metric.total_spaces: >2} | "
            f"Avail: {station_metric.availability_percent: >5.1f}%"
        )
    print("=" * 90 + "\n")


if __name__ == "__main__":
    print("█ DUBLIN BIKES FINDER")

    # Example: Find bikes in City Center with metrics
    area = "city_center"
    print(f"Searching for bikes in {area.replace('_', ' ').title()}...\n")
    result = find_stations_in_area(area, return_metrics=True)
    display_area_stations(area, result)

    # Access individual station metrics
    print("Individual Station Metrics:")
    for station_metric in result["station_metrics"]:
        print(f"  {station_metric}")

    print(f"\nArea Metrics: {result['area_metrics']}")
