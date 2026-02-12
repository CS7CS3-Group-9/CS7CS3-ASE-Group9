"""
Tests for caching and fallback mechanism.

Tests run in memory-only mode (no Firestore needed).
Firestore-specific tests mock firebase calls.

Run: pytest backend/fallback/tests/test_adapter_cache.py -v
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.fallback.cache import AdapterCache


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_snapshot(bikes=None, traffic=None):
    """Build a fake MobilitySnapshot-like object (for memory-only tests)."""
    snap = MagicMock()
    snap.timestamp = datetime.now(timezone.utc)
    snap.location = "dublin"
    snap.bikes = bikes
    snap.traffic = traffic
    snap.airquality = None
    snap.tours = None
    snap.source_status = {}
    return snap


class SimpleSnapshot:
    """Picklable snapshot for Firestore tests (MagicMock can't be pickled)."""
    def __init__(self, bikes=None, traffic=None):
        self.timestamp = datetime.now(timezone.utc)
        self.location = "dublin"
        self.bikes = bikes
        self.traffic = traffic
        self.airquality = None
        self.tours = None
        self.source_status = {}


class WorkingAdapter:
    def __init__(self, data=None):
        self._data = data or {"available_bikes": 50}
        self.call_count = 0

    def source_name(self):
        return "bikes"

    def fetch(self, **kwargs):
        self.call_count += 1
        return _make_snapshot(bikes=self._data)


class PicklableWorkingAdapter:
    """Returns picklable snapshots for Firestore tests."""
    def __init__(self, data=None):
        self._data = data or {"available_bikes": 50}

    def source_name(self):
        return "bikes"

    def fetch(self, **kwargs):
        return SimpleSnapshot(bikes=self._data)


class FailingAdapter:
    def source_name(self):
        return "bikes"

    def fetch(self, **kwargs):
        raise ConnectionError("API unreachable")


class SometimesFailsAdapter:
    def __init__(self):
        self.should_fail = False
        self.call_count = 0

    def source_name(self):
        return "traffic"

    def fetch(self, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise TimeoutError("API timed out")
        return _make_snapshot(traffic=[{"incident": 1}])


# ──────────────────────────────────────────────
# 1. Basic cache behaviour (memory-only, no Firestore)
# ──────────────────────────────────────────────

def test_cache_stores_successful_result():
    """After a successful fetch, result should be in cache."""
    cache = AdapterCache()
    adapter = WorkingAdapter()

    result, status = cache.fetch_with_fallback(adapter, location="dublin")

    assert result is not None
    assert result.bikes == {"available_bikes": 50}
    assert status == "live"


def test_cache_returns_cached_on_failure():
    """When adapter fails but cache has data, return cached data."""
    cache = AdapterCache()

    # First call succeeds - populates cache
    working = WorkingAdapter()
    cache.fetch_with_fallback(working, location="dublin")

    # Second call fails - should return cached
    failing = FailingAdapter()
    result, status = cache.fetch_with_fallback(failing, location="dublin")

    assert result is not None
    assert result.bikes == {"available_bikes": 50}
    assert status == "cached"


def test_cache_returns_none_on_failure_without_cache():
    """When adapter fails and no cache exists, return None."""
    cache = AdapterCache()
    failing = FailingAdapter()

    result, status = cache.fetch_with_fallback(failing, location="dublin")

    assert result is None
    assert status == "failed"


# ──────────────────────────────────────────────
# 2. Cache updates on success
# ──────────────────────────────────────────────

def test_cache_updates_with_newer_data():
    """Cache should update when adapter returns new data."""
    cache = AdapterCache()

    adapter_v1 = WorkingAdapter(data={"available_bikes": 50})
    cache.fetch_with_fallback(adapter_v1, location="dublin")

    adapter_v2 = WorkingAdapter(data={"available_bikes": 75})
    result, status = cache.fetch_with_fallback(adapter_v2, location="dublin")

    assert result.bikes == {"available_bikes": 75}
    assert status == "live"


def test_cache_keys_by_adapter_name():
    """Different adapters should have separate cache entries."""
    cache = AdapterCache()

    bikes = WorkingAdapter()
    bikes.source_name = lambda: "bikes"

    traffic = WorkingAdapter(data={"incidents": 3})
    traffic.source_name = lambda: "traffic"

    cache.fetch_with_fallback(bikes, location="dublin")
    cache.fetch_with_fallback(traffic, location="dublin")

    assert cache.has_cached("bikes")
    assert cache.has_cached("traffic")


# ──────────────────────────────────────────────
# 3. Adapter flapping (works, fails, works)
# ──────────────────────────────────────────────

def test_cache_handles_flapping_adapter():
    """Adapter that alternates between working and failing."""
    cache = AdapterCache()
    adapter = SometimesFailsAdapter()

    # Call 1: works
    result1, status1 = cache.fetch_with_fallback(adapter, location="dublin")
    assert status1 == "live"
    assert result1.traffic == [{"incident": 1}]

    # Call 2: fails - should return cached
    adapter.should_fail = True
    result2, status2 = cache.fetch_with_fallback(adapter, location="dublin")
    assert status2 == "cached"
    assert result2.traffic == [{"incident": 1}]

    # Call 3: works again
    adapter.should_fail = False
    result3, status3 = cache.fetch_with_fallback(adapter, location="dublin")
    assert status3 == "live"


# ──────────────────────────────────────────────
# 4. Cache metadata
# ──────────────────────────────────────────────

def test_cache_tracks_last_success_time():
    """Cache should track when data was last successfully fetched."""
    cache = AdapterCache()
    adapter = WorkingAdapter()

    cache.fetch_with_fallback(adapter, location="dublin")

    last_time = cache.last_success_time("bikes")
    assert last_time is not None
    assert isinstance(last_time, datetime)


def test_cache_no_success_time_before_fetch():
    """Before any fetch, last_success_time should be None."""
    cache = AdapterCache()
    assert cache.last_success_time("bikes") is None


def test_cache_has_cached_returns_false_initially():
    """has_cached should be False before any successful fetch."""
    cache = AdapterCache()
    assert cache.has_cached("bikes") is False


def test_cache_has_cached_returns_true_after_success():
    """has_cached should be True after a successful fetch."""
    cache = AdapterCache()
    adapter = WorkingAdapter()
    cache.fetch_with_fallback(adapter, location="dublin")
    assert cache.has_cached("bikes") is True


# ──────────────────────────────────────────────
# 5. Kwargs passthrough
# ──────────────────────────────────────────────

def test_cache_passes_kwargs_to_adapter():
    """Extra kwargs should be forwarded to adapter.fetch()."""
    cache = AdapterCache()

    class KwargsAdapter:
        def source_name(self):
            return "custom"

        def fetch(self, location="dublin", radius_km=1.0):
            snap = _make_snapshot()
            snap.traffic = {"radius": radius_km}
            return snap

    adapter = KwargsAdapter()
    result, status = cache.fetch_with_fallback(
        adapter, location="dublin", radius_km=5.0
    )

    assert result.traffic == {"radius": 5.0}
    assert status == "live"


# ──────────────────────────────────────────────
# 6. Clear cache
# ──────────────────────────────────────────────

def test_clear_cache_removes_all():
    """clear() should remove all cached data."""
    cache = AdapterCache()
    adapter = WorkingAdapter()
    cache.fetch_with_fallback(adapter, location="dublin")

    cache.clear()

    assert cache.has_cached("bikes") is False
    assert cache.last_success_time("bikes") is None


def test_clear_single_adapter():
    """clear(name) should remove only that adapter's cache."""
    cache = AdapterCache()

    bikes = WorkingAdapter()
    bikes.source_name = lambda: "bikes"

    traffic = WorkingAdapter(data={"incidents": 3})
    traffic.source_name = lambda: "traffic"

    cache.fetch_with_fallback(bikes, location="dublin")
    cache.fetch_with_fallback(traffic, location="dublin")

    cache.clear("bikes")

    assert cache.has_cached("bikes") is False
    assert cache.has_cached("traffic") is True


# ──────────────────────────────────────────────
# 7. Firestore persistence tests (mocked)
# ──────────────────────────────────────────────

def _make_mock_db():
    """Create a mock Firestore client with working storage."""
    db = MagicMock()
    db._store = {}

    def mock_set(data):
        doc_name = db._last_doc_name
        db._store[doc_name] = data

    def mock_get():
        doc_name = db._last_doc_name
        doc = MagicMock()
        if doc_name in db._store:
            doc.exists = True
            doc.to_dict.return_value = db._store[doc_name]
        else:
            doc.exists = False
        return doc

    def mock_delete():
        doc_name = db._last_doc_name
        db._store.pop(doc_name, None)

    def mock_document(name):
        db._last_doc_name = name
        doc_ref = MagicMock()
        doc_ref.set = mock_set
        doc_ref.get = mock_get
        doc_ref.delete = mock_delete
        return doc_ref

    def mock_stream():
        docs = []
        for name in list(db._store.keys()):
            doc = MagicMock()
            # Capture name in closure properly
            captured_name = name

            def make_delete(n):
                def delete():
                    db._last_doc_name = n
                    db._store.pop(n, None)
                return delete

            doc.reference.delete = make_delete(captured_name)
            docs.append(doc)
        return docs

    collection = MagicMock()
    collection.document = mock_document
    collection.stream = mock_stream
    db.collection.return_value = collection

    return db


def test_firestore_saves_on_success():
    """Successful fetch should save data to Firestore."""
    db = _make_mock_db()
    cache = AdapterCache(db=db)
    adapter = PicklableWorkingAdapter()

    cache.fetch_with_fallback(adapter, location="dublin")

    assert "bikes" in db._store
    assert "data" in db._store["bikes"]
    assert "timestamp" in db._store["bikes"]


def test_firestore_loads_on_memory_miss():
    """If memory is empty but Firestore has data, load from Firestore."""
    db = _make_mock_db()

    # First cache instance saves to Firestore
    cache1 = AdapterCache(db=db)
    adapter = PicklableWorkingAdapter()
    cache1.fetch_with_fallback(adapter, location="dublin")

    # Second cache instance (simulating container restart)
    cache2 = AdapterCache(db=db)

    # Memory is empty, but Firestore has data
    assert cache2.has_cached("bikes") is True


def test_firestore_fallback_after_restart():
    """After container restart, failing adapter should get Firestore cache."""
    db = _make_mock_db()

    # First run: adapter works, saves to Firestore
    cache1 = AdapterCache(db=db)
    working = PicklableWorkingAdapter()
    cache1.fetch_with_fallback(working, location="dublin")

    # Container restart: new cache, empty memory
    cache2 = AdapterCache(db=db)
    failing = FailingAdapter()

    result, status = cache2.fetch_with_fallback(failing, location="dublin")

    assert result is not None
    assert result.bikes == {"available_bikes": 50}
    assert status == "cached"


def test_firestore_clear_deletes_document():
    """clear(name) should delete from Firestore too."""
    db = _make_mock_db()
    cache = AdapterCache(db=db)

    adapter = PicklableWorkingAdapter()
    cache.fetch_with_fallback(adapter, location="dublin")
    assert "bikes" in db._store

    cache.clear("bikes")
    assert "bikes" not in db._store


def test_firestore_clear_all_deletes_everything():
    """clear() should delete all documents from Firestore."""
    db = _make_mock_db()
    cache = AdapterCache(db=db)

    class PicklableTrafficAdapter:
        def source_name(self):
            return "traffic"
        def fetch(self, **kwargs):
            return SimpleSnapshot(traffic=[{"incidents": 3}])

    bikes = PicklableWorkingAdapter()
    traffic = PicklableTrafficAdapter()

    cache.fetch_with_fallback(bikes, location="dublin")
    cache.fetch_with_fallback(traffic, location="dublin")

    cache.clear()
    assert len(db._store) == 0


def test_works_without_firestore():
    """Cache should work fine with db=None (memory only)."""
    cache = AdapterCache(db=None)
    adapter = WorkingAdapter()

    result, status = cache.fetch_with_fallback(adapter, location="dublin")
    assert status == "live"
    assert result.bikes == {"available_bikes": 50}

    # Failure falls back to memory
    failing = FailingAdapter()
    result2, status2 = cache.fetch_with_fallback(failing, location="dublin")
    assert status2 == "cached"