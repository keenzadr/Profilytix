"""Tests for simple financial anomaly detection."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
from app.ml.anomaly_detection import detect_financial_anomalies


class AnomalyDetectionTests(unittest.TestCase):
    """Focused tests for rule-based anomaly detection."""

    def test_detects_expense_spike_and_profit_drop(self) -> None:
        """A large expense period should also surface as a profit drop."""
        start = datetime(2026, 1, 1)
        expenses = [100, 110, 95, 105, 500, 98, 102, 99]
        points = [
            TimeSeriesPoint(
                period=start + timedelta(days=index),
                revenue=300,
                expenses=expense,
                profit=300 - expense,
                amount=300 - expense,
            )
            for index, expense in enumerate(expenses)
        ]
        time_series = TimeSeriesResult(
            points=points,
            grouping="day",
            week_start="monday",
            visible_series=("revenue", "expenses", "profit"),
        )

        result = detect_financial_anomalies(time_series)
        anomalies = {(item.period.date(), item.series_key, item.kind) for item in result.anomalies}

        self.assertIn((datetime(2026, 1, 5).date(), "expenses", "spike"), anomalies)
        self.assertIn((datetime(2026, 1, 5).date(), "profit", "drop"), anomalies)

    def test_requires_enough_periods(self) -> None:
        """Tiny series should return a clear no-result message."""
        points = [
            TimeSeriesPoint(
                period=datetime(2026, 1, day),
                revenue=100,
                expenses=50,
                profit=50,
                amount=50,
            )
            for day in range(1, 4)
        ]
        time_series = TimeSeriesResult(
            points=points,
            grouping="day",
            week_start="monday",
            visible_series=("profit",),
        )

        result = detect_financial_anomalies(time_series)

        self.assertFalse(result.has_anomalies)
        self.assertIn("Need at least", result.message)


if __name__ == "__main__":
    unittest.main()
