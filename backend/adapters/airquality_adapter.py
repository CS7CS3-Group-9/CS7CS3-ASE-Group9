import requests
from datetime import datetime
from backend.adapters.base_adapter import DataAdapter
from backend.models.airquality_models import PollutantLevels, AirQualityMetrics, AirQualitySnapshot


class AirQualityAdapter(DataAdapter):
    """
    Adapter for Open-Meteo Air Quality API
    Fetches air quality data including pollutants and AQI
    """
    
    def __init__(self):
        self.base_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    
    def source_name(self) -> str:
        return "airquality"
    
    def fetch(self, latitude: float, longitude: float) -> AirQualitySnapshot:
        """
        Fetch air quality data from Open-Meteo API
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            AirQualitySnapshot object with air quality data and metrics
        """
        # Make API request
        response = self._make_api_request(latitude, longitude)
        
        # Parse the response
        data = response.json()
        
        # Validate required fields
        if "current" not in data:
            raise KeyError("Missing required field: 'current'")
        
        # Extract location info
        lat = data.get("latitude", latitude)
        lng = data.get("longitude", longitude)
        elevation = data.get("elevation", 0.0)
        timezone = data.get("timezone", "UTC")
        
        # Parse pollutants
        pollutants = self._parse_pollutants(
            data["current"],
            data.get("current_units", {})
        )
        
        # Get AQI value
        aqi_value = data["current"].get("european_aqi", 0)
        
        # Calculate metrics
        metrics = self._calculate_metrics(aqi_value, pollutants)
        
        # Parse timestamp
        timestamp_str = data["current"].get("time")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.utcnow()
        
        # Create and return snapshot
        return AirQualitySnapshot(
            latitude=lat,
            longitude=lng,
            elevation=elevation,
            timezone=timezone,
            timestamp=timestamp,
            metrics=metrics,
            source_status={"open-meteo": "live"}
        )
    
    def _make_api_request(self, latitude: float, longitude: float):
        """Make API request to Open-Meteo Air Quality API"""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm2_5,pm10,nitrogen_dioxide,carbon_monoxide,ozone,sulphur_dioxide,european_aqi"
        }
        
        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        
        return response
    
    def _parse_pollutants(self, current_data: dict, units_data: dict) -> PollutantLevels:
        """Parse pollutant data from API response"""
        return PollutantLevels(
            pm2_5=current_data.get("pm2_5", 0.0),
            pm10=current_data.get("pm10", 0.0),
            nitrogen_dioxide=current_data.get("nitrogen_dioxide", 0.0),
            carbon_monoxide=current_data.get("carbon_monoxide", 0.0),
            ozone=current_data.get("ozone", 0.0),
            sulphur_dioxide=current_data.get("sulphur_dioxide", 0.0),
            units={
                "pm2_5": units_data.get("pm2_5", "μg/m³"),
                "pm10": units_data.get("pm10", "μg/m³"),
                "nitrogen_dioxide": units_data.get("nitrogen_dioxide", "μg/m³"),
                "carbon_monoxide": units_data.get("carbon_monoxide", "μg/m³"),
                "ozone": units_data.get("ozone", "μg/m³"),
                "sulphur_dioxide": units_data.get("sulphur_dioxide", "μg/m³")
            }
        )
    
    def _calculate_metrics(self, aqi_value: int, pollutants: PollutantLevels) -> AirQualityMetrics:
        """Calculate air quality metrics from AQI and pollutants"""
        
        return AirQualityMetrics(
            aqi_value=aqi_value,
            pollutants=pollutants
        )