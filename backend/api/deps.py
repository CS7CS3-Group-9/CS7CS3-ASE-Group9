from backend.adapters.bikes_adapter import BikesAdapter
from backend.adapters.traffic_adapter import TrafficAdapter
from backend.adapters.airquality_adapter import AirQualityAdapter
from backend.adapters.tour_adapter import TourAdapter


def build_adapters():
    return {
        "bikes": BikesAdapter(),
        "traffic": TrafficAdapter(),
        "airquality": AirQualityAdapter(),
        "tours": TourAdapter(),
    }
