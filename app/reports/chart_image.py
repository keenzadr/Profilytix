"""Chart drawing shared by the on-screen window and the exported report.

This module must not import PySide6. It builds Matplotlib figures through the
Agg backend directly, without touching the global backend, so the Qt canvas in
`app/ui/main_window.py` keeps working while reports render off-screen.

`main_window.py` imports the drawing functions from here rather than keeping
its own copy, which is what keeps the exported chart identical to the one the
user just looked at.
"""

from __future__ import annotations

from io import BytesIO

from app.analytics.time_series import TIME_GROUPINGS, TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult

try:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
except ImportError:  # pragma: no cover - matplotlib is a hard dependency
    FigureCanvasAgg = None
    Figure = None
    FuncFormatter = None


CHART_SERIES_LABELS = {
    "revenue": "Revenue",
    "expenses": "Expenses",
    "profit": "Profit",
    "amount": "Amount",
}

ANOMALY_MARKER_COLOR = "#d62728"
ANOMALY_SPIKE_MARKER = "v"
ANOMALY_DROP_MARKER = "^"
ANOMALY_LEGEND_LABEL = "Anomaly"

FORECAST_LEGEND_LABEL = "Forecast"

EXPORT_WIDTH_INCHES = 10.0
EXPORT_HEIGHT_INCHES = 4.5
EXPORT_DPI = 150


def format_chart_axis_value(value: float, _position: object = None) -> str:
    """Format chart axis values with compact suffixes."""
    if value == 0:
        return "0"

    sign = "-" if value < 0 else ""
    absolute_value = abs(value)
    for scale, suffix in (
        (1_000_000_000, "b"),
        (1_000_000, "m"),
        (1_000, "k"),
    ):
        if absolute_value >= scale:
            scaled = absolute_value / scale
            text = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"{sign}{text}{suffix}"

    if absolute_value >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_chart_title(series_keys: tuple[str, ...], group_label: str) -> str:
    """Build a chart title from visible series."""
    labels = [CHART_SERIES_LABELS[key].lower() for key in series_keys]
    if not labels:
        return f"Selected values by {group_label}"
    if len(labels) == 1:
        series_text = labels[0].capitalize()
    elif len(labels) == 2:
        series_text = f"{labels[0].capitalize()} and {labels[1]}"
    else:
        series_text = f"{', '.join(labels[:-1]).capitalize()}, and {labels[-1]}"
    return f"{series_text} by {group_label}"


def draw_time_series_chart(
    axes: object,
    figure: object,
    time_series: TimeSeriesResult,
) -> list[tuple[object, str]]:
    """Draw a time-series chart and return hoverable line metadata."""
    periods = [point.period for point in time_series.points]
    series_values = {
        "revenue": [point.revenue for point in time_series.points],
        "expenses": [point.expenses for point in time_series.points],
        "profit": [point.profit for point in time_series.points],
        "amount": [point.amount for point in time_series.points],
    }

    lines = []
    axes.set_axis_on()
    for series_key in time_series.visible_series:
        (line,) = axes.plot(
            periods,
            series_values[series_key],
            label=CHART_SERIES_LABELS[series_key],
            linewidth=1.8,
            solid_capstyle="round",
        )
        lines.append((line, series_key))

    axes.grid(True, alpha=0.25)
    axes.legend(loc="best")
    if FuncFormatter is not None:
        axes.yaxis.set_major_formatter(FuncFormatter(format_chart_axis_value))
        axes.yaxis.get_offset_text().set_visible(False)
    group_label = TIME_GROUPINGS[time_series.grouping].lower()
    axes.set_title(format_chart_title(time_series.visible_series, group_label))
    figure.autofmt_xdate()
    return lines


def draw_anomaly_markers(
    axes: object,
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult | None,
) -> int:
    """Mark detected anomalies on an already drawn chart.

    Markers sit exactly on the data points they describe, so the axis limits
    cannot move as a side effect of drawing them. Returns how many markers were
    added, which the caller uses to decide whether the legend needs redrawing.
    """
    if anomalies is None or not anomalies.has_anomalies or not time_series.points:
        return 0

    visible = set(time_series.visible_series)
    spikes: list[tuple[object, float]] = []
    drops: list[tuple[object, float]] = []

    for anomaly in anomalies.anomalies:
        if anomaly.series_key not in visible:
            continue
        target = drops if anomaly.kind == "drop" else spikes
        target.append((anomaly.period, anomaly.value))

    added = 0
    for points, marker in ((spikes, ANOMALY_SPIKE_MARKER), (drops, ANOMALY_DROP_MARKER)):
        if not points:
            continue
        axes.plot(
            [period for period, _value in points],
            [value for _period, value in points],
            linestyle="none",
            marker=marker,
            markersize=9,
            color=ANOMALY_MARKER_COLOR,
            markeredgecolor="white",
            markeredgewidth=0.8,
            label=ANOMALY_LEGEND_LABEL if added == 0 else None,
            zorder=5,
        )
        added += len(points)

    if added:
        axes.legend(loc="best")

    return added


def draw_forecast(
    axes: object,
    time_series: TimeSeriesResult,
    forecast: object | None,
    chart_lines: list[tuple[object, str]],
) -> int:
    """Draw each forecast as a dashed continuation of its own series.

    The dashed segment starts at the last observed point, so the projection
    visibly grows out of the data instead of floating beside it. Returns how
    many series were extended.
    """
    if forecast is None or not getattr(forecast, "has_forecast", False):
        return 0
    if not time_series.points:
        return 0

    colors_by_series = {series_key: line.get_color() for line, series_key in chart_lines}
    last_point = time_series.points[-1]
    added = 0

    for series_key in time_series.visible_series:
        series_forecast = forecast.for_series(series_key)
        if series_forecast is None or not series_forecast.points:
            continue

        periods = [last_point.period] + [point.period for point in series_forecast.points]
        values = [float(getattr(last_point, series_key))] + [
            point.value for point in series_forecast.points
        ]

        axes.plot(
            periods,
            values,
            linestyle="--",
            linewidth=1.5,
            color=colors_by_series.get(series_key, "#888888"),
            alpha=0.85,
            label=FORECAST_LEGEND_LABEL if added == 0 else None,
            zorder=3,
        )
        added += 1

    if added:
        axes.relim()
        axes.autoscale_view()
        axes.legend(loc="best")

    return added


def render_chart_png(
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult | None = None,
    forecast: object | None = None,
    width_in: float = EXPORT_WIDTH_INCHES,
    height_in: float = EXPORT_HEIGHT_INCHES,
    dpi: int = EXPORT_DPI,
) -> bytes | None:
    """Render the chart to PNG bytes, or return None when there is nothing to draw."""
    if Figure is None or FigureCanvasAgg is None:
        return None
    if not time_series.points or not time_series.visible_series:
        return None

    figure = Figure(figsize=(width_in, height_in), dpi=dpi)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)

    chart_lines = draw_time_series_chart(axes, figure, time_series)
    draw_forecast(axes, time_series, forecast, chart_lines)
    draw_anomaly_markers(axes, time_series, anomalies)

    buffer = BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    return buffer.getvalue()
