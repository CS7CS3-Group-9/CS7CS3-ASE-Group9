"""
Caching and fallback layer for adapters.

Dual-layer cache:
  - In-memory dict for fast access
  - Firestore for persistence across Cloud Run restarts

When an adapter succeeds: cache in memory + save to Firestore.
When an adapter fails: return memory cache, or load from Firestore, or None.
Status is "live", "cached", or "failed".

Location: backend/fallback/adapter_cache.py
"""

import pickle
import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class AdapterCache:
    """
    Wraps adapter.fetch() calls with a cache + fallback layer.

    Usage (production with Firestore):
        from firebase_admin import firestore
        db = firestore.client()
        cache = AdapterCache(db=db)

    Usage (without Firestore / testing):
        cache = AdapterCache()
    """

    COLLECTION_NAME = "adapter_cache"

    def __init__(self, db=None):
        """
        Args:
            db: Firestore client (firebase_admin.firestore.client()).
                If None, cache is in-memory only (still works,
                just won't persist across restarts).
        """
        self._cache = {}  # name -> snapshot
        self._timestamps = {}  # name -> datetime
        self._params = {}  # name -> normalized kwargs key
        self._db = db

    def _get_collection(self):
        """Get Firestore collection, or None if no db."""
        if self._db is not None:
            return self._db.collection(self.COLLECTION_NAME)
        return None

    @staticmethod
    def _normalize_kwargs(kwargs: Dict[str, Any]) -> str:
        """Create a stable string key for adapter kwargs."""
        if not kwargs:
            return ""
        try:
            return json.dumps(kwargs, sort_keys=True, default=str, separators=(",", ":"))
        except (TypeError, ValueError):
            # Fallback for odd types
            return repr(sorted(kwargs.items()))

    def fetch_with_fallback(self, adapter: Any, **kwargs) -> Tuple[Optional[Any], str]:
        """
        Try to fetch from adapter. On success, cache it.
        On failure, return cached data or None.

        Args:
            adapter: Any adapter with source_name() and fetch()
            **kwargs: Passed through to adapter.fetch()

        Returns:
            (snapshot_or_none, status_string)
            status is "live", "cached", or "failed"
        """
        name = adapter.source_name()
        params_key = self._normalize_kwargs(kwargs)

        try:
            result = adapter.fetch(**kwargs)
            self._store(name, result, params_key=params_key)
            return result, "live"
        except Exception:
            return self._fallback(name, expected_params=params_key)

    def _store(self, name: str, snapshot: Any, params_key: str | None = None) -> None:
        """Save to memory and Firestore."""
        now = datetime.now(timezone.utc)
        self._cache[name] = snapshot
        self._timestamps[name] = now
        if params_key is None:
            params_key = ""
        self._params[name] = params_key

        # Persist to Firestore
        collection = self._get_collection()
        if collection is not None:
            try:
                blob = base64.b64encode(pickle.dumps(snapshot)).decode("utf-8")
                collection.document(name).set(
                    {
                        "data": blob,
                        "timestamp": now.isoformat(),
                        "params": params_key,
                    }
                )
            except Exception:
                # Firestore save failed - memory cache still works
                pass

    def _fallback(self, name: str, expected_params: str | None = None) -> Tuple[Optional[Any], str]:
        """Try memory cache, then Firestore, then give up."""
        # 1. Check memory
        if name in self._cache:
            if expected_params is None or self._params.get(name) == expected_params:
                return self._cache[name], "cached"

        # 2. Check Firestore
        loaded = self._load_from_firestore(name, expected_params=expected_params)
        if loaded is not None:
            return loaded, "cached"

        # 3. Nothing available
        return None, "failed"

    def _load_from_firestore(self, name: str, expected_params: str | None = None) -> Optional[Any]:
        """Try to load cached data from Firestore."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            doc = collection.document(name).get()
            if doc.exists:
                data = doc.to_dict()
                stored_params = data.get("params")
                if expected_params is not None and stored_params is not None and stored_params != expected_params:
                    return None
                if expected_params is not None and stored_params is None:
                    return None
                snapshot = pickle.loads(base64.b64decode(data["data"]))
                # Warm the memory cache
                self._cache[name] = snapshot
                self._timestamps[name] = datetime.fromisoformat(data["timestamp"])
                if stored_params is not None:
                    self._params[name] = stored_params
                return snapshot
        except Exception:
            pass

        return None

    def has_cached(self, name: str) -> bool:
        """Check if there is cached data for this adapter."""
        if name in self._cache:
            return True
        # Check Firestore as fallback
        loaded = self._load_from_firestore(name)
        return loaded is not None

    def last_success_time(self, name: str) -> Optional[datetime]:
        """Get the timestamp of the last successful fetch, or None."""
        if name in self._timestamps:
            return self._timestamps[name]

        # Try loading from Firestore (populates self._timestamps)
        self._load_from_firestore(name)
        return self._timestamps.get(name)

    def get_cached(self, name: str) -> Optional[Any]:
        """
        Return cached snapshot for adapter if available.
        May load from Firestore as a fallback.
        """
        if name in self._cache:
            return self._cache[name]
        return self._load_from_firestore(name)

    def cached_age_seconds(self, name: str) -> Optional[float]:
        """
        Return age of cached data in seconds, or None if no cache exists.
        """
        ts = self.last_success_time(name)
        if ts is None:
            return None
        return (datetime.now(timezone.utc) - ts).total_seconds()

    def get_cached_for(self, adapter: Any, **kwargs) -> Optional[Any]:
        """Return cached snapshot for adapter if available and params match."""
        name = adapter.source_name()
        params_key = self._normalize_kwargs(kwargs)
        if name in self._cache and self._params.get(name) == params_key:
            return self._cache[name]
        return self._load_from_firestore(name, expected_params=params_key)

    def last_success_time_for(self, adapter: Any, **kwargs) -> Optional[datetime]:
        """Return last success time if cache params match."""
        name = adapter.source_name()
        params_key = self._normalize_kwargs(kwargs)
        if name in self._timestamps and self._params.get(name) == params_key:
            return self._timestamps[name]
        loaded = self._load_from_firestore(name, expected_params=params_key)
        if loaded is not None:
            return self._timestamps.get(name)
        return None

    def cached_age_seconds_for(self, adapter: Any, **kwargs) -> Optional[float]:
        """Return cache age in seconds if params match, else None."""
        ts = self.last_success_time_for(adapter, **kwargs)
        if ts is None:
            return None
        return (datetime.now(timezone.utc) - ts).total_seconds()

    def clear(self, adapter_name: str = None) -> None:
        """
        Clear cache. If adapter_name given, clear only that one.
        Otherwise clear all.
        """
        if adapter_name:
            self._cache.pop(adapter_name, None)
            self._timestamps.pop(adapter_name, None)
            self._params.pop(adapter_name, None)
            self._delete_from_firestore(adapter_name)
        else:
            self._cache.clear()
            self._timestamps.clear()
            self._params.clear()
            self._delete_all_from_firestore()

    def _delete_from_firestore(self, name: str) -> None:
        """Delete a single cache entry from Firestore."""
        collection = self._get_collection()
        if collection is not None:
            try:
                collection.document(name).delete()
            except Exception:
                pass

    def _delete_all_from_firestore(self) -> None:
        """Delete all cache entries from Firestore."""
        collection = self._get_collection()
        if collection is not None:
            try:
                docs = collection.stream()
                for doc in docs:
                    doc.reference.delete()
            except Exception:
                pass
