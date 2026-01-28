import requests
from datetime import datetime
from backend.adapters.base_adapter import DataAdapter
from backend.models.tour_models import Attraction, AttractionMetrics, TourSnapshot


class TourAdapter(DataAdapter):
    """
    Adapter for Overpass API (OpenStreetMap)
    Fetches tourist attractions in a given area
    """
    
    def __init__(self):
        self.base_url = "https://overpass-api.de/api/interpreter"
    
    def source_name(self) -> str:
        return "tour"
    
    def fetch(self, location: str, radius_km: float = 5) -> TourSnapshot:
        """
        Fetch tourist attractions from Overpass API
        
        Args:
            location: Location name (city, area)
            radius_km: Search radius in kilometers (default: 5km)
            
        Returns:
            TourSnapshot object with attractions and metrics
        """
        # TODO: Build Overpass query
        # Need to:
        # 1. Geocode location name to lat/lon
        # 2. Build Overpass QL query for tourism attractions within radius
        # 3. Execute query
        
        # overpass_query = f"""
        # [out:json];
        # (
        #   node["tourism"](around:{radius_km * 1000},{lat},{lon});
        #   way["tourism"](around:{radius_km * 1000},{lat},{lon});
        # );
        # out center;
        # """
        
        # TODO: Make API request
        # response = requests.post(self.base_url, data=overpass_query, timeout=30)
        # response.raise_for_status()
        # data = response.json()
        
        # TODO: Parse attractions
        # attractions = []
        # for element in data.get("elements", []):
        #     # Extract coordinates (different for nodes vs ways)
        #     if element["type"] == "node":
        #         lat = element["lat"]
        #         lon = element["lon"]
        #     else:  # way
        #         lat = element.get("center", {}).get("lat")
        #         lon = element.get("center", {}).get("lon")
        #     
        #     tags = element.get("tags", {})
        #     
        #     # Determine attraction type
        #     attraction_type = tags.get("tourism")
        #     if not attraction_type:
        #         attraction_type = tags.get("historic", tags.get("leisure", "attraction"))
        #     
        #     attraction = Attraction(
        #         attraction_id=element["id"],
        #         attraction_name=tags.get("name", "Unnamed"),
        #         attraction_type=attraction_type,
        #         latitude=lat,
        #         longitude=lon,
        #         open_times=tags.get("opening_hours"),
        #         price=tags.get("fee"),
        #         website=tags.get("website"),
        #         phone=tags.get("phone"),
        #         wheelchair_accessible=tags.get("wheelchair"),
        #         tags=tags
        #     )
        #     attractions.append(attraction)
        
        # TODO: Calculate metrics
        # total = len(attractions)
        # free_count = sum(1 for a in attractions if a.price == "no")
        # paid_count = sum(1 for a in attractions if a.price == "yes")
        # wheelchair_count = sum(1 for a in attractions if a.wheelchair_accessible == "yes")
        # 
        # # Count by type
        # by_type = {}
        # for a in attractions:
        #     by_type[a.attraction_type] = by_type.get(a.attraction_type, 0) + 1
        # 
        # metrics = AttractionMetrics(
        #     total_attractions=total,
        #     attractions_by_type=by_type,
        #     free_attractions_count=free_count,
        #     paid_attractions_count=paid_count,
        #     wheelchair_accessible_count=wheelchair_count,
        #     attractions=attractions
        # )
        # 
        # return TourSnapshot(
        #     location=location,
        #     search_radius_km=radius_km,
        #     timestamp=datetime.utcnow(),
        #     metrics=metrics,
        #     source_status={"overpass": "live"}
        # )
        
        raise NotImplementedError("Tour fetching not yet implemented")