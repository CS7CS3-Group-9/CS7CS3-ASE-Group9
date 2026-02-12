from __future__ import annotations

from datetime import datetime
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """
    Convert arbitrary domain objects into JSON-serializable primitives.
    Handles:
      - datetime -> ISO string
      - list/tuple -> list
      - dict -> dict
      - objects with __dict__ -> dict recursively
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]

    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if hasattr(obj, "__dict__"):
        return {str(k): to_jsonable(v) for k, v in obj.__dict__.items()}

    # fallback: stringify unknown types
    return str(obj)
