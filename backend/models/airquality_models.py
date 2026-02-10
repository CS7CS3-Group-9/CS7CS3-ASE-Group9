class PollutantLevels:
    """Individual pollutant measurements"""

    def __init__(self, pm2_5, pm10, nitrogen_dioxide, carbon_monoxide, ozone, sulphur_dioxide, units):
        self.pm2_5 = pm2_5  # Particulate matter ≤2.5μm
        self.pm10 = pm10  # Particulate matter ≤10μm
        self.nitrogen_dioxide = nitrogen_dioxide  # NO₂
        self.carbon_monoxide = carbon_monoxide  # CO
        self.ozone = ozone  # O₃
        self.sulphur_dioxide = sulphur_dioxide  # SO₂
        self.units = units  # Dict of units for each pollutant


class AirQualityMetrics:
    """Air quality metrics - raw data only"""

    def __init__(self, aqi_value, pollutants):
        self.aqi_value = aqi_value  # European air quality index score (raw number)
        self.pollutants = pollutants  # PollutantLevels object


class AirQualitySnapshot:
    """Snapshot of air quality data for a location"""

    def __init__(self, latitude, longitude, elevation, timezone, timestamp, metrics, source_status):
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.timezone = timezone
        self.timestamp = timestamp
        self.metrics = metrics  # AirQualityMetrics object
        self.source_status = source_status  # {"open-meteo": "live"}
