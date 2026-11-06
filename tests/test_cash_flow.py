"""Cash estimates require real dated profit and an explicit balance."""

from dataclasses import replace
from datetime import datetime
import unittest

from app.analytics.metrics import build_basic_metrics


class CashFlowTests(unittest.TestCase):
    def metrics(self):
        return build_basic_metrics(
            transaction_count=10,
            total_revenue=1000,
            total_expenses=2000,
            date_min=datetime(2026, 1, 1),
            date_max=datetime(2026, 1, 10),
        )

    def calculate(self, metrics, balance=None):
        from app.analytics.cash_flow import calculate_cash_flow
        return calculate_cash_flow(metrics, balance)

    def test_cash_balance_and_loss_produce_runway(self) -> None:
        result = self.calculate(self.metrics(), 2500)
        self.assertEqual(result.cash_balance, 2500)
        self.assertEqual(result.daily_net_burn, 100)
        self.assertEqual(result.runway_days, 25)
        self.assertEqual(result.projected_balance_30_days, -500)

    def test_missing_balance_does_not_invent_cash(self) -> None:
        result = self.calculate(self.metrics())
        self.assertEqual(result.daily_net_burn, 100)
        self.assertIsNone(result.cash_balance)
        self.assertIsNone(result.runway_days)
        self.assertIsNone(result.projected_balance_30_days)

    def test_positive_profit_has_zero_burn_and_growing_balance(self) -> None:
        result = self.calculate(replace(self.metrics(), total_profit=1000,
                                       average_daily_profit=100), 2500)
        self.assertEqual(result.daily_net_burn, 0)
        self.assertIsNone(result.runway_days)
        self.assertEqual(result.projected_balance_30_days, 5500)

    def test_zero_profit_has_no_runway_limit(self) -> None:
        result = self.calculate(replace(self.metrics(), total_profit=0,
                                       average_daily_profit=0), 2500)
        self.assertEqual(result.daily_net_burn, 0)
        self.assertIsNone(result.runway_days)
        self.assertEqual(result.projected_balance_30_days, 2500)

    def test_zero_balance_is_not_missing(self) -> None:
        result = self.calculate(self.metrics(), 0)
        self.assertEqual(result.cash_balance, 0)
        self.assertEqual(result.runway_days, 0)
        self.assertEqual(result.projected_balance_30_days, -3000)

    def test_missing_profit_dates_or_finite_average_prevent_estimates(self) -> None:
        for updates in (
            {"total_profit": None}, {"average_daily_profit": None},
            {"average_daily_profit": float("nan")},
            {"average_daily_profit": float("inf")},
            {"date_min": None}, {"date_max": None}, {"period_days": None},
        ):
            with self.subTest(updates=updates):
                result = self.calculate(replace(self.metrics(), **updates), 2500)
                self.assertEqual(result.cash_balance, 2500)
                self.assertIsNone(result.daily_net_burn)
                self.assertIsNone(result.runway_days)
                self.assertIsNone(result.projected_balance_30_days)

    def test_invalid_balance_is_rejected(self) -> None:
        for balance in (-1, float("nan"), float("inf"), float("-inf"), "bad", True):
            with self.subTest(balance=balance):
                with self.assertRaisesRegex(ValueError, "balance"):
                    self.calculate(self.metrics(), balance)

    def test_overflow_does_not_return_infinite_estimates(self) -> None:
        result = self.calculate(replace(self.metrics(), total_profit=-1e308,
                                       average_daily_profit=-1e308), 1e308)
        self.assertEqual(result.runway_days, 1)
        self.assertIsNone(result.projected_balance_30_days)

        result = self.calculate(replace(self.metrics(), total_profit=-1e-308,
                                       average_daily_profit=-1e-308), 1e308)
        self.assertIsNone(result.runway_days)
        self.assertEqual(result.projected_balance_30_days, 1e308)


if __name__ == "__main__":
    unittest.main()
