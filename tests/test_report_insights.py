"""Tests for rule-based report insights."""

from datetime import datetime

from app.analytics.metrics import CategoryMetric, build_basic_metrics
from app.ml.anomaly_detection import AnomalyDetectionResult, FinancialAnomaly
from app.reports.insights import MAX_INSIGHTS, generate_insights
from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult


def make_point(day: int, revenue: float, expenses: float) -> TimeSeriesPoint:
    """Build one aggregated point with profit derived from the two sides."""
    return TimeSeriesPoint(
        period=datetime(2026, 1, day),
        revenue=revenue,
        expenses=expenses,
        profit=revenue - expenses,
        amount=revenue - expenses,
    )


def make_series(points: list[TimeSeriesPoint]) -> TimeSeriesResult:
    return TimeSeriesResult(
        points=points,
        grouping="day",
        week_start="monday",
        visible_series=("revenue", "expenses", "profit"),
    )


EMPTY_SERIES = make_series([])
NO_ANOMALIES = AnomalyDetectionResult(anomalies=(), total_found=0)


def make_metrics(**overrides) -> object:
    """Build metrics with sensible defaults for insight tests."""
    values = {
        "transaction_count": 100,
        "total_revenue": 1_000_000.0,
        "total_expenses": 600_000.0,
        "date_min": datetime(2026, 1, 1),
        "date_max": datetime(2026, 1, 10),
    }
    values.update(overrides)
    return build_basic_metrics(**values)


# Rule 1: last period against the previous one.


def test_profit_growth_between_last_two_periods_is_reported():
    series = make_series([make_point(1, 100.0, 50.0), make_point(2, 150.0, 50.0)])
    insights = generate_insights(make_metrics(), series, NO_ANOMALIES, "en")

    assert any("rose 100%" in text for text in insights)


def test_profit_fall_between_last_two_periods_is_reported():
    series = make_series([make_point(1, 300.0, 100.0), make_point(2, 200.0, 100.0)])
    insights = generate_insights(make_metrics(), series, NO_ANOMALIES, "en")

    assert any("fell 50%" in text for text in insights)


def test_period_comparison_is_silent_with_a_single_period():
    series = make_series([make_point(1, 100.0, 50.0)])
    insights = generate_insights(make_metrics(), series, NO_ANOMALIES, "en")

    assert not any("last period" in text for text in insights)


def test_period_comparison_is_silent_when_previous_profit_is_zero():
    series = make_series([make_point(1, 100.0, 100.0), make_point(2, 200.0, 100.0)])
    insights = generate_insights(make_metrics(), series, NO_ANOMALIES, "en")

    assert not any("last period" in text for text in insights)


# Rule 3: category concentration.


def test_dominant_category_share_is_reported():
    categories = (
        CategoryMetric("Продажи", 50, 750.0, 0.0, 750.0),
        CategoryMetric("Аренда", 10, 0.0, 250.0, -250.0),
    )
    insights = generate_insights(
        make_metrics(top_categories=categories, category_column_count=1),
        EMPTY_SERIES,
        NO_ANOMALIES,
        "en",
    )

    assert any("Продажи" in text and "75%" in text for text in insights)


def test_category_rule_is_silent_without_categories():
    insights = generate_insights(make_metrics(), EMPTY_SERIES, NO_ANOMALIES, "en")

    assert not any("turnover" in text for text in insights)


# Rule 4: anomalies.


def test_anomaly_count_and_most_notable_are_reported():
    anomaly = FinancialAnomaly(
        period=datetime(2026, 3, 31),
        series_key="expenses",
        series_label="Expenses",
        kind="spike",
        value=900.0,
        baseline=100.0,
        score=4.0,
        rule="IQR",
        severity="High",
    )
    result = AnomalyDetectionResult(anomalies=(anomaly,), total_found=3)
    insights = generate_insights(make_metrics(), EMPTY_SERIES, result, "en")

    assert any("3" in text and "spike" in text for text in insights)


def test_anomaly_rule_is_silent_without_anomalies():
    insights = generate_insights(make_metrics(), EMPTY_SERIES, NO_ANOMALIES, "en")

    assert not any("Unusual periods" in text for text in insights)


# Rule 5: burn rate and cash gap.


def test_burn_rate_is_reported_when_daily_expense_is_known():
    insights = generate_insights(make_metrics(), EMPTY_SERIES, NO_ANOMALIES, "en")

    assert any("per day" in text for text in insights)


def test_cash_gap_warning_fires_only_on_negative_daily_profit():
    losing = make_metrics(total_revenue=100_000.0, total_expenses=900_000.0)
    earning = make_metrics(total_revenue=900_000.0, total_expenses=100_000.0)

    losing_insights = generate_insights(losing, EMPTY_SERIES, NO_ANOMALIES, "en")
    earning_insights = generate_insights(earning, EMPTY_SERIES, NO_ANOMALIES, "en")

    assert any("cash gap" in text for text in losing_insights)
    assert not any("cash gap" in text for text in earning_insights)


# Whole-function behaviour.


def test_empty_analysis_produces_no_insights_instead_of_raising():
    metrics = build_basic_metrics(
        transaction_count=0,
        total_revenue=None,
        total_expenses=None,
    )
    assert generate_insights(metrics, EMPTY_SERIES, NO_ANOMALIES, "en") == ()


def test_insight_count_is_capped():
    points = [make_point(day, day * 100.0, 50.0) for day in range(1, 9)]
    categories = (CategoryMetric("Продажи", 50, 750.0, 0.0, 750.0),)
    anomaly = FinancialAnomaly(
        period=datetime(2026, 1, 8),
        series_key="revenue",
        series_label="Revenue",
        kind="spike",
        value=800.0,
        baseline=100.0,
        score=4.0,
        rule="IQR",
        severity="High",
    )
    insights = generate_insights(
        make_metrics(top_categories=categories, category_column_count=1),
        make_series(points),
        AnomalyDetectionResult(anomalies=(anomaly,), total_found=5),
        "en",
    )

    assert len(insights) <= MAX_INSIGHTS


def test_russian_output_is_russian():
    series = make_series([make_point(1, 100.0, 50.0), make_point(2, 150.0, 50.0)])
    insights = generate_insights(make_metrics(), series, NO_ANOMALIES, "ru")

    assert any("Прибыль" in text for text in insights)


def test_no_insight_contains_nan_or_inf():
    series = make_series([make_point(1, 0.0, 0.0), make_point(2, 0.0, 0.0)])
    insights = generate_insights(
        make_metrics(total_revenue=0.0, total_expenses=0.0),
        series,
        NO_ANOMALIES,
        "en",
    )

    for text in insights:
        assert "nan" not in text.lower()
        assert "inf" not in text.lower()
