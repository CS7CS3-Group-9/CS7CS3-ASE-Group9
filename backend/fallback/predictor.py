from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class PredictionResult:
    """
    Container for a predicted snapshot plus metadata.
    """

    snapshot: Any
    generated_at: datetime
    based_on: Optional[datetime]
    confidence: float
    reason: str


def _prediction_confidence(age_seconds: float, max_age_seconds: float) -> float:
    """
    Simple confidence decay from 1.0 down to 0.0 as data gets older.
    """
    if max_age_seconds <= 0:
        return 0.0
    return max(0.0, 1.0 - (age_seconds / max_age_seconds))


def predict_snapshot(
    last_snapshot: Any,
    max_age_seconds: float = 900.0,
) -> Optional[PredictionResult]:
    """
    Naive predictor:
    - Reuses last snapshot data if it is recent.
    - Updates timestamp to now.
    - Marks source_status entries as "predicted" if present.
    """
    if last_snapshot is None:
        return None

    last_ts = getattr(last_snapshot, "timestamp", None)
    now = datetime.now(timezone.utc)

    if last_ts is not None:
        age_seconds = (now - last_ts).total_seconds()
        if age_seconds > max_age_seconds:
            return None
    else:
        age_seconds = max_age_seconds

    predicted = deepcopy(last_snapshot)
    if hasattr(predicted, "timestamp"):
        predicted.timestamp = now

    if hasattr(predicted, "source_status") and isinstance(predicted.source_status, dict):
        predicted.source_status = {k: "predicted" for k in predicted.source_status.keys()}

    confidence = _prediction_confidence(age_seconds, max_age_seconds)
    reason = "predicted_from_recent_cache"

    return PredictionResult(
        snapshot=predicted,
        generated_at=now,
        based_on=last_ts if isinstance(last_ts, datetime) else None,
        confidence=confidence,
        reason=reason,
    )


def predict_value(last_value: Optional[float], drift: float = 0.0) -> Optional[float]:
    """
    Small helper for numeric series: return last_value + drift.
    """
    if last_value is None:
        return None
    return float(last_value) + float(drift)
