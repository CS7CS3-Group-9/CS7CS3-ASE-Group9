from datetime import datetime, timezone

from backend.fallback.resolver import choose_snapshot, resolve_with_cache
from backend.fallback.cache import AdapterCache
from backend.models.mobility_snapshot import MobilitySnapshot


class WorkingAdapter:
    def source_name(self):
        return "bikes"

    def fetch(self, **kwargs):
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location="dublin",
            bikes={"available_bikes": 10},
            source_status={"bikes": "live"},
        )


class FailingAdapter:
    def source_name(self):
        return "bikes"

    def fetch(self, **kwargs):
        raise RuntimeError("fail")


def test_choose_snapshot_priority():
    live = object()
    cached = object()
    predicted = object()
    snap, status = choose_snapshot(live, cached, predicted)
    assert snap is live
    assert status == "live"

    snap, status = choose_snapshot(None, cached, predicted)
    assert snap is cached
    assert status == "cached"

    snap, status = choose_snapshot(None, None, predicted)
    assert snap is predicted
    assert status == "predicted"


def test_resolve_with_cache_live():
    cache = AdapterCache()
    result = resolve_with_cache(WorkingAdapter(), cache, location="dublin")
    assert result.status == "live"
    assert result.snapshot is not None


def test_resolve_with_cache_cached():
    cache = AdapterCache()
    cache.fetch_with_fallback(WorkingAdapter(), location="dublin")
    result = resolve_with_cache(FailingAdapter(), cache, location="dublin")
    assert result.status == "cached"
    assert result.snapshot is not None


def test_resolve_with_cache_predicted():
    class DummyCache:
        def fetch_with_fallback(self, adapter, **kwargs):
            return None, "failed"

        def get_cached(self, name):
            return MobilitySnapshot(
                timestamp=datetime.now(timezone.utc),
                location="dublin",
                bikes={"available_bikes": 10},
                source_status={"bikes": "live"},
            )

    cache = DummyCache()
    result = resolve_with_cache(FailingAdapter(), cache)
    assert result.status == "predicted"
    assert result.snapshot is not None
    assert "confidence" in result.detail


def test_resolve_with_cache_failed():
    class DummyCache:
        def fetch_with_fallback(self, adapter, **kwargs):
            return None, "failed"

        def get_cached(self, name):
            return None

    cache = DummyCache()
    result = resolve_with_cache(FailingAdapter(), cache)
    assert result.status == "failed"
    assert result.snapshot is None
