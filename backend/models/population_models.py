class PopulationMetrics:
    def __init__(self, area_name, latitude, longitude, quantity):
        self.area_name = area_name
        self.latitude = latitude  # latitude coordinate of the center of the area
        self.longitude = longitude  # longitude coordinate of the area
        self.quantity = quantity  # census population in this area
