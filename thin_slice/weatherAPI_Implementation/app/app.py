from flask import Flask, render_template, jsonify
import os
import requests
import redis
import json
import paho.mqtt.client as mqtt
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

# Initialize Redis
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=6379,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    redis_client.ping()
    print("✅ Redis connected")
except:
    redis_client = None
    print("⚠️ Redis not available - running without cache")

# Initialize MQTT
try:
    mqtt_client = mqtt.Client()
    mqtt_client.connect(os.getenv("MQTT_BROKER", "localhost"), 1883, 60)
    mqtt_client.loop_start()
    print("✅ MQTT connected")
except:
    mqtt_client = None
    print("⚠️ MQTT not available - running without messaging")

# Initialize Firebase
try:
    if os.path.exists("firebase-key.json"):
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase connected")
    else:
        db = None
        print("⚠️ Firebase key not found - running without database")
except:
    db = None
    print("⚠️ Firebase not available - running without database")


def fetch_weather_data():
    """Fetch weather from OpenWeatherMap API"""
    api_key = os.getenv("WEATHER_API_KEY")

    if not api_key:
        # Return mock data for demo
        return {
            "city": "Dublin",
            "temperature": 12,
            "condition": "Cloudy",
            "timestamp": datetime.now().isoformat(),
            "source": "mock_data",
        }

    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Dublin,IE&appid={api_key}&units=metric"
        response = requests.get(url, timeout=5)
        data = response.json()

        return {
            "city": data["name"],
            "temperature": round(data["main"]["temp"]),
            "condition": data["weather"][0]["description"].title(),
            "timestamp": datetime.now().isoformat(),
            "source": "openweathermap_api",
        }
    except:
        # Fallback to mock data
        return {
            "city": "Dublin",
            "temperature": 12,
            "condition": "Cloudy",
            "timestamp": datetime.now().isoformat(),
            "source": "fallback_mock_data",
        }


@app.route("/")
def index():
    """Main page - demonstrates full integration flow"""

    # Step 1: Check Redis cache
    cache_hit = False
    if redis_client:
        try:
            cached_data = redis_client.get("weather_data")
            if cached_data:
                weather_data = json.loads(cached_data)
                weather_data["from_cache"] = True
                cache_hit = True
                print("📦 Data retrieved from cache")
        except:
            pass

    # Step 2: If no cache, fetch from API
    if not cache_hit:
        weather_data = fetch_weather_data()
        weather_data["from_cache"] = False
        print(f"🌐 Data fetched from {weather_data['source']}")

        # Step 3: Store in Redis cache (60 seconds TTL for demo)
        if redis_client:
            try:
                redis_client.setex("weather_data", 60, json.dumps(weather_data))
                print("💾 Data cached in Redis")
            except:
                pass

        # Step 4: Store in Firebase
        if db:
            try:
                db.collection("weather_logs").add(
                    {**weather_data, "stored_at": firestore.SERVER_TIMESTAMP}
                )
                print("🔥 Data stored in Firebase")
            except:
                pass

        # Step 5: Send MQTT alert if temperature extreme
        if mqtt_client and (
            weather_data["temperature"] < 0 or weather_data["temperature"] > 25
        ):
            try:
                alert_msg = {
                    "alert": "Extreme temperature detected!",
                    "temperature": weather_data["temperature"],
                    "city": weather_data["city"],
                }
                mqtt_client.publish("weather/alerts", json.dumps(alert_msg))
                print("📢 MQTT alert sent")
            except:
                pass

    # Component status
    status = {
        "redis": redis_client is not None,
        "mqtt": mqtt_client is not None,
        "firebase": db is not None,
    }

    return render_template("index.html", weather=weather_data, status=status)


@app.route("/api/weather")
def api_weather():
    """REST API endpoint"""
    if redis_client:
        cached = redis_client.get("weather_data")
        if cached:
            return jsonify(json.loads(cached))

    weather_data = fetch_weather_data()
    return jsonify(weather_data)


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "components": {
                "redis": redis_client is not None,
                "mqtt": mqtt_client is not None,
                "firebase": db is not None,
            },
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
