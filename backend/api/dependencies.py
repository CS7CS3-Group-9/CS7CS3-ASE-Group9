from adapters.bikes_adapter import BikesAdapter
from adapters.traffic_adapter import TrafficAdapter
from adapters.airquality_adapter import AirQualityAdapter
from adapters.tour_adapter import TourAdapter


def build_adapters():
    return {
        "bikes": BikesAdapter(),
        "traffic": TrafficAdapter(),
        "airquality": AirQualityAdapter(),
        "tours": TourAdapter(),
    }
