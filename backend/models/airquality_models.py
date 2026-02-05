class AirQualityMetrics:
    def __init__(self, area: str, aqi: float, status: str = None):
        self.area = area  # e.g., "city center"
        self.aqi = aqi  # european_aqi number
        self.status = status  # computed by analytics
