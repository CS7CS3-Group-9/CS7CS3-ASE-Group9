from __future__ import annotations

from backend.adapters.base_adapter import DataAdapter
from backend.adapters.airquality_adapter import AirQualityAdapter
from backend.models.mobility_snapshot import MobilitySnapshot


class AirQualityLocationAdapter(DataAdapter):
    """
    Wrapper so AirQualityAdapter can be used with SnapshotService, which calls:
        adapter.fetch(location=..., **kwargs)

    AirQualityAdapter expects:
        fetch(latitude, longitude) -> AirQualitySnapshot
    """

    def __init__(self):
        self._inner = AirQualityAdapter()

    def source_name(self) -> str:
        return self._inner.source_name()  # "airquality"

    def fetch(
        self,
        location: str = "dublin",
        latitude: float | None = None,
        longitude: float | None = None,
        **kwargs,
    ) -> MobilitySnapshot:
        if latitude is None or longitude is None:
            raise ValueError("Air quality requires latitude and longitude")

        aq_snapshot = self._inner.fetch(latitude=latitude, longitude=longitude)

        return MobilitySnapshot(
            timestamp=aq_snapshot.timestamp,
            location=location,
            airquality=aq_snapshot.metrics,  # AirQualityMetrics
        )
