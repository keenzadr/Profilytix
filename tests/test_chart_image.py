"""Tests for chart rendering and anomaly markers."""

from datetime import datetime

from matplotlib.figure import Figure

from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult, FinancialAnomaly
from app.reports.chart_image import (
    draw_anomaly_markers,
    draw_time_series_chart,
    format_chart_axis_value,
    render_chart_png,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def make_series(point_count: int = 6) -> TimeSeriesResult:
    points = [
        TimeSeriesPoint(
            period=datetime(2026, 1, day),
            revenue=100.0 * day,
            expenses=50.0 * day,
            profit=50.0 * day,
            amount=50.0 * day,
        )
        for day in range(1, point_count + 1)
    ]
    return TimeSeriesResult(
        points=points,
        grouping="day",
        week_start="monday",
        visible_series=("revenue", "expenses", "profit"),
    )


def make_anomalies() -> AnomalyDetectionResult:
    items = (
        FinancialAnomaly(
            period=datetime(2026, 1, 3),
            series_key="revenue",
            series_label="Revenue",
            kind="spike",
            value=300.0,
            baseline=150.0,
            score=3.0,
            rule="IQR",
            severity="High",
        ),
        FinancialAnomaly(
            period=datetime(2026, 1, 5),
            series_key="profit",
            series_label="Profit",
            kind="drop",
            value=250.0,
            baseline=400.0,
            score=2.6,
            rule="Z-score",
            severity="Medium",
        ),
    )
    return AnomalyDetectionResult(anomalies=items, total_found=2)


def test_render_returns_png_bytes():
    result = render_chart_png(make_series(), make_anomalies())

    assert result is not None
    assert result[:8] == PNG_SIGNATURE
    assert len(result) > 1000


def test_render_returns_none_without_points():
    empty = TimeSeriesResult(points=[], grouping="day", week_start="monday")

    assert render_chart_png(empty, None) is None


def test_render_returns_none_without_visible_series():
    series = make_series()
    without_series = TimeSeriesResult(
        points=series.points,
        grouping="day",
        week_start="monday",
        visible_series=(),
    )

    assert render_chart_png(without_series, None) is None


def test_render_works_without_anomalies():
    result = render_chart_png(make_series(), None)

    assert result is not None
    assert result[:8] == PNG_SIGNATURE


def test_markers_are_drawn_for_each_anomaly():
    figure = Figure()
    axes = figure.add_subplot(111)
    series = make_series()
    draw_time_series_chart(axes, figure, series)
    before = len(axes.lines)

    added = draw_anomaly_markers(axes, series, make_anomalies())

    assert added == 2
    assert len(axes.lines) > before


def test_markers_ignore_series_that_are_not_visible():
    figure = Figure()
    axes = figure.add_subplot(111)
    series = TimeSeriesResult(
        points=make_series().points,
        grouping="day",
        week_start="monday",
        visible_series=("amount",),
    )
    draw_time_series_chart(axes, figure, series)

    assert draw_anomaly_markers(axes, series, make_anomalies()) == 0


def test_markers_do_not_move_axis_limits():
    figure = Figure()
    axes = figure.add_subplot(111)
    series = make_series()
    draw_time_series_chart(axes, figure, series)
    limits_before = (axes.get_xlim(), axes.get_ylim())

    draw_anomaly_markers(axes, series, make_anomalies())

    assert (axes.get_xlim(), axes.get_ylim()) == limits_before


def test_axis_values_use_compact_suffixes():
    assert format_chart_axis_value(0) == "0"
    assert format_chart_axis_value(1_500) == "1.5k"
    assert format_chart_axis_value(2_000_000) == "2m"
    assert format_chart_axis_value(-1_200) == "-1.2k"
