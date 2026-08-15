"""Assemble a print-ready report model from analysis results.

Depth and language are applied here and nowhere else. By the time a writer
receives the model, every number is a formatted string in the target language
and every section that does not apply is simply absent.

Numbers pass through the same `format_money` and `format_number` helpers the
window uses, so an exported report always agrees with what was on screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.analytics.metrics import BasicMetrics, format_money, format_number
from app.analytics.time_series import TIME_GROUPINGS, TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult
from app.reports.chart_image import render_chart_png
from app.reports.insights import generate_insights
from app.reports.model import ReportModel, ReportSection, ReportTable
from app.reports.strings import label


DEPTH_BRIEF = "brief"
DEPTH_DETAILED = "detailed"
DEPTHS = (DEPTH_BRIEF, DEPTH_DETAILED)

BRIEF_CATEGORY_LIMIT = 5
BRIEF_ANOMALY_LIMIT = 8

DATE_FORMAT = "%d.%m.%Y"


@dataclass(frozen=True)
class ReportRequest:
    """What the user chose in the export dialog."""

    file_name: str
    depth: str = DEPTH_BRIEF
    language: str = "ru"
    grouping: str = "day"
    include_chart: bool = True

    @property
    def is_detailed(self) -> bool:
        """Return whether the full report was requested."""
        return self.depth == DEPTH_DETAILED


def build_report(
    metrics: BasicMetrics,
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult,
    request: ReportRequest,
) -> ReportModel:
    """Turn analysis results into a model every writer can lay out."""
    language = request.language

    return ReportModel(
        title=label(language, "report_title"),
        generated_at=datetime.now(),
        source=_build_source(metrics, request),
        summary=_build_summary(metrics, request),
        insights=generate_insights(metrics, time_series, anomalies, language),
        categories=_build_categories(metrics, request),
        anomalies=_build_anomalies(anomalies, request),
        periods=_build_periods(time_series, request) if request.is_detailed else None,
        chart_png=_build_chart(time_series, anomalies, request),
        language=language,
        depth=request.depth,
    )


def _build_source(metrics: BasicMetrics, request: ReportRequest) -> ReportSection:
    """Describe where the numbers came from."""
    language = request.language
    rows: list[tuple[str, str]] = [
        (label(language, "source_file"), request.file_name),
        (label(language, "source_transactions"), format_number(metrics.transaction_count)),
    ]

    period = _format_period(metrics, language)
    if period is not None:
        rows.insert(1, (label(language, "source_period"), period))

    grouping_key = f"grouping_{request.grouping}"
    if request.grouping in TIME_GROUPINGS:
        rows.append((label(language, "source_grouping"), label(language, grouping_key)))

    return ReportSection(title=label(language, "section_source"), rows=tuple(rows))


def _build_summary(metrics: BasicMetrics, request: ReportRequest) -> ReportSection:
    """Build the metric list at the requested depth."""
    language = request.language
    amount_only = _is_amount_only(metrics)
    rows: list[tuple[str, str]] = [
        (label(language, "metric_transactions"), format_number(metrics.transaction_count)),
    ]

    if amount_only:
        rows.append((label(language, "metric_amount"), _money(metrics.total_profit, language)))
    else:
        rows.extend(
            [
                (label(language, "metric_revenue"), _money(metrics.total_revenue, language)),
                (label(language, "metric_expenses"), _money(metrics.total_expenses, language)),
                (label(language, "metric_profit"), _money(metrics.total_profit, language)),
            ]
        )

    if metrics.average_daily_profit is not None:
        rows.append(
            (
                label(language, "metric_average_daily_profit"),
                _money(metrics.average_daily_profit, language),
            )
        )

    if not request.is_detailed:
        return ReportSection(title=label(language, "section_summary"), rows=tuple(rows))

    rows.extend(
        [
            (
                label(language, "metric_average_revenue"),
                _money(metrics.average_revenue, language),
            ),
            (
                label(language, "metric_average_expense"),
                _money(metrics.average_expense, language),
            ),
        ]
    )

    if metrics.period_days is not None:
        rows.append(
            (label(language, "metric_period_days"), format_number(metrics.period_days))
        )
    if metrics.average_daily_revenue is not None:
        rows.append(
            (
                label(language, "metric_average_daily_revenue"),
                _money(metrics.average_daily_revenue, language),
            )
        )
    if metrics.average_daily_expense is not None:
        rows.append(
            (
                label(language, "metric_average_daily_expense"),
                _money(metrics.average_daily_expense, language),
            )
        )

    rows.extend(
        [
            (
                label(language, "metric_revenue_fields"),
                format_number(metrics.revenue_column_count),
            ),
            (
                label(language, "metric_expense_fields"),
                format_number(metrics.expense_column_count),
            ),
            (
                label(language, "metric_amount_fields"),
                format_number(metrics.amount_column_count),
            ),
            (
                label(language, "metric_category_fields"),
                format_number(metrics.category_column_count),
            ),
        ]
    )

    return ReportSection(title=label(language, "section_summary"), rows=tuple(rows))


def _build_categories(metrics: BasicMetrics, request: ReportRequest) -> ReportTable | None:
    """Build the category breakdown, or nothing when no categories were selected."""
    if not metrics.top_categories:
        return None

    language = request.language
    categories = metrics.top_categories
    if not request.is_detailed:
        categories = categories[:BRIEF_CATEGORY_LIMIT]

    rows = tuple(
        (
            category.name,
            format_number(category.transaction_count),
            _money(category.revenue, language),
            _money(category.expenses, language),
            _money(category.profit, language),
        )
        for category in categories
    )

    return ReportTable(
        title=label(language, "section_categories"),
        headers=(
            label(language, "header_category"),
            label(language, "header_transactions"),
            label(language, "header_revenue"),
            label(language, "header_expenses"),
            label(language, "header_profit"),
        ),
        rows=rows,
    )


def _build_anomalies(
    anomalies: AnomalyDetectionResult,
    request: ReportRequest,
) -> ReportTable | None:
    """Build the anomaly table, or nothing when none were found."""
    if not anomalies.has_anomalies:
        return None

    language = request.language
    items = anomalies.anomalies
    if not request.is_detailed:
        items = items[:BRIEF_ANOMALY_LIMIT]

    rows = tuple(
        (
            f"{anomaly.period:{DATE_FORMAT}}",
            anomaly.series_label,
            label(language, "anomaly_drop" if anomaly.kind == "drop" else "anomaly_spike"),
            _money(anomaly.value, language),
            _money(anomaly.baseline, language),
            label(language, _severity_key(anomaly.severity)),
        )
        for anomaly in items
    )

    return ReportTable(
        title=label(language, "section_anomalies"),
        headers=(
            label(language, "header_period"),
            label(language, "header_indicator"),
            label(language, "header_kind"),
            label(language, "header_value"),
            label(language, "header_baseline"),
            label(language, "header_severity"),
        ),
        rows=rows,
    )


def _build_periods(
    time_series: TimeSeriesResult,
    request: ReportRequest,
) -> ReportTable | None:
    """Build the per-period table used only by detailed reports."""
    if not time_series.points:
        return None

    language = request.language
    amount_only = time_series.visible_series == ("amount",)

    if amount_only:
        headers = (label(language, "header_period"), label(language, "header_amount"))
        rows = tuple(
            (f"{point.period:{DATE_FORMAT}}", _money(point.amount, language))
            for point in time_series.points
        )
    else:
        headers = (
            label(language, "header_period"),
            label(language, "header_revenue"),
            label(language, "header_expenses"),
            label(language, "header_profit"),
        )
        rows = tuple(
            (
                f"{point.period:{DATE_FORMAT}}",
                _money(point.revenue, language),
                _money(point.expenses, language),
                _money(point.profit, language),
            )
            for point in time_series.points
        )

    return ReportTable(
        title=label(language, "section_periods"),
        headers=headers,
        rows=rows,
    )


def _build_chart(
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult,
    request: ReportRequest,
) -> bytes | None:
    """Render the chart image, unless the caller asked to skip it."""
    if not request.include_chart:
        return None
    return render_chart_png(time_series, anomalies)


def _build_period_text(value: datetime | None) -> str:
    """Format one boundary date."""
    return f"{value:{DATE_FORMAT}}" if value is not None else ""


def _format_period(metrics: BasicMetrics, language: str) -> str | None:
    """Format the analysed date range, or None when there are no dates."""
    if metrics.date_min is None or metrics.date_max is None:
        return None

    start = _build_period_text(metrics.date_min)
    end = _build_period_text(metrics.date_max)
    if start == end:
        return start

    days = metrics.period_days
    span = f" ({format_number(days)})" if days is not None else ""
    return f"{start} — {end}{span}"


def _is_amount_only(metrics: BasicMetrics) -> bool:
    """Return whether the analysis used only signed amount columns."""
    return bool(
        metrics.amount_column_count
        and not metrics.revenue_column_count
        and not metrics.expense_column_count
    )


def _severity_key(severity: str) -> str:
    """Map an anomaly severity onto a label key."""
    return "severity_high" if severity.lower() == "high" else "severity_medium"


def _money(value: float | None, language: str) -> str:
    """Format money, using the localised placeholder when it is missing."""
    if value is None:
        return label(language, "not_available")
    return format_money(value)
