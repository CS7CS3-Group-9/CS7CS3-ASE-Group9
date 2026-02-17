from __future__ import annotations

from typing import Iterable, List, Optional


def moving_average(values: Iterable[float], window: int) -> List[Optional[float]]:
    """
    Simple moving average over a fixed window.
    Returns list with None for positions lacking enough samples.
    """
    vals = list(values)
    if window <= 0:
        raise ValueError("window must be > 0")
    out: List[Optional[float]] = []
    for i in range(len(vals)):
        if i + 1 < window:
            out.append(None)
            continue

        start = i + 1 - window
        total = 0.0
        for j in range(start, i + 1):
            total += vals[j]
        out.append(total / window)

    return out


def rolling_std(values: Iterable[float], window: int) -> List[Optional[float]]:
    """
    Rolling standard deviation over a fixed window.
    """
    vals = list(values)
    if window <= 1:
        raise ValueError("window must be > 1")
    out: List[Optional[float]] = []
    for i in range(len(vals)):
        if i + 1 < window:
            out.append(None)
            continue

        start = i + 1 - window

        total = 0.0
        for j in range(start, i + 1):
            total += vals[j]
        mean = total / window

        var_total = 0.0
        for j in range(start, i + 1):
            diff = vals[j] - mean
            var_total += diff * diff

        out.append((var_total / window) ** 0.5)

    return out


def rate_of_change(values: Iterable[float]) -> List[Optional[float]]:
    """
    First difference of a series. First entry is None.
    """
    vals = list(values)
    if not vals:
        return []
    out: List[Optional[float]] = [None]
    for i in range(1, len(vals)):
        out.append(vals[i] - vals[i - 1])
    return out


def detect_spikes(
    values: Iterable[float],
    window: int = 5,
    z_threshold: float = 2.5,
) -> List[bool]:
    """
    Detect spikes using rolling z-score.
    """
    vals = list(values)
    means = moving_average(vals, window)
    stds = rolling_std(vals, window)

    spikes: List[bool] = []
    for i in range(len(vals)):
        mean = means[i]
        std = stds[i]
        if mean is None or std is None or std == 0:
            spikes.append(False)
            continue
        z = abs(vals[i] - mean) / std
        spikes.append(z >= z_threshold)
    return spikes
