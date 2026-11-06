"""Simple cash runway estimates from an explicit balance and dated net profit."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from app.analytics.metrics import BasicMetrics


@dataclass(frozen=True)
class CashFlowResult:
    """Historical-average estimates, not a bank balance or cash-flow statement."""

    cash_balance: float | None
    daily_net_burn: float | None
    runway_days: float | None
    projected_balance_30_days: float | None


def calculate_cash_flow(
    metrics: BasicMetrics,
    cash_balance: float | None = None,
) -> CashFlowResult:
    """Estimate runway from losses; never infer cash from historical profit.

    Daily net burn is nonnegative. A profitable or break-even period has zero
    burn and no finite runway estimate. The 30-day projection uses the signed
    historical daily profit, and may be negative. Missing cash or dated profit
    leaves the affected estimates unavailable.
    """
    if cash_balance is not None:
        try:
            balance = float(cash_balance)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Cash balance must be a finite nonnegative number.") from error
        if isinstance(cash_balance, bool) or not isfinite(balance) or balance < 0:
            raise ValueError("Cash balance must be a finite nonnegative number.")
        cash_balance = balance

    daily_profit = metrics.average_daily_profit
    if (
        metrics.date_min is None
        or metrics.undated_money_rows > 0
        or metrics.date_max is None
        or metrics.period_days is None
        or metrics.period_days <= 0
        or metrics.total_profit is None
        or not isfinite(metrics.total_profit)
        or daily_profit is None
        or not isfinite(daily_profit)
    ):
        return CashFlowResult(cash_balance, None, None, None)

    daily_burn = max(-daily_profit, 0.0)
    runway = None
    projection = None
    if cash_balance is not None:
        if daily_burn > 0:
            runway = cash_balance / daily_burn
            if not isfinite(runway):
                runway = None
        projection = cash_balance + daily_profit * 30
        if not isfinite(projection):
            projection = None
    return CashFlowResult(cash_balance, daily_burn, runway, projection)
