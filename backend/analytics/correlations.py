from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


def pearson_correlation(x: Iterable[float], y: Iterable[float]) -> float:
    """
    Compute Pearson correlation coefficient for two numeric series.
    Returns 0.0 if not enough data or variance is zero.
    """
    xs = list(x)
    ys = list(y)
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0

    xs = xs[:n]
    ys = ys[:n]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    num = 0.0
    den_x = 0.0
    den_y = 0.0

    for i in range(n):
        dx = xs[i] - mean_x
        dy = ys[i] - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / ((den_x * den_y) ** 0.5)


def rolling_correlation(
    x: Iterable[float],
    y: Iterable[float],
    window: int,
) -> List[Optional[float]]:
    """
    Rolling Pearson correlation over a fixed window.
    Returns list with None for positions that lack enough samples.
    """
    if window <= 1:
        raise ValueError("window must be > 1")

    xs = list(x)
    ys = list(y)
    n = min(len(xs), len(ys))

    out: List[Optional[float]] = []
    for i in range(n):
        if i + 1 < window:
            out.append(None)
            continue

        start = i + 1 - window

        xw: List[float] = []
        yw: List[float] = []
        for j in range(start, i + 1):
            xw.append(xs[j])
            yw.append(ys[j])

        out.append(pearson_correlation(xw, yw))

    return out


def pairwise_correlations(series: Dict[str, Iterable[float]]) -> Dict[Tuple[str, str], float]:
    """
    Compute pairwise Pearson correlations for a dict of series.
    """
    keys = list(series.keys())
    results: Dict[Tuple[str, str], float] = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = keys[i]
            b = keys[j]
            results[(a, b)] = pearson_correlation(series[a], series[b])
    return results
