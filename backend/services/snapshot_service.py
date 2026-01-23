# This files will:
#   - call multiple adapters
#   - merge their output
#   - handle partial failures
#   - return one MobilitySnapshot

from datetime import datetime
from backend.models.mobility_snapshot import MobilitySnapshot


class SnapshotService:
    def __init__(self, adapters: list):
        self.adapters = adapters

    def build_snapshot(self, location="dublin") -> MobilitySnapshot:
        snapshot = MobilitySnapshot(timestamp=datetime.utcnow(), location=location, source_status={})

        for adapter in self.adapters:
            try:
                partial = adapter.fetch(location)
                self._merge(snapshot, partial)
                snapshot.source_status[adapter.source_name()] = "live"
            except Exception:
                snapshot.source_status[adapter.source_name()] = "failed"

        return snapshot

    def _merge(self, snapshot, partial_snapshot):
        """Merge partial snapshot into full snapshot"""
        if partial_snapshot.bikes:
            snapshot.bikes = partial_snapshot.bikes
