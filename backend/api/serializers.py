from __future__ import annotations
from datetime import datetime
from typing import Any


def to_jsonable(obj: Any) -> Any:

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]

    if hasattr(obj, "__dict__"):
        return {k: to_jsonable(v) for k, v in obj.__dict__.items()}

    return str(obj)
