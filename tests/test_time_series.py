"""Tests for time-series aggregation and chart series visibility."""

from datetime import datetime

import pandas as pd

from app.analytics.metrics import SelectedColumns, prepare_financial_data
from app.analytics.time_series import calculate_time_series


def make_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": [f"0{day}.01.2026" for day in range(1, 9)],
            "Sales": [1000.0, 1200.0, 900.0, 1500.0, 1100.0, 1300.0, 1250.0, 1400.0],
            "Shipping": [20.0, 25.0, 18.0, 30.0, 22.0, 26.0, 24.0, 28.0],
            "Region": ["North", "South", "North", "East", "South", "North", "East", "South"],
        }
    )


def series_for(selected: SelectedColumns):
    prepared = prepare_financial_data(make_frame(), selected)
    return calculate_time_series(prepared, "day", "monday")


def test_revenue_and_expense_columns_show_all_three_series():
    result = series_for(SelectedColumns(date="Date", revenue="Sales", expense="Shipping"))

    assert result.visible_series == ("revenue", "expenses", "profit")


def test_amount_only_analysis_shows_amount():
    result = series_for(SelectedColumns(date="Date", amount="Sales"))

    assert result.visible_series == ("amount",)


def test_revenue_only_analysis_shows_revenue():
    result = series_for(SelectedColumns(date="Date", revenue="Sales"))

    assert result.visible_series == ("revenue",)


def test_expense_only_analysis_shows_expenses():
    result = series_for(SelectedColumns(date="Date", expense="Shipping"))

    assert result.visible_series == ("expenses",)


def test_amount_plus_expense_still_shows_the_revenue_inside_the_amount():
    """A signed amount feeds revenue; selecting an expense too must not hide it.

    This is the shape automatic detection produces for a sales export whose
    money column is a positive total and whose only named cost is shipping.
    """
    result = series_for(SelectedColumns(date="Date", amount="Sales", expense="Shipping"))

    assert result.visible_series == ("revenue", "expenses", "profit")


def test_amount_derived_revenue_carries_the_real_total():
    result = series_for(SelectedColumns(date="Date", amount="Sales", expense="Shipping"))

    assert sum(point.revenue for point in result.points) == 9650.0
    assert sum(point.expenses for point in result.points) == 193.0


def test_periods_are_sorted():
    result = series_for(SelectedColumns(date="Date", revenue="Sales"))
    periods = [point.period for point in result.points]

    assert periods == sorted(periods)
    assert periods[0] == datetime(2026, 1, 1)


def test_no_date_column_yields_a_message_and_no_points():
    result = series_for(SelectedColumns(revenue="Sales"))

    assert result.points == []
    assert result.visible_series == ()
    assert "date" in result.message.lower()
