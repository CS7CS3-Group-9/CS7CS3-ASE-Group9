import requests


def get_air_quality(latitude, longitude):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ("pm2_5,pm10,nitrogen_dioxide,carbon_monoxide,ozone," "sulphur_dioxide,european_aqi"),
    }
    response = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params)
    return response.json()
