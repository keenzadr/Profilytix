"""Simple rule-based financial anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

import pandas as pd

from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult


SERIES_LABELS = {
    "revenue": "Revenue",
    "expenses": "Expenses",
    "profit": "Profit",
    "amount": "Amount",
}

SERIES_DIRECTIONS = {
    "revenue": ("high",),
    "expenses": ("high",),
    "profit": ("low",),
    "amount": ("low", "high"),
}

Z_SCORE_THRESHOLD = 2.5
IQR_MULTIPLIER = 1.5
MIN_PERIODS_FOR_ANOMALIES = 4


@dataclass(frozen=True)
class FinancialAnomaly:
    """One unusual aggregated financial value."""

    period: datetime
    series_key: str
    series_label: str
    kind: str
    value: float
    baseline: float
    score: float
    rule: str
    severity: str


@dataclass(frozen=True)
class AnomalyDetectionResult:
    """Detected anomalies for the current chart grouping."""

    anomalies: tuple[FinancialAnomaly, ...]
    total_found: int
    message: str = ""

    @property
    def has_anomalies(self) -> bool:
        """Return whether at least one anomaly was detected."""
        return bool(self.anomalies)


def detect_financial_anomalies(
    time_series: TimeSeriesResult,
    max_items: int = 8,
) -> AnomalyDetectionResult:
    """Detect simple spikes and drops in aggregated chart data."""
    if not time_series.points:
        return AnomalyDetectionResult(
            anomalies=(),
            total_found=0,
            message=time_series.message or "No chart data available for anomaly detection.",
        )

    if len(time_series.points) < MIN_PERIODS_FOR_ANOMALIES:
        return AnomalyDetectionResult(
            anomalies=(),
            total_found=0,
            message=(
                f"Need at least {MIN_PERIODS_FOR_ANOMALIES} periods to detect anomalies."
            ),
        )

    if not time_series.visible_series:
        return AnomalyDetectionResult(
            anomalies=(),
            total_found=0,
            message="No visible financial series available for anomaly detection.",
        )

    anomalies: list[FinancialAnomaly] = []
    for series_key in time_series.visible_series:
        anomalies.extend(_detect_series_anomalies(time_series.points, series_key))

    anomalies.sort(
        key=lambda item: (item.score, abs(item.value - item.baseline)),
        reverse=True,
    )
    if not anomalies:
        return AnomalyDetectionResult(
            anomalies=(),
            total_found=0,
            message="No unusual periods found with the current grouping.",
        )

    return AnomalyDetectionResult(
        anomalies=tuple(anomalies[:max_items]),
        total_found=len(anomalies),
    )


def _detect_series_anomalies(
    points: list[TimeSeriesPoint],
    series_key: str,
) -> list[FinancialAnomaly]:
    """Detect anomalies for one numeric chart series."""
    values_by_point = []
    for point in points:
        value = _point_value(point, series_key)
        if isfinite(value):
            values_by_point.append((point, value))
    if len(values_by_point) < MIN_PERIODS_FOR_ANOMALIES:
        return []

    values = pd.Series([value for _point, value in values_by_point], dtype="float64")
    if values.abs().sum() == 0:
        return []

    stats = _series_stats(values)
    allowed_directions = SERIES_DIRECTIONS.get(series_key, ())
    anomalies = []

    for point, value in values_by_point:
        for direction in allowed_directions:
            anomaly = _build_anomaly(point, series_key, value, direction, stats)
            if anomaly is not None:
                anomalies.append(anomaly)
                break

    return anomalies


def _series_stats(values: pd.Series) -> dict[str, float | None]:
    """Calculate reusable thresholds for one series."""
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    iqr = q3 - q1
    mean = float(values.mean())
    std = float(values.std(ddof=0))
    median = float(values.median())

    high_iqr_bound = q3 + IQR_MULTIPLIER * iqr if iqr > 0 else None
    low_iqr_bound = q1 - IQR_MULTIPLIER * iqr if iqr > 0 else None
    high_z_bound = mean + Z_SCORE_THRESHOLD * std if std > 0 else None
    low_z_bound = mean - Z_SCORE_THRESHOLD * std if std > 0 else None

    return {
        "median": median,
        "std": std,
        "high_iqr_bound": high_iqr_bound,
        "low_iqr_bound": low_iqr_bound,
        "high_z_bound": high_z_bound,
        "low_z_bound": low_z_bound,
    }


def _build_anomaly(
    point: TimeSeriesPoint,
    series_key: str,
    value: float,
    direction: str,
    stats: dict[str, float | None],
) -> FinancialAnomaly | None:
    """Return an anomaly when a value crosses IQR or Z-score thresholds."""
    rules = []
    scores = []

    iqr_bound = stats[f"{direction}_iqr_bound"]
    if iqr_bound is not None and _crosses_bound(value, iqr_bound, direction):
        rules.append("IQR")
        scores.append(_relative_distance(value, iqr_bound))

    z_bound = stats[f"{direction}_z_bound"]
    if z_bound is not None and _crosses_bound(value, z_bound, direction):
        rules.append("Z-score")
        std = float(stats["std"] or 1.0)
        scores.append(abs(value - float(stats["median"])) / std)

    if not rules:
        return None

    score = max(scores) if scores else 0.0
    return FinancialAnomaly(
        period=point.period,
        series_key=series_key,
        series_label=SERIES_LABELS.get(series_key, series_key.title()),
        kind=_anomaly_kind(series_key, direction),
        value=value,
        baseline=float(stats["median"] or 0.0),
        score=score,
        rule=", ".join(rules),
        severity="High" if score >= 3 else "Medium",
    )


def _point_value(point: TimeSeriesPoint, series_key: str) -> float:
    """Read one numeric value from a time-series point."""
    return float(getattr(point, series_key))


def _crosses_bound(value: float, bound: float, direction: str) -> bool:
    """Return whether a value crosses a high or low threshold."""
    if direction == "high":
        return value > bound
    return value < bound


def _relative_distance(value: float, bound: float) -> float:
    """Return a scale-independent distance from a threshold."""
    denominator = max(abs(bound), 1.0)
    return 1.0 + abs(value - bound) / denominator


def _anomaly_kind(series_key: str, direction: str) -> str:
    """Return a user-facing anomaly kind."""
    if direction == "low":
        return "drop"
    return "spike"
