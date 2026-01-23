import requests
import json


def Current_location():
    response = requests.get("http://ip-api.com/json/")
    data = response.json()
    print("current location api:", data)
    return data
