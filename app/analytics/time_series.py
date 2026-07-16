"""Time-series aggregation for financial charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.analytics.metrics import PreparedFinancialData


TIME_GROUPINGS = {
    "hour": "Hour",
    "day": "Day",
    "week": "Week",
    "month": "Month",
    "year": "Year",
}

WEEK_START_DAYS = {
    "monday": ("Monday", 0),
    "tuesday": ("Tuesday", 1),
    "wednesday": ("Wednesday", 2),
    "thursday": ("Thursday", 3),
    "friday": ("Friday", 4),
    "saturday": ("Saturday", 5),
    "sunday": ("Sunday", 6),
}


@dataclass(frozen=True)
class TimeSeriesPoint:
    """One aggregated financial point."""

    period: datetime
    revenue: float
    expenses: float
    profit: float
    amount: float


@dataclass(frozen=True)
class TimeSeriesResult:
    """Aggregated financial time series."""

    points: list[TimeSeriesPoint]
    grouping: str
    week_start: str
    visible_series: tuple[str, ...] = ()
    message: str = ""


def calculate_time_series(
    prepared: PreparedFinancialData,
    grouping: str,
    week_start: str,
) -> TimeSeriesResult:
    """Aggregate cleaned financial series by the selected time grain."""
    grouping = grouping if grouping in TIME_GROUPINGS else "day"
    week_start = week_start if week_start in WEEK_START_DAYS else "monday"

    if prepared.dates is None:
        return TimeSeriesResult(
            points=[],
            grouping=grouping,
            week_start=week_start,
            visible_series=(),
            message="Select a date column to build a chart.",
        )

    dates = _normalize_dates(prepared.dates)
    valid_mask = dates.notna()
    if not valid_mask.any():
        return TimeSeriesResult(
            points=[],
            grouping=grouping,
            week_start=week_start,
            visible_series=(),
            message="No valid dates found for charting.",
        )

    revenue = _series_or_zero(prepared.revenue, dates.index)
    expenses = _series_or_zero(prepared.expenses, dates.index)
    amount = _series_or_zero(prepared.amount, dates.index)
    periods = _group_periods(dates, grouping, week_start)

    frame = pd.DataFrame(
        {
            "period": periods[valid_mask],
            "revenue": revenue[valid_mask],
            "expenses": expenses[valid_mask],
            "amount": amount[valid_mask],
        }
    )
    frame["profit"] = frame["revenue"] - frame["expenses"]
    grouped = (
        frame.groupby("period", as_index=False)[["revenue", "expenses", "profit", "amount"]]
        .sum()
        .sort_values("period")
    )
    visible_series = _visible_chart_series(grouped, prepared)

    points = [
        TimeSeriesPoint(
            period=_to_python_datetime(row.period),
            revenue=float(row.revenue),
            expenses=float(row.expenses),
            profit=float(row.profit),
            amount=float(row.amount),
        )
        for row in grouped.itertuples(index=False)
    ]
    return TimeSeriesResult(
        points=points,
        grouping=grouping,
        week_start=week_start,
        visible_series=visible_series,
    )


def _normalize_dates(dates: pd.Series) -> pd.Series:
    """Return timezone-naive datetimes for grouping."""
    normalized = pd.to_datetime(dates, errors="coerce", utc=True)
    return normalized.dt.tz_convert(None)


def _series_or_zero(series: pd.Series | None, index: pd.Index) -> pd.Series:
    """Return a numeric series aligned to the source index."""
    if series is None:
        return pd.Series(0.0, index=index)
    return series.fillna(0).astype(float)


def _visible_chart_series(
    grouped: pd.DataFrame,
    prepared: PreparedFinancialData,
) -> tuple[str, ...]:
    """Return series that should be visible on the chart."""
    if prepared.amount_column_count and not prepared.revenue_column_count and not prepared.expense_column_count:
        return ("amount",)

    visible = []
    if prepared.revenue_column_count and _has_nonzero_values(grouped["revenue"]):
        visible.append("revenue")
    if prepared.expense_column_count and _has_nonzero_values(grouped["expenses"]):
        visible.append("expenses")
    if len(visible) >= 2 and _has_nonzero_values(grouped["profit"]):
        visible.append("profit")

    if not visible and prepared.amount_column_count and _has_nonzero_values(grouped["amount"]):
        visible.append("amount")

    return tuple(visible)


def _has_nonzero_values(series: pd.Series) -> bool:
    """Return whether a numeric series has at least one non-zero value."""
    return bool(series.abs().gt(0).any())


def _group_periods(dates: pd.Series, grouping: str, week_start: str) -> pd.Series:
    """Create period-start timestamps for the selected grouping."""
    if grouping == "hour":
        return dates.dt.floor("h")
    if grouping == "day":
        return dates.dt.floor("D")
    if grouping == "week":
        _label, week_start_index = WEEK_START_DAYS[week_start]
        offset_days = (dates.dt.dayofweek - week_start_index) % 7
        return dates.dt.floor("D") - pd.to_timedelta(offset_days, unit="D")
    if grouping == "month":
        return dates.dt.to_period("M").dt.to_timestamp()
    if grouping == "year":
        return dates.dt.to_period("Y").dt.to_timestamp()
    return dates.dt.floor("D")


def _to_python_datetime(value: object) -> datetime:
    """Convert pandas timestamps to Python datetimes."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value
