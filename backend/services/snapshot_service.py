from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from backend.models.mobility_snapshot import MobilitySnapshot

# Import analytics you already have (adjust names if yours differ)
from backend.analytics.traffic_analytics import build_traffic_metrics
from backend.analytics.airquality_analytics import overall_air_quality_level
from backend.fallback.cache import AdapterCache
from backend.fallback.resolver import resolve_with_cache


@dataclass
class AdapterCallSpec:
    """
    Optional per-adapter call config.
    Allows SnapshotService to call adapters without hardcoding parameters.
    """

    adapter: Any
    kwargs: Dict[str, Any]
    cache_ttl_seconds: float | None = None


class SnapshotService:
    """
    - Calls multiple adapters
    - Merges outputs into one MobilitySnapshot
    - Sets source_status (live/failed)
    - Runs analytics to compute derived fields
    """

    def __init__(
        self,
        adapters: Iterable[Any] | None = None,
        adapter_specs: Iterable[AdapterCallSpec] | None = None,
        cache: AdapterCache | None = None,
        predictor: Callable[..., Optional[Any]] | None = None,
    ):
        """
        Provide either:
          - adapters: list of adapters with fetch(location=...) and source_name()
          OR
          - adapter_specs: list of AdapterCallSpec for per-adapter kwargs
        """
        self._adapters = list(adapters) if adapters else []
        self._adapter_specs = list(adapter_specs) if adapter_specs else []
        self._cache = cache
        self._predictor = predictor

        if self._adapters and self._adapter_specs:
            raise ValueError("Provide either adapters OR adapter_specs, not both.")

        if not self._adapters and not self._adapter_specs:
            raise ValueError("SnapshotService requires at least one adapter.")

    def build_snapshot(self, location: str = "dublin") -> MobilitySnapshot:
        snapshot = MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=location,
            source_status={},
        )

        adapter_list = list(self._iter_adapters_with_kwargs())

        def _fetch_one(adapter_kwargs: Tuple[Any, Dict, float | None]) -> Tuple[str, Any, str]:
            """Fetch a single adapter; returns (name, partial_snapshot, status)."""
            adapter, kwargs, ttl_seconds = adapter_kwargs
            name = self._safe_source_name(adapter)
            if self._cache is None:
                try:
                    partial = adapter.fetch(location=location, **kwargs)
                    return name, partial, "live"
                except Exception:
                    return name, None, "failed"
            else:
                try:
                    result = resolve_with_cache(
                        adapter,
                        self._cache,
                        predictor=self._predictor,
                        max_age_seconds=ttl_seconds,
                        location=location,
                        **kwargs,
                    )
                    return name, result.snapshot, result.status
                except Exception:
                    return name, None, "failed"

        # Fetch all adapters concurrently then merge sequentially (thread-safe)
        n_workers = max(1, len(adapter_list))
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            results = list(pool.map(_fetch_one, adapter_list))

        for name, partial, status in results:
            if partial is not None:
                self._merge(snapshot, partial)
            snapshot.source_status[name] = status

        # After merging raw data, compute derived indicators
        self._apply_analytics(snapshot)

        return snapshot

    def _iter_adapters_with_kwargs(self) -> Iterable[Tuple[Any, Dict[str, Any], float | None]]:
        if self._adapter_specs:
            for spec in self._adapter_specs:
                yield spec.adapter, spec.kwargs, spec.cache_ttl_seconds
        else:
            for adapter in self._adapters:
                yield adapter, {}, None

    def _safe_source_name(self, adapter: Any) -> str:
        try:
            return str(adapter.source_name())
        except Exception:
            return adapter.__class__.__name__

    def _merge(self, target: MobilitySnapshot, partial: MobilitySnapshot) -> None:
        """
        Merge non-None fields from partial into target.
        Rules:
          - If partial.<field> is not None, overwrite target.<field>
          - Never overwrite target.source_status here (service owns it)
          - Location/time remain those of the unified snapshot (service owns it)
        """
        if partial is None:
            return

        # Merge known MobilitySnapshot fields
        if getattr(partial, "bikes", None) is not None:
            target.bikes = partial.bikes

        if getattr(partial, "buses", None) is not None:
            target.buses = partial.buses

        if getattr(partial, "traffic", None) is not None:
            target.traffic = partial.traffic

        if getattr(partial, "airquality", None) is not None:
            target.airquality = partial.airquality

        if getattr(partial, "population", None) is not None:
            target.population = partial.population

        if getattr(partial, "tours", None) is not None:
            target.tours = partial.tours

        if getattr(partial, "alerts", None) is not None:
            target.alerts = partial.alerts

        if getattr(partial, "recommendations", None) is not None:
            target.recommendations = partial.recommendations

    def _apply_analytics(self, snapshot: MobilitySnapshot) -> None:
        """
        Convert raw adapter outputs into computed metrics / categories.
        Keep this lightweight and deterministic.
        """

        # --- TRAFFIC ---
        # Adapter returns list[TrafficIncident]; analytics converts -> TrafficMetrics
        if isinstance(snapshot.traffic, list):
            # radius_km is not in MobilitySnapshot (good). Use a default,
            # OR pass radius through AdapterCallSpec kwargs and store it elsewhere later.
            # For now, use a sensible default.
            snapshot.traffic = build_traffic_metrics(snapshot.traffic, radius_km=1.0)

        # --- AIR QUALITY ---
        # If your adapter returns AirQualityMetrics(aqi_value=..., pollutants=...)
        # compute an overall status string and attach to the model if you have that field.
        if snapshot.airquality is not None:
            try:
                # If your AirQualityMetrics model has a 'status' attribute, set it.
                status = overall_air_quality_level(snapshot.airquality)
                if hasattr(snapshot.airquality, "status"):
                    snapshot.airquality.status = status
            except Exception:
                # Analytics should never crash snapshot building
                pass

        # Add more analytics hooks here as you implement them:
        # - bikes critical occupancy stations
        # - tour counts by type
        # - cross-domain correlations
        # - recommendations
