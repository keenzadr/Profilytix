"""Rule-based insight sentences for reports.

Formulas only, no model and no LLM. Each rule returns an empty tuple when its
inputs are missing, so a sparse dataset simply yields fewer sentences rather
than raising or printing `nan`.

Rules are collected in priority order and the result is capped, because a
report that opens with fifteen observations tells the reader nothing.
"""

from __future__ import annotations

from math import isfinite

from app.analytics.metrics import BasicMetrics, format_money
from app.analytics.time_series import TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult
from app.reports.strings import label, series_label


MAX_INSIGHTS = 6

# A category share below this is unremarkable and not worth a sentence.
MIN_CATEGORY_SHARE = 25.0

# Comparing against a near-zero baseline produces meaningless percentages.
MIN_COMPARISON_BASE = 1e-9


def generate_insights(
    metrics: BasicMetrics,
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult,
    language: str,
    forecast: object | None = None,
) -> tuple[str, ...]:
    """Return short observations about the analysis, most useful first."""
    collected: list[str] = []
    for rule in (
        _last_period_change,
        _half_period_trend,
        _category_concentration,
        _anomaly_summary,
        _burn_rate_and_cash_gap,
    ):
        collected.extend(rule(metrics, time_series, anomalies, language))

    collected.extend(_forecast_summary(time_series, forecast, language))
    return tuple(collected[:MAX_INSIGHTS])


def _forecast_summary(
    time_series: TimeSeriesResult,
    forecast: object | None,
    language: str,
) -> tuple[str, ...]:
    """Report the next projected value for the most telling series."""
    if forecast is None or not getattr(forecast, "has_forecast", False):
        return ()

    # Profit is what an owner actually asks about; fall back to whatever is shown.
    preferred = ("profit", "amount", "revenue")
    for series_key in preferred:
        if series_key not in time_series.visible_series:
            continue
        series_forecast = forecast.for_series(series_key)
        if series_forecast is None or not series_forecast.points:
            continue

        value = series_forecast.points[0].value
        if not isfinite(value):
            return ()

        return (
            label(language, "insight_forecast").format(
                series=series_label(language, series_key),
                value=format_money(value),
            ),
        )

    return ()


def _last_period_change(
    _metrics: BasicMetrics,
    time_series: TimeSeriesResult,
    _anomalies: AnomalyDetectionResult,
    language: str,
) -> tuple[str, ...]:
    """Compare the final period against the one before it."""
    points = time_series.points
    if len(points) < 2:
        return ()

    previous = points[-2].profit
    latest = points[-1].profit
    percent = _percent_change(previous, latest)
    if percent is None:
        return ()

    key = "insight_profit_change_up" if percent >= 0 else "insight_profit_change_down"
    return (label(language, key).format(percent=_format_percent(abs(percent))),)


def _half_period_trend(
    _metrics: BasicMetrics,
    time_series: TimeSeriesResult,
    _anomalies: AnomalyDetectionResult,
    language: str,
) -> tuple[str, ...]:
    """Compare the second half of the range against the first."""
    points = time_series.points
    if len(points) < 4:
        return ()

    middle = len(points) // 2
    first_half = sum(point.profit for point in points[:middle])
    second_half = sum(point.profit for point in points[middle:])
    percent = _percent_change(first_half, second_half)
    if percent is None:
        return ()

    key = "insight_half_trend_up" if percent >= 0 else "insight_half_trend_down"
    return (label(language, key).format(percent=_format_percent(abs(percent))),)


def _category_concentration(
    metrics: BasicMetrics,
    _time_series: TimeSeriesResult,
    _anomalies: AnomalyDetectionResult,
    language: str,
) -> tuple[str, ...]:
    """Report the share of the largest category when one dominates."""
    if not metrics.top_categories:
        return ()

    turnovers = [(category, _category_turnover(category)) for category in metrics.top_categories]
    total = sum(turnover for _category, turnover in turnovers)
    if total <= MIN_COMPARISON_BASE:
        return ()

    leader, leader_turnover = max(turnovers, key=lambda item: item[1])
    share = leader_turnover / total * 100
    if not isfinite(share) or share < MIN_CATEGORY_SHARE:
        return ()

    return (
        label(language, "insight_category_share").format(
            name=leader.name,
            percent=_format_percent(share),
        ),
    )


def _anomaly_summary(
    _metrics: BasicMetrics,
    _time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult,
    language: str,
) -> tuple[str, ...]:
    """Report how many unusual periods were found and name the strongest."""
    if not anomalies.has_anomalies:
        return ()

    strongest = anomalies.anomalies[0]
    kind_key = "anomaly_drop" if strongest.kind == "drop" else "anomaly_spike"
    return (
        label(language, "insight_anomalies").format(
            count=anomalies.total_found,
            kind=label(language, kind_key),
            series=series_label(language, strongest.series_key, strongest.series_label),
            date=f"{strongest.period:%d.%m.%Y}",
        ),
    )


def _burn_rate_and_cash_gap(
    metrics: BasicMetrics,
    _time_series: TimeSeriesResult,
    _anomalies: AnomalyDetectionResult,
    language: str,
) -> tuple[str, ...]:
    """Report the daily burn rate, and warn when the average day loses money."""
    sentences: list[str] = []

    daily_expense = metrics.average_daily_expense
    if daily_expense is not None and isfinite(daily_expense) and daily_expense > 0:
        sentences.append(
            label(language, "insight_burn_rate").format(value=format_money(daily_expense))
        )

    daily_profit = metrics.average_daily_profit
    if daily_profit is not None and isfinite(daily_profit) and daily_profit < 0:
        sentences.append(
            label(language, "insight_cash_gap").format(value=format_money(abs(daily_profit)))
        )

    return tuple(sentences)


def _category_turnover(category: object) -> float:
    """Return how much money moved through one category, in either direction."""
    revenue = abs(getattr(category, "revenue", None) or 0.0)
    expenses = abs(getattr(category, "expenses", None) or 0.0)
    return revenue + expenses


def _percent_change(base: float, current: float) -> float | None:
    """Return the percentage change, or None when the base is unusable."""
    if base is None or current is None:
        return None
    if not isfinite(base) or not isfinite(current):
        return None
    if abs(base) <= MIN_COMPARISON_BASE:
        return None

    percent = (current - base) / abs(base) * 100
    return percent if isfinite(percent) else None


def _format_percent(value: float) -> str:
    """Format a percentage without a pointless trailing zero."""
    rounded = round(value, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded}"
