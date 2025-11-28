import requests


def get_current_location():
    """Get your current location."""
    try:
        response = requests.get("http://ip-api.com/json/")
        data = response.json()
        return {"latitude": data["lat"], "longitude": data["lon"], "city": data["city"]}
    except Exception:
        print("Using generic Dublin location")
        return {"latitude": 53.3498, "longitude": -6.2603, "city": "Dublin"}


def get_weather(latitude, longitude):
    """Fetch weather data for your location."""
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,wind_speed_10m,rain,cloud_cover",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data["current"]

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather: {e}")
        return None


def display_weather(location, weather):
    """Display weather in a simple format."""
    if not weather:
        print("Could not fetch weather data")
        return

    print("\n" + "=" * 60)
    print(f"WEATHER FOR {location['city'].upper()}")
    print("=" * 60)
    print(f"GPS: {location['latitude']}, {location['longitude']}\n")

    print(f"Temperature: {weather['temperature_2m']}°C")
    print(f"Wind Speed (10m): {weather['wind_speed_10m']} km/h")
    print(f"Rain Amount: {weather['rain']} mm")
    print(f"Cloud Cover: {weather['cloud_cover']}%")

    print("=" * 60 + "\n")


# Main execution
if __name__ == "__main__":
    print("\nGetting your location...\n")
    location = get_current_location()
    print(f"Location: {location['city']}")

    print("\nFetching weather data...\n")
    weather = get_weather(location["latitude"], location["longitude"])

    display_weather(location, weather)
