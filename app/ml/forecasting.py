"""Simple revenue, expense, and profit forecasting.

Two candidates only: a moving average and a least-squares linear trend. Each
series gets whichever had the lower in-sample error, which is honest about the
fact that neither is clever and lets a flat series keep a flat forecast instead
of inheriting a trend it does not have.

`PROJECT_CONTEXT.md` is explicit that forecasting should not start complex, so
there is no seasonality, no Prophet, and no gradient boosting here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

import pandas as pd

from app.analytics.time_series import TimeSeriesResult


MIN_POINTS_FOR_FORECAST = 6
DEFAULT_PERIODS_AHEAD = 3
MOVING_AVERAGE_WINDOW = 3

# The line must beat the moving average by this much to be believed. A free
# slope always fits noise a little better; that is not the same as a real trend.
TREND_ADVANTAGE = 0.85

METHOD_MOVING_AVERAGE = "moving_average"
METHOD_LINEAR_TREND = "linear_trend"

PERIOD_STEPS = {
    "hour": pd.Timedelta(hours=1),
    "day": pd.Timedelta(days=1),
    "week": pd.Timedelta(days=7),
    "month": pd.DateOffset(months=1),
    "year": pd.DateOffset(years=1),
}


@dataclass(frozen=True)
class ForecastPoint:
    """One projected value at a future period."""

    period: datetime
    value: float


@dataclass(frozen=True)
class SeriesForecast:
    """Projected values for one financial series."""

    series_key: str
    points: tuple[ForecastPoint, ...]
    method: str


@dataclass(frozen=True)
class ForecastResult:
    """Forecasts for every visible series."""

    forecasts: tuple[SeriesForecast, ...]
    periods_ahead: int
    grouping: str = "day"
    message: str = ""

    @property
    def has_forecast(self) -> bool:
        """Return whether anything could be projected."""
        return bool(self.forecasts)

    def for_series(self, series_key: str) -> SeriesForecast | None:
        """Return the forecast for one series, if it exists."""
        for forecast in self.forecasts:
            if forecast.series_key == series_key:
                return forecast
        return None

    def future_periods(self) -> tuple[datetime, ...]:
        """Return the projected periods, taken from the first forecast."""
        if not self.forecasts:
            return ()
        return tuple(point.period for point in self.forecasts[0].points)


def forecast_time_series(
    time_series: TimeSeriesResult,
    periods_ahead: int = DEFAULT_PERIODS_AHEAD,
) -> ForecastResult:
    """Project each visible series a few periods forward."""
    if periods_ahead < 1:
        return ForecastResult((), 0, time_series.grouping, "Nothing to forecast.")

    if len(time_series.points) < MIN_POINTS_FOR_FORECAST:
        return ForecastResult(
            (),
            periods_ahead,
            time_series.grouping,
            f"Need at least {MIN_POINTS_FOR_FORECAST} periods to forecast.",
        )

    if not time_series.visible_series:
        return ForecastResult(
            (), periods_ahead, time_series.grouping, "No series available to forecast."
        )

    future = _future_periods(time_series, periods_ahead)
    if not future:
        return ForecastResult(
            (),
            periods_ahead,
            time_series.grouping,
            "Unsupported grouping for forecasting.",
        )

    forecasts = []
    for series_key in time_series.visible_series:
        values = [float(getattr(point, series_key)) for point in time_series.points]
        if not all(isfinite(value) for value in values):
            continue

        forecast = _forecast_one_series(series_key, values, future)
        if forecast is not None:
            forecasts.append(forecast)

    if not forecasts:
        return ForecastResult(
            (), periods_ahead, time_series.grouping, "No series could be forecast."
        )

    return ForecastResult(tuple(forecasts), periods_ahead, time_series.grouping)


def _forecast_one_series(
    series_key: str,
    values: list[float],
    future: list[datetime],
) -> SeriesForecast | None:
    """Pick a method and project it forward.

    Both errors are measured over the same periods. The moving average cannot
    predict the first few points at all, so scoring the line over the whole
    range and the average over the tail would compare two different questions.

    The line also has a free slope, which lets it fit noise the average cannot.
    It is therefore only chosen when it wins by a clear margin: claiming a steep
    trend that the data does not really support is worse for a small business
    than admitting the level is flat.
    """
    trend = _linear_trend_forecast(values, len(future))
    average = _moving_average_forecast(values, len(future))
    if trend is None and average is None:
        return None

    start = min(MOVING_AVERAGE_WINDOW, len(values))
    trend_error = _linear_trend_error(values, start)
    average_error = _moving_average_error(values, start)

    method, projected = _choose_method(trend, trend_error, average, average_error)
    if projected is None:
        return None

    points = tuple(
        ForecastPoint(period=period, value=value)
        for period, value in zip(future, projected)
    )
    return SeriesForecast(series_key=series_key, points=points, method=method)


def _choose_method(
    trend: list[float] | None,
    trend_error: float | None,
    average: list[float] | None,
    average_error: float | None,
) -> tuple[str, list[float] | None]:
    """Return the method to use and its projection."""
    trend_usable = trend is not None and trend_error is not None and isfinite(trend_error)
    average_usable = (
        average is not None and average_error is not None and isfinite(average_error)
    )

    if trend_usable and not average_usable:
        return METHOD_LINEAR_TREND, trend
    if average_usable and not trend_usable:
        return METHOD_MOVING_AVERAGE, average
    if not trend_usable and not average_usable:
        return METHOD_MOVING_AVERAGE, average

    if trend_error < average_error * TREND_ADVANTAGE:
        return METHOD_LINEAR_TREND, trend
    return METHOD_MOVING_AVERAGE, average


def _linear_trend_forecast(values: list[float], periods_ahead: int) -> list[float] | None:
    """Project a least-squares straight line forward."""
    slope, intercept = _fit_line(values)
    if slope is None:
        return None

    start = len(values)
    return [slope * (start + step) + intercept for step in range(periods_ahead)]


def _moving_average_forecast(values: list[float], periods_ahead: int) -> list[float] | None:
    """Project the average of the most recent periods forward, flat."""
    window = min(MOVING_AVERAGE_WINDOW, len(values))
    if window < 1:
        return None

    level = sum(values[-window:]) / window
    if not isfinite(level):
        return None

    return [level] * periods_ahead


def _linear_trend_error(values: list[float], start: int) -> float | None:
    """Return the mean absolute error of the fitted line, from `start` onward."""
    slope, intercept = _fit_line(values)
    if slope is None or start >= len(values):
        return None

    errors = [
        abs(values[index] - (slope * index + intercept))
        for index in range(start, len(values))
    ]
    return sum(errors) / len(errors) if errors else None


def _moving_average_error(values: list[float], start: int) -> float | None:
    """Return the mean absolute error of the moving average, from `start` onward."""
    window = min(MOVING_AVERAGE_WINDOW, len(values))
    if start < window or start >= len(values):
        return None

    errors = []
    for index in range(start, len(values)):
        predicted = sum(values[index - window : index]) / window
        errors.append(abs(values[index] - predicted))

    return sum(errors) / len(errors) if errors else None


def _fit_line(values: list[float]) -> tuple[float | None, float]:
    """Fit value = slope * index + intercept by least squares."""
    count = len(values)
    if count < 2:
        return None, 0.0

    mean_index = (count - 1) / 2
    mean_value = sum(values) / count

    denominator = sum((index - mean_index) ** 2 for index in range(count))
    if denominator == 0:
        return None, 0.0

    numerator = sum(
        (index - mean_index) * (value - mean_value) for index, value in enumerate(values)
    )
    slope = numerator / denominator
    intercept = mean_value - slope * mean_index

    if not isfinite(slope) or not isfinite(intercept):
        return None, 0.0
    return slope, intercept


def _future_periods(time_series: TimeSeriesResult, periods_ahead: int) -> list[datetime]:
    """Return the next periods after the observed range."""
    step = PERIOD_STEPS.get(time_series.grouping)
    if step is None:
        return []

    last = pd.Timestamp(time_series.points[-1].period)
    periods = []
    current = last
    for _ in range(periods_ahead):
        current = current + step
        periods.append(current.to_pydatetime())

    return periods
