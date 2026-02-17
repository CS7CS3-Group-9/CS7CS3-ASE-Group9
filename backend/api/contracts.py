from __future__ import annotations

from typing import Iterable, List, Optional

ALLOWED_SOURCE_STATUSES = {"live", "cached", "predicted", "failed"}

SNAPSHOT_KEYS = [
    "timestamp",
    "location",
    "source_status",
    "bikes",
    "buses",
    "traffic",
    "airquality",
    "population",
    "tours",
    "alerts",
    "recommendations",
]


def _type_name(value) -> str:
    return type(value).__name__


def _require_key(data: dict, key: str, errors: List[str]) -> None:
    if key not in data:
        errors.append(f"missing key: {key}")


def _require_type(value, expected, path: str, errors: List[str]) -> None:
    if not isinstance(value, expected):
        errors.append(f"expected {path} to be {expected}, got {_type_name(value)}")


def validate_snapshot_contract(
    data: dict,
    require_source_keys: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    Validate the standard MobilitySnapshot JSON contract.
    Returns a list of errors; empty list means valid.
    """
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["snapshot payload must be a dict"]

    for key in SNAPSHOT_KEYS:
        _require_key(data, key, errors)

    if "timestamp" in data and data["timestamp"] is not None:
        _require_type(data["timestamp"], str, "timestamp", errors)
    if "location" in data and data["location"] is not None:
        _require_type(data["location"], str, "location", errors)
    if "source_status" in data and data["source_status"] is not None:
        _require_type(data["source_status"], dict, "source_status", errors)

    if require_source_keys and isinstance(data.get("source_status"), dict):
        for key in require_source_keys:
            if key not in data["source_status"]:
                errors.append(f"missing source_status key: {key}")
            else:
                status = data["source_status"].get(key)
                if status not in ALLOWED_SOURCE_STATUSES:
                    errors.append(f"invalid source_status value for {key}: {status}")

    return errors


def validate_health_contract(data: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["health payload must be a dict"]

    for key in ("status", "adapters", "timestamp", "last_snapshot"):
        _require_key(data, key, errors)

    if "status" in data:
        _require_type(data["status"], str, "status", errors)
    if "adapters" in data:
        _require_type(data["adapters"], dict, "adapters", errors)
    if "timestamp" in data:
        _require_type(data["timestamp"], str, "timestamp", errors)

    return errors


def validate_hello_contract(data: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["hello payload must be a dict"]
    _require_key(data, "message", errors)
    if "message" in data:
        _require_type(data["message"], str, "message", errors)
    return errors
