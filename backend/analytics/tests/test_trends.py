import math

from analytics.trends import (
    moving_average,
    rolling_std,
    rate_of_change,
    detect_spikes,
)


def test_moving_average_basic():
    values = [1, 2, 3, 4]
    assert moving_average(values, window=2) == [None, 1.5, 2.5, 3.5]


def test_moving_average_invalid_window():
    try:
        moving_average([1, 2], window=0)
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_rolling_std_basic():
    values = [1, 2, 3]
    result = rolling_std(values, window=3)
    assert result[0] is None
    assert result[1] is None
    assert abs(result[2] - math.sqrt(2 / 3)) < 1e-6


def test_rolling_std_zero_variance():
    values = [1, 1, 1, 1]
    result = rolling_std(values, window=2)
    assert result == [None, 0.0, 0.0, 0.0]


def test_rolling_std_invalid_window():
    try:
        rolling_std([1, 2], window=1)
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_rate_of_change():
    values = [1, 4, 6]
    assert rate_of_change(values) == [None, 3, 2]


def test_detect_spikes_with_lower_threshold():
    values = [1, 1, 1, 10, 1, 1]
    spikes = detect_spikes(values, window=3, z_threshold=1.0)
    assert spikes[0] is False
    assert spikes[1] is False
    assert spikes[3] is True
