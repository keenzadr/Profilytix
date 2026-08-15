"""Tests for assembling a print-ready report model."""

from datetime import datetime

from app.analytics.metrics import CategoryMetric, build_basic_metrics
from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult, FinancialAnomaly
from app.reports.builder import ReportRequest, build_report
from app.reports.model import ReportModel


def make_series(point_count: int = 6) -> TimeSeriesResult:
    points = [
        TimeSeriesPoint(
            period=datetime(2026, 1, day),
            revenue=100.0 * day,
            expenses=40.0 * day,
            profit=60.0 * day,
            amount=60.0 * day,
        )
        for day in range(1, point_count + 1)
    ]
    return TimeSeriesResult(
        points=points,
        grouping="day",
        week_start="monday",
        visible_series=("revenue", "expenses", "profit"),
    )


def make_categories(count: int) -> tuple[CategoryMetric, ...]:
    return tuple(
        CategoryMetric(
            name=f"Category {index}",
            transaction_count=10 + index,
            revenue=1000.0 - index * 10,
            expenses=100.0,
            profit=900.0 - index * 10,
        )
        for index in range(count)
    )


def make_anomalies(count: int) -> AnomalyDetectionResult:
    items = tuple(
        FinancialAnomaly(
            period=datetime(2026, 1, index + 1),
            series_key="revenue",
            series_label="Revenue",
            kind="spike" if index % 2 == 0 else "drop",
            value=500.0 + index,
            baseline=100.0,
            score=3.0,
            rule="IQR",
            severity="High",
        )
        for index in range(count)
    )
    return AnomalyDetectionResult(anomalies=items, total_found=count)


def make_metrics(**overrides):
    values = {
        "transaction_count": 120,
        "total_revenue": 500_000.0,
        "total_expenses": 300_000.0,
        "revenue_column_count": 1,
        "expense_column_count": 1,
        "category_column_count": 1,
        "date_min": datetime(2026, 1, 1),
        "date_max": datetime(2026, 1, 6),
        "top_categories": make_categories(8),
    }
    values.update(overrides)
    return build_basic_metrics(**values)


def make_request(**overrides) -> ReportRequest:
    values = {
        "file_name": "transactions.csv",
        "depth": "brief",
        "language": "en",
        "grouping": "day",
    }
    values.update(overrides)
    return ReportRequest(**values)


def build(**request_overrides) -> ReportModel:
    return build_report(
        make_metrics(),
        make_series(),
        make_anomalies(12),
        make_request(**request_overrides),
    )


# Depth.


def test_brief_report_has_no_period_table():
    assert build(depth="brief").periods is None


def test_detailed_report_has_a_period_table():
    periods = build(depth="detailed").periods

    assert periods is not None
    assert len(periods.rows) == 6


def test_brief_report_caps_categories_and_anomalies():
    model = build(depth="brief")

    assert len(model.categories.rows) == 5
    assert len(model.anomalies.rows) == 8


def test_detailed_report_keeps_every_category_and_anomaly():
    model = build(depth="detailed")

    assert len(model.categories.rows) == 8
    assert len(model.anomalies.rows) == 12


def test_detailed_report_has_more_metric_rows_than_brief():
    assert len(build(depth="detailed").summary.rows) > len(build(depth="brief").summary.rows)


# Language.


def test_language_selects_section_titles():
    assert build(language="en").summary.title == "Metrics"
    assert build(language="ru").summary.title == "Показатели"


def test_language_is_recorded_on_the_model():
    assert build(language="ru").language == "ru"


def test_anomaly_series_names_are_translated():
    """Anomaly detection labels series in English; the report must not repeat that."""
    russian = build(language="ru").anomalies
    english = build(language="en").anomalies

    assert russian.rows[0][1] == "Выручка"
    assert english.rows[0][1] == "Revenue"


# Shape guarantees every writer relies on.


def test_every_section_value_is_a_string():
    model = build(depth="detailed")

    for section in (model.source, model.summary):
        for label_text, value in section.rows:
            assert isinstance(label_text, str)
            assert isinstance(value, str)

    for table in model.tables():
        for row in table.rows:
            assert all(isinstance(cell, str) for cell in row)


def test_chart_is_rendered_when_points_exist():
    model = build()

    assert model.has_chart
    assert model.chart_png[:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_can_be_switched_off():
    assert build(include_chart=False).chart_png is None


# Degenerate analyses must not raise.


def test_analysis_without_dates_has_no_chart_and_no_periods():
    metrics = build_basic_metrics(
        transaction_count=10,
        total_revenue=100.0,
        total_expenses=50.0,
    )
    empty_series = TimeSeriesResult(points=[], grouping="day", week_start="monday")
    model = build_report(
        metrics,
        empty_series,
        AnomalyDetectionResult(anomalies=(), total_found=0),
        make_request(),
    )

    assert model.chart_png is None
    assert model.periods is None
    assert model.anomalies is None


def test_analysis_without_categories_has_no_category_table():
    metrics = build_basic_metrics(
        transaction_count=10,
        total_revenue=100.0,
        total_expenses=50.0,
        top_categories=(),
    )
    model = build_report(
        metrics,
        make_series(),
        AnomalyDetectionResult(anomalies=(), total_found=0),
        make_request(),
    )

    assert model.categories is None


def test_amount_only_analysis_reports_amount_instead_of_profit():
    metrics = build_basic_metrics(
        transaction_count=10,
        total_revenue=300.0,
        total_expenses=100.0,
        amount_column_count=1,
        date_min=datetime(2026, 1, 1),
        date_max=datetime(2026, 1, 6),
    )
    series = TimeSeriesResult(
        points=make_series().points,
        grouping="day",
        week_start="monday",
        visible_series=("amount",),
    )
    model = build_report(
        metrics,
        series,
        AnomalyDetectionResult(anomalies=(), total_found=0),
        make_request(language="en"),
    )
    labels = [row[0] for row in model.summary.rows]

    assert "Amount" in labels
    assert "Profit" not in labels


def test_forecast_table_is_absent_without_a_forecast():
    assert build().forecast is None


def test_forecast_table_lists_every_projected_series():
    from app.ml.forecasting import forecast_time_series

    series = make_series(8)
    forecast = forecast_time_series(series, periods_ahead=2)
    model = build_report(
        make_metrics(),
        series,
        make_anomalies(2),
        make_request(language="ru"),
        forecast,
    )

    assert model.forecast is not None
    assert len(model.forecast.rows) == len(forecast.forecasts)
    assert model.forecast.title == "Прогноз"
    # Indicator, two projected periods, and the method.
    assert len(model.forecast.headers) == 4
    assert model.forecast in model.tables()


def test_forecast_adds_an_insight():
    from app.ml.forecasting import forecast_time_series

    series = make_series(8)
    model = build_report(
        make_metrics(),
        series,
        make_anomalies(1),
        make_request(language="en"),
        forecast_time_series(series),
    )

    assert any("forecast" in text.lower() for text in model.insights)


def test_title_and_generation_time_are_present():
    model = build()

    assert model.title
    assert isinstance(model.generated_at, datetime)


def test_source_section_names_the_file():
    model = build()
    values = [value for _label, value in model.source.rows]

    assert "transactions.csv" in values
