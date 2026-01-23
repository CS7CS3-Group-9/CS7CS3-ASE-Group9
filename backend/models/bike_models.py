class StationMetrics:
    def __init__(self, name, free_bikes, empty_slots, total_spaces):
        self.name = name
        self.free_bikes = free_bikes
        self.empty_slots = empty_slots
        self.total_spaces = total_spaces
        self.availability_percent = free_bikes / total_spaces * 100 if total_spaces > 0 else 0


class BikeMetrics:
    def __init__(self, available_bikes, available_docks, stations_reporting):
        self.available_bikes = available_bikes
        self.available_docks = available_docks
        self.stations_reporting = stations_reporting
