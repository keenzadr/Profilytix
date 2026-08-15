"""Tests for simple forecasting."""

from datetime import datetime

from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
from app.ml.forecasting import (
    METHOD_LINEAR_TREND,
    METHOD_MOVING_AVERAGE,
    MIN_POINTS_FOR_FORECAST,
    forecast_time_series,
)


def make_series(
    revenues: list[float],
    grouping: str = "day",
    visible: tuple[str, ...] = ("revenue",),
) -> TimeSeriesResult:
    points = [
        TimeSeriesPoint(
            period=datetime(2026, 1, index + 1),
            revenue=value,
            expenses=0.0,
            profit=value,
            amount=value,
        )
        for index, value in enumerate(revenues)
    ]
    return TimeSeriesResult(
        points=points,
        grouping=grouping,
        week_start="monday",
        visible_series=visible,
    )


def test_short_series_is_refused():
    series = make_series([100.0] * (MIN_POINTS_FOR_FORECAST - 1))

    result = forecast_time_series(series)

    assert not result.has_forecast
    assert str(MIN_POINTS_FOR_FORECAST) in result.message


def test_straight_line_is_continued_by_the_trend_method():
    series = make_series([100.0, 200.0, 300.0, 400.0, 500.0, 600.0])

    result = forecast_time_series(series, periods_ahead=2)
    forecast = result.for_series("revenue")

    assert forecast.method == METHOD_LINEAR_TREND
    assert forecast.points[0].value == 700.0
    assert forecast.points[1].value == 800.0


def test_flat_series_keeps_a_flat_forecast():
    series = make_series([250.0] * 8)

    forecast = forecast_time_series(series).for_series("revenue")

    assert all(point.value == 250.0 for point in forecast.points)


def test_series_without_a_trend_uses_the_moving_average():
    """With no slope to find, the line has no advantage and is not claimed."""
    series = make_series([250.0] * 8)

    forecast = forecast_time_series(series).for_series("revenue")

    assert forecast.method == METHOD_MOVING_AVERAGE


def test_gentle_growth_is_recognised_as_a_trend():
    series = make_series([100.0, 110.0, 125.0, 130.0, 145.0, 150.0, 162.0, 170.0])

    forecast = forecast_time_series(series).for_series("revenue")

    assert forecast.method == METHOD_LINEAR_TREND
    assert forecast.points[0].value > 170.0


def test_both_methods_are_scored_over_the_same_periods():
    """The moving average cannot predict the first periods, so neither is scored there."""
    from app.ml.forecasting import (
        MOVING_AVERAGE_WINDOW,
        _linear_trend_error,
        _moving_average_error,
    )

    values = [100.0, 500.0, 120.0, 480.0, 90.0, 510.0, 110.0, 495.0]
    start = MOVING_AVERAGE_WINDOW

    assert _linear_trend_error(values, start) is not None
    assert _moving_average_error(values, start) is not None
    assert _linear_trend_error(values, len(values)) is None
    assert _moving_average_error(values, len(values)) is None


def test_forecast_periods_follow_the_grouping():
    daily = forecast_time_series(make_series([100.0] * 6), periods_ahead=2)
    assert daily.future_periods() == (datetime(2026, 1, 7), datetime(2026, 1, 8))

    weekly = forecast_time_series(
        make_series([100.0] * 6, grouping="week"), periods_ahead=1
    )
    assert weekly.future_periods() == (datetime(2026, 1, 13),)

    monthly = forecast_time_series(
        make_series([100.0] * 6, grouping="month"), periods_ahead=1
    )
    assert monthly.future_periods() == (datetime(2026, 2, 6),)


def test_every_visible_series_is_forecast():
    series = make_series(
        [100.0 * step for step in range(1, 8)],
        visible=("revenue", "profit"),
    )

    result = forecast_time_series(series)

    assert {forecast.series_key for forecast in result.forecasts} == {"revenue", "profit"}


def test_hidden_series_are_not_forecast():
    series = make_series([100.0 * step for step in range(1, 8)], visible=("revenue",))

    result = forecast_time_series(series)

    assert result.for_series("expenses") is None


def test_requesting_zero_periods_returns_nothing():
    result = forecast_time_series(make_series([100.0] * 8), periods_ahead=0)

    assert not result.has_forecast


def test_empty_series_is_handled():
    empty = TimeSeriesResult(points=[], grouping="day", week_start="monday")

    assert not forecast_time_series(empty).has_forecast


def test_forecast_values_are_finite():
    series = make_series([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    forecast = forecast_time_series(series).for_series("revenue")

    for point in forecast.points:
        assert point.value == point.value  # not nan
        assert abs(point.value) != float("inf")
