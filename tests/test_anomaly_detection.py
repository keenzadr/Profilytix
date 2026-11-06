"""Tests for simple financial anomaly detection."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from math import isfinite

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


class IsolationForestTests(unittest.TestCase):
    """Optional ML detection preserves financial direction and safe fallbacks."""

    def make_series(self, values: list[float], key: str = "expenses") -> TimeSeriesResult:
        start = datetime(2026, 1, 1)
        return TimeSeriesResult(
            points=[
                TimeSeriesPoint(start + timedelta(days=i), value, value, value, value)
                for i, value in enumerate(values)
            ],
            grouping="day",
            week_start="monday",
            visible_series=(key,),
        )

    def test_detects_real_spike_deterministically(self) -> None:
        series = self.make_series([100, 101, 99, 102, 98, 100, 101, 99, 100, 1000])
        first = detect_financial_anomalies(series, method="isolation_forest")
        second = detect_financial_anomalies(series, method="isolation_forest")

        self.assertEqual(first, second)
        self.assertTrue(first.has_anomalies)
        spike = next(item for item in first.anomalies if item.value == 1000)
        self.assertEqual(spike.kind, "spike")
        self.assertEqual(spike.rule, "Isolation Forest")
        self.assertTrue(isfinite(spike.score))

    def test_direction_filters_revenue_drop_and_profit_spike(self) -> None:
        for key, values in (
            ("revenue", [100] * 15 + [-1000]),
            ("expenses", [100] * 15 + [-1000]),
            ("profit", [100] * 15 + [1000]),
        ):
            with self.subTest(key=key):
                result = detect_financial_anomalies(
                    self.make_series(values, key), method="isolation_forest"
                )
                self.assertFalse(result.has_anomalies)

    def test_profit_drop_and_amount_directions(self) -> None:
        for key, value, kind in (("profit", -1000, "drop"), ("amount", -1000, "drop"),
                                 ("amount", 1000, "spike")):
            with self.subTest(key=key, value=value):
                result = detect_financial_anomalies(
                    self.make_series([100] * 15 + [value], key), method="isolation_forest"
                )
                self.assertTrue(any(item.value == value and item.kind == kind
                                    for item in result.anomalies))

    def test_short_constant_and_nonfinite_data_have_no_anomalies(self) -> None:
        for values in ([], [100, 100, 1000], [7] * 16, [0] * 16,
                       [float("nan"), float("inf"), float("-inf")] * 8,
                       [100, 101, 99, 1000] + [float("nan")] * 10):
            with self.subTest(values=values):
                result = detect_financial_anomalies(
                    self.make_series(values), method="isolation_forest"
                )
                self.assertFalse(result.has_anomalies)
                self.assertTrue(result.message)

    def test_nonfinite_values_are_skipped_while_spike_is_detected(self) -> None:
        result = detect_financial_anomalies(
            self.make_series([100] * 15 + [float("nan"), float("inf"), 1000]),
            method="isolation_forest",
        )
        self.assertEqual([item.value for item in result.anomalies], [1000])

    def test_large_finite_values_do_not_overflow_model_or_baseline(self) -> None:
        result = detect_financial_anomalies(
            self.make_series([1e308] * 15 + [1.7e308]), method="isolation_forest"
        )
        self.assertEqual(len(result.anomalies), 1)
        self.assertEqual(result.anomalies[0].value, 1.7e308)
        self.assertEqual(result.anomalies[0].baseline, 1e308)

    def test_limit_keeps_total_count(self) -> None:
        result = detect_financial_anomalies(
            self.make_series([100] * 20 + [-1000, 1000], "amount"),
            1,
            method="isolation_forest",
        )
        self.assertEqual(len(result.anomalies), 1)
        self.assertEqual(result.total_found, 2)

    def test_default_rules_match_explicit_method(self) -> None:
        series = self.make_series([100, 110, 95, 105, 500, 98, 102, 99])
        self.assertEqual(detect_financial_anomalies(series),
                         detect_financial_anomalies(series, method="rules"))

    def test_invalid_method_is_rejected_even_on_empty_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            detect_financial_anomalies(self.make_series([]), method="unknown")


if __name__ == "__main__":
    unittest.main()
