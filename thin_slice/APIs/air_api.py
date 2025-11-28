import requests


def get_current_location():
    """Get your current location."""
    try:
        response = requests.get("http://ip-api.com/json/")
        data = response.json()
        return {
            "latitude": data["lat"],
            "longitude": data["lon"],
            "city": data["city"],
        }
    except Exception:
        return {
            "latitude": 53.3498,
            "longitude": -6.2603,
            "city": "Dublin",
        }


def get_air_quality(latitude, longitude):
    """
    Fetch air quality and emissions data using Open-Meteo API.
    Returns: PM2.5, PM10, NO2, CO, O3, and other pollutants.
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "pm2_5,pm10,nitrogen_dioxide,carbon_monoxide,ozone,"
            "sulphur_dioxide,european_aqi"
        ),
    }

    try:
        print("📡 Fetching air quality data...\n")
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        print(f"Error fetching air quality: {error}")
        return None


def get_aqi_level(aqi_value):
    """Interpret AQI level."""
    if aqi_value <= 25:
        return "Good"
    if aqi_value <= 50:
        return "Fair"
    if aqi_value <= 75:
        return "Moderate"
    if aqi_value <= 100:
        return "Poor"
    return "Very Poor"


def display_air_quality(location, air_data):
    """Display air quality information."""
    if not air_data or "current" not in air_data:
        print("Could not fetch air quality data")
        return

    current = air_data["current"]

    print("\n" + "=" * 80)
    print(f"AIR QUALITY & EMISSIONS DATA - {location['city'].upper()}")
    print("=" * 80)
    print(f"Location: {location['latitude']: .4f}, " f"{location['longitude']: .4f}\n")

    # AQI
    aqi_value = current.get("european_aqi", 0)
    aqi_level = get_aqi_level(aqi_value)

    print("EUROPEAN AIR QUALITY INDEX (AQI)")
    print(f"   AQI Level: {aqi_level} ({aqi_value})\n")

    # PM levels
    print("PARTICULATE MATTER (PM)")
    pm25 = current.get("pm2_5", 0)
    pm10 = current.get("pm10", 0)

    print(f"   PM2.5 (fine): {pm25: .1f} µg/m³")
    print(f"   PM10 (coarse): {pm10: .1f} µg/m³")

    if pm25 <= 12:
        print("   PM2.5 within WHO guidelines (< 12 µg/m³)")
    else:
        print("   PM2.5 above WHO guidelines (> 12 µg/m³)")

    # Gases
    print("\nGASEOUS POLLUTANTS (EMISSIONS)")
    no2 = current.get("nitrogen_dioxide", 0)
    co = current.get("carbon_monoxide", 0)
    o3 = current.get("ozone", 0)
    so2 = current.get("sulphur_dioxide", 0)

    print(f"   NO₂ (Nitrogen Dioxide): {no2: .1f} µg/m³")
    print(f"   CO (Carbon Monoxide): {co: .1f} µg/m³")
    print(f"   O₃ (Ozone): {o3: .1f} µg/m³")
    print(f"   SO₂ (Sulphur Dioxide): {so2: .1f} µg/m³")

    # Health recommendations
    print("\nHEALTH RECOMMENDATIONS")
    if aqi_level == "Good":
        print("   Air quality is satisfactory - enjoy outdoor activities")
    elif aqi_level == "Fair":
        print(
            "   Air quality is acceptable - sensitive groups may "
            "experience minor effects"
        )
    elif aqi_level == "Moderate":
        print("   Air quality is unhealthy for sensitive groups")
        print(
            "      • Limit outdoor activities for children, elderly, and "
            "people with respiratory conditions"
        )
    elif aqi_level == "Poor":
        print("   Air quality is unhealthy for the general population")
        print("      • Everyone should limit prolonged outdoor activities")
    else:
        print("   Air quality is hazardous")
        print("      • Avoid outdoor activities")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    print("\n" + "" * 80)
    print("█ AIR QUALITY & EMISSIONS TRACKER")
    print("█ Dublin Air Pollution Monitoring")
    print("█ Data from Open-Meteo (Free, No API Key Required)")
    print("█" * 80 + "\n")

    print("Getting your location...\n")
    location = get_current_location()

    print(f"Location: {location['city']}")
    print(f"   GPS: {location['latitude']: .4f}, " f"{location['longitude']: .4f}\n")

    air_data = get_air_quality(
        location["latitude"],
        location["longitude"],
    )

    if air_data:
        display_air_quality(location, air_data)
        print("✓ Air quality data successfully fetched\n")
    else:
        print("Failed to fetch air quality data\n")
