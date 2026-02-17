import math

from backend.analytics.correlations import (
    pearson_correlation,
    rolling_correlation,
    pairwise_correlations,
)


def test_pearson_perfect_positive():
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    assert pearson_correlation(x, y) == 1.0


def test_pearson_perfect_negative():
    x = [1, 2, 3, 4, 5]
    y = [5, 4, 3, 2, 1]
    assert pearson_correlation(x, y) == -1.0


def test_pearson_zero_variance_returns_zero():
    x = [1, 1, 1, 1]
    y = [1, 2, 3, 4]
    assert pearson_correlation(x, y) == 0.0


def test_rolling_correlation_window():
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 5]
    result = rolling_correlation(x, y, window=3)
    assert result == [None, None, 1.0, 1.0, 1.0]


def test_rolling_correlation_invalid_window():
    try:
        rolling_correlation([1, 2], [1, 2], window=1)
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_pairwise_correlations():
    series = {
        "a": [1, 2, 3],
        "b": [1, 2, 3],
        "c": [3, 2, 1],
    }
    results = pairwise_correlations(series)
    assert results[("a", "b")] == 1.0
    assert results[("a", "c")] == -1.0
    assert results[("b", "c")] == -1.0
