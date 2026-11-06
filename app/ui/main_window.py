"""Main application window for Profilytix."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.dates import date2num
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
except ImportError:
    date2num = None
    FigureCanvas = None
    Figure = None
    FuncFormatter = None

from app.analytics.column_detection import (
    COLUMN_ROLES,
    ROLE_LABELS,
    ColumnCandidate,
    ColumnDetectionResult,
    detect_columns,
)
from app.analytics.metrics import (
    BasicMetrics,
    SelectedColumns,
    calculate_basic_metrics_from_prepared,
    format_money,
    format_number,
    prepare_financial_data,
)
from app.analytics.time_series import (
    TIME_GROUPINGS,
    WEEK_START_DAYS,
    TimeSeriesResult,
    calculate_time_series,
)
from app.analytics.anomaly_context import add_category_context
from app.analytics.cash_flow import calculate_cash_flow
from app.ml.anomaly_detection import (
    AnomalyDetectionResult,
    FinancialAnomaly,
    detect_financial_anomalies,
)
from app.ml.forecasting import ForecastResult, forecast_time_series
from app.reports.builder import ReportRequest, build_report
from app.reports.chart_image import (
    CHART_SERIES_LABELS,
    draw_anomaly_markers,
    draw_forecast,
    draw_time_series_chart as _draw_time_series_chart,
    format_chart_axis_value as _format_chart_axis_value,
)
from app.reports.writers import WRITERS, ReportExportError, write_report
from app.ui.export_dialog import ExportDialog, ExportOptions
from app.ui.analysis_options import AnalysisOptionsWidget
from app.ui.table_browser import TableBrowserDialog
from app.ui.strings import normalize_language, tr
from app.ui.shell import Sidebar, PAGES, stylesheet, style_chart
from app.services.analysis_loader import AnalysisCancelled, load_selected_columns
from app.services.mapping_profiles import MappingProfiles, MissingProfileColumns
from app.reports.strings import label as report_label, series_label
from app.services.file_loader import (
    FileLoadError,
    LoadedFile,
    format_file_size,
    load_file_preview,
)


# Analysis keeps a wider category breakdown than the panel shows, because a
# detailed exported report wants the full list.
ANALYSIS_CATEGORY_LIMIT = None
UI_CATEGORY_LIMIT = 5
UI_CATEGORY_TABLE_LIMIT = 100
SELECTION_ROLES = (*COLUMN_ROLES, 'description')
SELECTION_LABELS = {**ROLE_LABELS, 'description': 'Description (categorisation)'}


def _set_ui_text(widget: QWidget, template: str, language: str, **values: object) -> None:
    """Remember a translated label's template for a later language change."""
    widget.setProperty("translation_template", template)
    widget.setProperty("translation_values", values)
    widget.setText(tr(template, language, **values))


def _ui_widget(widget: QWidget, template: str, language: str) -> QWidget:
    """Label an existing Qt control without changing its identity or state."""
    _set_ui_text(widget, template, language)
    return widget


def _localize_chart(axes: object, series: TimeSeriesResult, language: str) -> None:
    """Translate the UI chart artists without affecting exported report charts."""
    if language == "en":
        return
    for line in axes.lines:
        label = line.get_label()
        if label in (*CHART_SERIES_LABELS.values(), "Anomaly", "Forecast"):
            line.set_label(tr(label, language))
    labels = [tr(CHART_SERIES_LABELS[key], language) for key in series.visible_series]
    title = tr("{series} by {group}", language, series=", ".join(labels), group=tr(TIME_GROUPINGS[series.grouping], language).lower())
    axes.set_title(title)
    axes.legend(loc="best")


def _translate_candidate_reason(reason: str, language: str) -> str:
    """Translate detector-owned reason tokens while preserving keyword values."""
    parts = []
    for part in reason.split(", "):
        for prefix in ("exact keyword", "partial keyword", "generic amount keyword"):
            if part.startswith(prefix + ": "):
                part = tr(prefix + ": {keyword}", language, keyword=part[len(prefix) + 2:])
                break
        else:
            part = tr(part, language)
        parts.append(part)
    return ", ".join(parts)


@dataclass(frozen=True)
class AnalysisResult:
    """Metrics and chart data calculated for a file."""

    metrics: BasicMetrics
    time_series: TimeSeriesResult
    anomalies: AnomalyDetectionResult
    forecast: ForecastResult | None = None
    cash_balance: float | None = None


@dataclass
class ChartHoverState:
    """Interactive hover state for a rendered chart."""

    canvas: QWidget
    axes: object
    chart_lines: list[tuple[object, str]]
    grouping: str
    vertical_line: object
    markers: list[object]
    labels: list[object]
    date_label: object
    language: str = "en"
    is_visible: bool = False


class FilePreviewWorker(QObject):
    """Load a file preview outside the UI thread."""

    loaded = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)
    finished = Signal()

    def __init__(self, file_path: str, language: str = "en") -> None:
        super().__init__()
        self.file_path = file_path
        self.language = language

    @Slot()
    def run(self) -> None:
        """Load the selected file preview and report the result."""
        try:
            path = Path(self.file_path)
            self.status_changed.emit(tr("Loading preview for {name}...", self.language, name=path.name))
            loaded_file = load_file_preview(path)
        except FileLoadError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(tr("Unexpected error while loading file: {error}", self.language, error=error))
        else:
            self.loaded.emit(loaded_file)
        finally:
            self.finished.emit()


class AnalysisWorker(QObject):
    """Calculate metrics outside the UI thread."""

    completed = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)
    finished = Signal()
    cancelled = Signal()
    progress_changed = Signal(object, object, str)

    def __init__(
        self,
        file_path: str,
        selected_columns: SelectedColumns,
        grouping: str,
        week_start: str,
        language: str = "en",
        cash_balance: float | None = None,
        anomaly_method: str = 'rules',
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.selected_columns = selected_columns
        self.grouping = grouping
        self.week_start = week_start
        self.language = language
        self.cash_balance = cash_balance
        self.anomaly_method = anomaly_method
        self._cancel_event = Event()

    def cancel(self) -> None:
        """Safe to call directly from the UI thread while run() is busy."""
        self._cancel_event.set()

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise AnalysisCancelled()

    @Slot()
    def run(self) -> None:
        """Load selected columns and calculate metrics."""
        try:
            path = Path(self.file_path)
            self.status_changed.emit(tr("Analyzing {name}...", self.language, name=path.name))
            data = load_selected_columns(path, self.selected_columns, progress=self.progress_changed.emit, cancelled=self._cancel_event.is_set)
            self._check_cancelled()
            self.status_changed.emit(tr('Calculating metrics...', self.language))
            prepared = prepare_financial_data(data, self.selected_columns)
            self._check_cancelled()
            metrics = calculate_basic_metrics_from_prepared(
                prepared,
                category_limit=ANALYSIS_CATEGORY_LIMIT,
            )
            time_series = calculate_time_series(prepared, self.grouping, self.week_start)
            self._check_cancelled()
            anomalies = detect_financial_anomalies(time_series, max_items=1000000, method=self.anomaly_method)
            anomalies = add_category_context(anomalies, prepared, self.grouping, self.week_start, cancelled=self._cancel_event.is_set)
            self._check_cancelled()
            forecast = forecast_time_series(time_series)
            calculate_cash_flow(metrics, self.cash_balance)
            self._check_cancelled()
        except AnalysisCancelled:
            self.cancelled.emit()
            return
        except FileLoadError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(tr("Unexpected error while analyzing file: {error}", self.language, error=error))
        else:
            self.completed.emit(
                AnalysisResult(
                    metrics=metrics,
                    time_series=time_series,
                    anomalies=anomalies,
                    forecast=forecast,
                    cash_balance=self.cash_balance,
                )
            )
        finally:
            self.finished.emit()


class ExportWorker(QObject):
    """Build and write a report outside the UI thread.

    A detailed workbook over a long period takes long enough to freeze the
    window, so this follows the same pattern as preview and analysis loading.
    """

    completed = Signal(str)
    failed = Signal(str)
    status_changed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        target_path: Path,
        options: ExportOptions,
        result: AnalysisResult,
        file_name: str,
        language: str = "en",
    ) -> None:
        super().__init__()
        self.target_path = target_path
        self.options = options
        self.result = result
        self.file_name = file_name
        self.language = language

    @Slot()
    def run(self) -> None:
        """Assemble the report model and hand it to the chosen writer."""
        try:
            self.status_changed.emit(tr("Exporting {name}...", self.language, name=self.target_path.name))
            request = ReportRequest(
                file_name=self.file_name,
                depth=self.options.depth,
                language=self.options.language,
                grouping=self.result.time_series.grouping,
            )
            model = build_report(
                self.result.metrics,
                self.result.time_series,
                self.result.anomalies,
                request,
                self.result.forecast,
                cash_balance=self.result.cash_balance,
            )
            write_report(model, self.target_path, self.options.format_key)
        except ReportExportError as error:
            self.failed.emit(str(error))
        except OSError as error:
            self.failed.emit(
                tr("Could not write {name}. Close it in other applications and try again. ({error})", self.language, name=self.target_path.name, error=error)
            )
        except Exception as error:
            self.failed.emit(tr("Unexpected error while exporting the report: {error}", self.language, error=error))
        else:
            self.completed.emit(str(self.target_path))
        finally:
            self.finished.emit()


def _detection_warning_text(result: ColumnDetectionResult, language: str = "en") -> str:
    """Return a short warning for uncertain automatic detection."""
    if result.weak_headers:
        return tr("Column names look generic. Please confirm the selected columns.", language)
    return tr("Please confirm detected columns before analysis.", language)


def _format_detection_summary(result: ColumnDetectionResult, language: str = "en") -> str:
    """Format automatic detection results."""
    lines = []
    for role in COLUMN_ROLES:
        match = result.get(role)
        label = tr(ROLE_LABELS[role], language)
        if match.column_name is None:
            lines.append(f"{label}: {tr('not found', language)}")
        else:
            confidence = int(match.confidence * 100)
            lines.append(f"{label}: {match.column_name} ({confidence}%)")
    return "\n".join(lines)


def _format_detection_candidates(result: ColumnDetectionResult, language: str = "en") -> str:
    """Format useful alternative candidates."""
    lines = []

    if result.money_candidates:
        lines.append(tr("Money candidates: {candidates}", language, candidates=_format_candidates(result.money_candidates, language)))

    if result.direction_candidates:
        lines.append(tr("Direction candidates: {candidates}", language, candidates=_format_candidates(result.direction_candidates, language)))

    for role in COLUMN_ROLES:
        if result.get(role).column_name is not None:
            continue
        candidates = result.candidates.get(role, [])
        if candidates:
            lines.append(tr("{role} candidates: {candidates}", language, role=tr(ROLE_LABELS[role], language), candidates=_format_candidates(candidates, language)))

    return "\n".join(lines)


def _format_candidates(candidates: list[ColumnCandidate], language: str = "en") -> str:
    """Format column candidates with compact confidence labels."""
    formatted = []
    for candidate in candidates[:5]:
        confidence = int(candidate.confidence * 100)
        reason = f", {_translate_candidate_reason(candidate.reason, language)}" if candidate.reason else ""
        formatted.append(f"{candidate.column_name} ({confidence}%{reason})")
    return ", ".join(formatted)


def _format_chart_hover_value(value: float) -> str:
    """Format exact values for chart hover labels."""
    if float(value).is_integer():
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ")


def _format_chart_period(value: object, grouping: str) -> str:
    """Format one chart period for tooltips."""
    if hasattr(value, "strftime"):
        if grouping == "hour":
            return value.strftime("%Y-%m-%d %H:%M")
        if grouping == "month":
            return value.strftime("%Y-%m")
        if grouping == "year":
            return value.strftime("%Y")
        return value.strftime("%Y-%m-%d")
    return str(value)


def _chart_x_number(value: object) -> float:
    """Return a numeric x-coordinate for datetime or numeric chart values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        if date2num is None:
            raise
        return float(date2num(value))


def _format_chart_tooltip(series_key: str, period: object, value: float, grouping: str, language: str = "en") -> str:
    """Format hover tooltip text for a chart point."""
    return (
        tr("Date: {period}\n{series}: {value}", language, period=_format_chart_period(period, grouping), series=tr(CHART_SERIES_LABELS[series_key], language), value=_format_chart_hover_value(value))
    )


def _create_chart_hover_state(
    canvas: QWidget,
    axes: object,
    chart_lines: list[tuple[object, str]],
    grouping: str,
    language: str = "en",
) -> ChartHoverState:
    """Create hidden hover artists for a rendered chart."""
    x_limits = axes.get_xlim()
    y_limits = axes.get_ylim()
    first_x = _first_chart_x_value(chart_lines)
    vertical_line = axes.axvline(
        first_x,
        color="#444444",
        linewidth=1.0,
        alpha=0.35,
        visible=False,
        zorder=3,
    )
    markers = []
    labels = []

    for line, series_key in chart_lines:
        color = line.get_color()
        (marker,) = axes.plot(
            [],
            [],
            linestyle="None",
            marker="D",
            markersize=7,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=1.0,
            visible=False,
            zorder=6,
        )
        label = axes.annotate(
            "",
            xy=(0, 0),
            xytext=(8, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=9,
            color="white",
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": color,
                "edgecolor": color,
                "alpha": 0.95,
            },
            visible=False,
            zorder=7,
        )
        markers.append(marker)
        labels.append(label)

    date_label = axes.annotate(
        "",
        xy=(0, 0),
        xytext=(0, -26),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=9,
        color="white",
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": "#333333",
            "edgecolor": "#333333",
            "alpha": 0.95,
        },
        visible=False,
        zorder=7,
        annotation_clip=False,
    )
    axes.set_xlim(x_limits)
    axes.set_ylim(y_limits)

    return ChartHoverState(
        canvas=canvas,
        axes=axes,
        chart_lines=chart_lines,
        grouping=grouping,
        vertical_line=vertical_line,
        markers=markers,
        labels=labels,
        date_label=date_label,
        language=language,
    )


def _first_chart_x_value(chart_lines: list[tuple[object, str]]) -> object:
    """Return the first real x value from rendered chart lines."""
    if not chart_lines:
        return 0

    first_line = chart_lines[0][0]
    x_values = list(first_line.get_xdata(orig=True))
    return x_values[0] if x_values else 0


def _update_chart_hover(event: object, state: ChartHoverState) -> None:
    """Snap hover visuals to the nearest chart period."""
    if getattr(event, "inaxes", None) is not state.axes or getattr(event, "xdata", None) is None:
        _hide_chart_hover(state)
        return

    if not state.chart_lines:
        _hide_chart_hover(state)
        return

    first_line = state.chart_lines[0][0]
    x_values = list(first_line.get_xdata(orig=True))
    if not x_values:
        _hide_chart_hover(state)
        return

    hover_x = float(event.xdata)
    x_values_numeric = [_chart_x_number(value) for value in x_values]
    index = min(
        range(len(x_values_numeric)),
        key=lambda item_index: abs(float(x_values_numeric[item_index]) - hover_x),
    )
    x_value = x_values[index]
    y_min, _y_max = state.axes.get_ylim()

    state.vertical_line.set_xdata([x_value, x_value])
    state.vertical_line.set_visible(True)

    for item_index, (line, series_key) in enumerate(state.chart_lines):
        x_data = line.get_xdata(orig=True)
        y_data = line.get_ydata(orig=True)
        if index >= len(x_data) or index >= len(y_data):
            continue

        y_value = float(y_data[index])
        state.markers[item_index].set_data([x_data[index]], [y_value])
        state.markers[item_index].set_visible(True)

        state.labels[item_index].xy = (x_data[index], y_value)
        state.labels[item_index].set_text(
            f"{_format_chart_hover_value(y_value)} {tr(CHART_SERIES_LABELS[series_key], state.language)}"
        )
        state.labels[item_index].set_visible(True)

    state.date_label.xy = (x_value, y_min)
    state.date_label.set_text(_format_chart_period(x_value, state.grouping))
    state.date_label.set_visible(True)
    state.is_visible = True
    state.canvas.draw_idle()


def _hide_chart_hover(state: ChartHoverState) -> None:
    """Hide chart hover visuals."""
    if not state.is_visible:
        return

    state.vertical_line.set_visible(False)
    for marker in state.markers:
        marker.set_visible(False)
    for label in state.labels:
        label.set_visible(False)
    state.date_label.set_visible(False)
    state.is_visible = False
    state.canvas.draw_idle()


class ChartDialog(QDialog):
    """Fullscreen chart viewer."""

    def __init__(
        self,
        time_series: TimeSeriesResult,
        anomalies: AnomalyDetectionResult | None = None,
        forecast: ForecastResult | None = None,
        parent: QWidget | None = None,
        language: str = "en",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.time_series = time_series
        self.anomalies = anomalies
        self.forecast = forecast
        self.motion_connection: int | None = None
        self.hover_state: ChartHoverState | None = None
        self.setWindowTitle(tr("Charts", self.language))
        self.resize(1280, 800)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build and render the fullscreen chart."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        if Figure is None or FigureCanvas is None:
            label = _ui_widget(QLabel(), "Install matplotlib to show charts.", self.language)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label, stretch=1)
            return

        self.figure = Figure(figsize=(12, 7), tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.axes.clear()
        chart_lines = _draw_time_series_chart(self.axes, self.figure, self.time_series)
        draw_forecast(self.axes, self.time_series, self.forecast, chart_lines)
        draw_anomaly_markers(self.axes, self.time_series, self.anomalies)
        _localize_chart(self.axes, self.time_series, self.language)
        self.hover_state = _create_chart_hover_state(
            self.canvas,
            self.axes,
            chart_lines,
            self.time_series.grouping,
            self.language,
        )
        self.motion_connection = self.canvas.mpl_connect(
            "motion_notify_event",
            lambda event: _update_chart_hover(event, self.hover_state),
        )
        layout.addWidget(self.canvas, stretch=1)
        theme = getattr(self.parentWidget(), 'theme', 'light')
        self.setStyleSheet(stylesheet(theme))
        style_chart(self.figure, self.axes, theme)


class ColumnSelectionDialog(QDialog):
    """Dialog for reviewing and manually selecting analysis columns."""

    def __init__(
        self,
        column_names: list[str],
        detection_result: ColumnDetectionResult,
        selected_columns: SelectedColumns,
        parent: QWidget | None = None,
        language: str = "en",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.column_names = column_names
        self.detection_result = detection_result
        self.role_layouts: dict[str, QVBoxLayout] = {}
        self.role_rows: dict[str, list[tuple[QWidget, QComboBox, QPushButton]]] = {
            role: [] for role in SELECTION_ROLES
        }
        self.setWindowTitle(tr("Configure Columns", self.language))
        self.resize(720, 520)
        self._setup_ui(selected_columns)

    def _setup_ui(self, selected_columns: SelectedColumns) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = _ui_widget(QLabel(), "Configure Columns", self.language)
        title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        warning_label = QLabel("")
        warning_label.setWordWrap(True)
        warning_label.setProperty('tone', 'warning')
        if self.detection_result.needs_user_confirmation:
            warning_label.setText(_detection_warning_text(self.detection_result, self.language))
        else:
            warning_label.hide()

        detected_label = QLabel(_format_detection_summary(self.detection_result, self.language))
        detected_label.setWordWrap(True)
        detected_label.setProperty('tone', 'muted')

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        selector_widget = QWidget()
        selector_layout = QGridLayout(selector_widget)
        selector_layout.setHorizontalSpacing(12)
        selector_layout.setVerticalSpacing(10)

        for row_index, role in enumerate(SELECTION_ROLES):
            label = QLabel(f"{tr(SELECTION_LABELS[role], self.language)}:")
            label.setMinimumWidth(80)

            add_button = QPushButton("+")
            add_button.setFixedWidth(30)
            add_button.setEnabled(bool(self.column_names))
            add_button.clicked.connect(
                lambda checked=False, role=role: self._add_selector_row(role)
            )

            label_layout = QHBoxLayout()
            label_layout.setContentsMargins(0, 0, 0, 0)
            label_layout.addWidget(label)
            label_layout.addStretch()
            label_layout.addWidget(add_button)

            role_container = QWidget()
            role_layout = QVBoxLayout(role_container)
            role_layout.setContentsMargins(0, 0, 0, 0)
            role_layout.setSpacing(5)
            self.role_layouts[role] = role_layout

            selected_for_role = getattr(selected_columns, role)
            if selected_for_role:
                for column_name in selected_for_role:
                    self._add_selector_row(role, column_name)
            else:
                self._add_selector_row(role)

            selector_layout.addLayout(label_layout, row_index, 0)
            selector_layout.addWidget(role_container, row_index, 1)

        scroll_area.setWidget(selector_widget)

        candidates_text = _format_detection_candidates(self.detection_result, self.language)
        candidates_label = QLabel(candidates_text)
        candidates_label.setWordWrap(True)
        candidates_label.setProperty('tone', 'muted')
        if not candidates_text:
            candidates_label.hide()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK", self.language))
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel", self.language))
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(title_label)
        layout.addWidget(warning_label)
        layout.addWidget(detected_label)
        layout.addWidget(scroll_area, stretch=1)
        layout.addWidget(candidates_label)
        layout.addWidget(button_box)

    def _add_selector_row(self, role: str, selected_column: str | None = None) -> None:
        """Add one selectable column row for a role."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        combo = QComboBox()
        combo.addItem(tr("Not selected", self.language), None)
        for column_name in self.column_names:
            combo.addItem(column_name, column_name)

        if selected_column is not None:
            index = combo.findData(selected_column)
            if index >= 0:
                combo.setCurrentIndex(index)

        combo.setEnabled(bool(self.column_names))

        remove_button = QPushButton("-")
        remove_button.setFixedWidth(30)
        remove_button.clicked.connect(
            lambda checked=False, role=role, row_widget=row_widget: (
                self._remove_selector_row(role, row_widget)
            )
        )

        row_layout.addWidget(combo, stretch=1)
        row_layout.addWidget(remove_button)

        self.role_rows[role].append((row_widget, combo, remove_button))
        self.role_layouts[role].addWidget(row_widget)
        self._update_remove_buttons(role)

    def _remove_selector_row(self, role: str, row_widget: QWidget) -> None:
        """Remove one selector row while keeping one row per role."""
        if len(self.role_rows[role]) <= 1:
            return

        for index, (candidate_widget, _combo, _remove_button) in enumerate(
            self.role_rows[role]
        ):
            if candidate_widget is not row_widget:
                continue
            self.role_rows[role].pop(index)
            self.role_layouts[role].removeWidget(candidate_widget)
            candidate_widget.deleteLater()
            break

        self._update_remove_buttons(role)

    def _update_remove_buttons(self, role: str) -> None:
        """Enable remove buttons only when a role has multiple rows."""
        can_remove = len(self.role_rows[role]) > 1
        for _row_widget, _combo, remove_button in self.role_rows[role]:
            remove_button.setEnabled(can_remove)

    def selected_columns(self) -> SelectedColumns:
        """Return selected columns from the dialog."""
        return SelectedColumns(
            date=self._selected_role_columns("date"),
            revenue=self._selected_role_columns("revenue"),
            expense=self._selected_role_columns("expense"),
            amount=self._selected_role_columns("amount"),
            category=self._selected_role_columns("category"),
            description=self._selected_role_columns('description'),
        )

    def _selected_role_columns(self, role: str) -> tuple[str, ...]:
        """Return deduplicated selected columns for one role."""
        selected: list[str] = []
        seen: set[str] = set()
        for _row_widget, combo, _remove_button in self.role_rows[role]:
            column_name = combo.currentData()
            if not column_name or column_name in seen:
                continue
            selected.append(column_name)
            seen.add(column_name)
        return tuple(selected)


class MainWindow(QMainWindow):
    """Main Profilytix window with placeholder areas for future features."""

    def __init__(self, language: str | None = None) -> None:
        super().__init__()
        self.settings = QSettings("Profilytix", "Profilytix")
        self.theme = 'dark' if self.settings.value('ui_theme', 'light', str) == 'dark' else 'light'
        self.mapping_profiles = MappingProfiles(self.settings)
        self._close_pending = False
        self.language = normalize_language(language or self.settings.value("ui_language", "ru", str))
        self.preview_thread: QThread | None = None
        self.preview_worker: FilePreviewWorker | None = None
        self.analysis_thread: QThread | None = None
        self.analysis_worker: AnalysisWorker | None = None
        self.export_thread: QThread | None = None
        self.export_worker: ExportWorker | None = None
        self.current_analysis_result: AnalysisResult | None = None
        self.last_export_path: Path | None = None
        self.last_export_options: ExportOptions | None = None
        self.current_loaded_file: LoadedFile | None = None
        self.available_column_names: list[str] = []
        self.selected_columns = SelectedColumns()
        self.chart_canvas = None
        self.chart_axes = None
        self.chart_motion_connection: int | None = None
        self.chart_hover_state: ChartHoverState | None = None
        self.current_detection_result: ColumnDetectionResult | None = None
        self.current_metrics: BasicMetrics | None = None
        self.current_metrics_text = ""
        self.current_time_series: TimeSeriesResult | None = None
        self.current_anomalies: AnomalyDetectionResult | None = None
        self.current_forecast: ForecastResult | None = None
        self.setWindowTitle("Profilytix")
        self.resize(1280, 850)
        self.setMinimumSize(960, 640)

        self._setup_ui()

    def tr(self, template: str, **values: object) -> str:
        """Translate application-owned UI text in the selected desktop language."""
        return tr(template, self.language, **values)

    def set_language(self, language: str) -> None:
        """Persist the UI choice and update existing widgets and analysis in place."""
        self.language = normalize_language(language)
        self.settings.setValue("ui_language", self.language)
        for widget in self.findChildren(QWidget):
            template = widget.property("translation_template")
            if template:
                widget.setText(self.tr(template, **(widget.property("translation_values") or {})))
        for combo, labels in ((self.grouping_combo, TIME_GROUPINGS), (self.week_start_combo, {key: value[0] for key, value in WEEK_START_DAYS.items()})):
            for index in range(combo.count()):
                combo.setItemText(index, self.tr(labels[combo.itemData(index)]))
        index = self.language_combo.findData(self.language)
        if self.language_combo.currentIndex() != index:
            self.language_combo.setCurrentIndex(index)
        if self.current_loaded_file is not None:
            self._update_file_info(self.current_loaded_file)
            self.detected_columns_label.setText(self._format_selected_columns_summary())
        if self.current_detection_result is not None:
            self.detection_warning_label.setText(_detection_warning_text(self.current_detection_result, self.language))
        result = self.current_analysis_result
        if result is not None and self.analysis_thread is None:
            self.current_metrics_text = self._format_analysis_details(result.metrics, result.anomalies, result.time_series.grouping)
            self.metrics_label.setText(self._format_metrics_compact(result.metrics))
            self.anomalies_label.setText(self._format_anomalies_compact(result.anomalies, result.time_series.grouping))
            self._update_chart(result.time_series)
            self._update_forecast_summary(result)
        self.analysis_options.set_language(self.language)
        self.sidebar.set_language(self.language)
        self._update_dashboard(self.current_metrics)
        for worker in (self.preview_worker, self.analysis_worker, self.export_worker):
            if worker is not None:
                worker.language = self.language
        if self.export_worker is not None:
            _set_ui_text(self.status_label, "Exporting {name}...", self.language, name=self.export_worker.target_path.name)
        elif self.analysis_worker is not None:
            _set_ui_text(self.status_label, "Analyzing {name}...", self.language, name=Path(self.analysis_worker.file_path).name)
        elif self.preview_worker is not None:
            _set_ui_text(self.status_label, "Loading preview for {name}...", self.language, name=Path(self.preview_worker.file_path).name)

    def _setup_ui(self) -> None:
        """Build five persistent pages around the existing analysis controls."""
        central_widget = QWidget(self)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.sidebar = Sidebar(self.language, self.settings.value('sidebar_collapsed', False, bool), self.theme)
        self.sidebar.collapsed_changed.connect(lambda value: self.settings.setValue('sidebar_collapsed', value))
        self.sidebar.theme_requested.connect(self._toggle_theme)
        root_layout.addWidget(self.sidebar)
        workspace = QWidget()
        workspace.setObjectName('workspace')
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(24, 20, 24, 12)
        workspace_layout.setSpacing(14)
        header_layout = QHBoxLayout()
        self.workspace_label = _ui_widget(QLabel(), 'Financial workspace', self.language)
        self.workspace_label.setProperty('tone', 'muted')
        self.load_button = _ui_widget(QPushButton(), "Load Excel/CSV", self.language)
        self.load_button.setMinimumHeight(36)
        self.load_button.clicked.connect(self._choose_file)
        header_layout.addWidget(self.workspace_label)
        header_layout.addStretch()
        self.language_combo = QComboBox()
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        self.language_combo.currentIndexChanged.connect(lambda: self.set_language(self.language_combo.currentData()))
        header_layout.addWidget(self.language_combo)
        header_layout.addWidget(self.load_button)
        table_preview_area = self._create_table_preview_area()
        metrics_area = self._create_analysis_area()
        header_layout.addWidget(self.analyze_button)
        chart_area = self._create_chart_area()
        self.page_stack = QStackedWidget()
        self.sidebar.page_requested.connect(self.page_stack.setCurrentIndex)
        self.page_layouts = []
        for title in PAGES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            page = QWidget()
            page.setObjectName('page')
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 6, 0, 6)
            layout.setSpacing(16)
            heading = _ui_widget(QLabel(), title, self.language)
            heading.setProperty('role', 'heading')
            layout.addWidget(heading)
            scroll.setWidget(page)
            self.page_stack.addWidget(scroll)
            self.page_layouts.append(layout)
        overview, data, categories, analysis, reports = self.page_layouts
        overview.addWidget(metrics_area)
        chart_area.setMinimumHeight(350)
        overview.addWidget(chart_area, 1)
        data.addWidget(self.mapping_area)
        profile_card, profile_layout = self._card('Saved column mappings')
        profile_layout.addWidget(self.analysis_options.profile_widget)
        data.addWidget(profile_card)
        data.addWidget(table_preview_area, 1)
        self.category_table, self.category_summary = self._category_view(categories, 'Source categories')
        self.derived_category_table, self.derived_category_summary = self._category_view(categories, 'Categories from descriptions')
        analysis.addWidget(self.anomalies_area)
        analysis.addStretch()
        reports.addWidget(self.reports_area)
        help_card, help_layout = self._card('Mode help')
        for title, text in self._help_sections():
            label = _ui_widget(QLabel(), title, self.language)
            label.setProperty('role', 'card_title')
            help_layout.addWidget(label)
            label = _ui_widget(QLabel(), text, self.language)
            label.setWordWrap(True)
            label.setProperty('tone', 'muted')
            help_layout.addWidget(label)
        reports.addWidget(help_card)
        reports.addStretch()
        workspace_layout.addLayout(header_layout)
        workspace_layout.addWidget(self.page_stack, 1)
        # Global job status/cancellation must stay visible while browsing any page.
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        footer = QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.cancel_button)
        workspace_layout.addLayout(footer)
        workspace_layout.addWidget(self.progress_bar)
        root_layout.addWidget(workspace, 1)
        self.setCentralWidget(central_widget)
        self._update_dashboard(None)
        self._apply_theme()

    def _toggle_theme(self) -> None:
        self.theme = 'light' if self.theme == 'dark' else 'dark'
        self.settings.setValue('ui_theme', self.theme)
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet(self.theme))
        self.sidebar.set_theme(self.theme)
        if self.chart_axes is not None:
            style_chart(self.chart_figure, self.chart_axes, self.theme)
            self.chart_canvas.draw_idle()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setProperty('role', 'card')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        label = _ui_widget(QLabel(), title, self.language)
        label.setProperty('role', 'card_title')
        layout.addWidget(label)
        return frame, layout

    def _category_view(self, page_layout, title):
        frame, layout = self._card(title)
        table = QTableWidget(0, 5)
        table.setMinimumHeight(180)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        summary = QLabel()
        summary.setWordWrap(True)
        summary.setProperty('tone', 'muted')
        layout.addWidget(summary)
        page_layout.addWidget(frame)
        return table, summary

    def _update_dashboard(self, metrics: BasicMetrics | None) -> None:
        _set_ui_text(self.report_hint, 'Report export is ready.' if metrics else 'Analyze a file to enable report export.', self.language)
        for key, field in [('revenue', 'total_revenue'), ('expenses', 'total_expenses'), ('profit', 'total_profit')]:
            value = getattr(metrics, field, None)
            self.metric_values[key].setText('—' if value is None else format_money(value))
        for table, summary, rows, derived in [
            (self.category_table, self.category_summary, metrics.top_categories if metrics else (), False),
            (self.derived_category_table, self.derived_category_summary, metrics.derived_categories if metrics else (), True),
        ]:
            table.setHorizontalHeaderLabels([self.tr(title) for title in ('Category', 'Transactions', 'Revenue', 'Expenses', 'Profit')])
            _set_ui_text(summary, 'Showing {shown} of {total} categories. Full results are available in a detailed report.', self.language,
                         shown=min(UI_CATEGORY_TABLE_LIMIT, len(rows)), total=len(rows))
            rows = rows[:UI_CATEGORY_TABLE_LIMIT]
            table.setRowCount(len(rows))
            for i, item in enumerate(rows):
                name = report_label(self.language, 'category_' + item.name) if derived else item.name
                values = (name, format_number(item.transaction_count), format_money(item.revenue),
                          format_money(item.expenses), format_money(item.profit))
                for j, text in enumerate(values):
                    cell = QTableWidgetItem(text)
                    if j:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(i, j, cell)

    @staticmethod
    def _help_sections():
        return (
            ('Getting started', 'Load a CSV or Excel file, review columns on Data, then click Analyze File. Navigation keeps your file and results.'),
            ('Anomaly methods', 'IQR / Z-score rules need at least 4 periods; Isolation Forest needs 8. Each financial series is checked separately. Revenue/expense spikes and profit drops are flagged; signed amounts are checked in both directions. A signal is a reason to inspect the data, not proof of an error.'),
            ('Grouping and forecast', 'Grouping changes the periods used by charts and anomaly detection. Week starts applies to weekly grouping. Forecasts use a moving average or linear trend from past values and cannot account for future one-off payments.'),
            ('Cash balance', 'Current cash is optional and separate from profit. Cash runway and 30-day estimates use historical daily profit. Missing dates on money rows prevent a cash estimate.'),
            ('Columns and categories', 'Review automatic column choices on Data. Saved mappings reuse column names. Description-based categories use local RU/EN rules and are separate from source categories; they are not a trained classifier.'),
            ('Reports', 'Export PDF, XLSX, HTML, PNG or CSV after analysis. PNG requires a date-based chart. Choose report language and detail level in the export dialog; these are independent of the interface language.'),
        )

    def _choose_file(self) -> None:
        """Open a file picker and load the selected spreadsheet."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Load Excel/CSV", self.language),
            str(self._get_initial_file_directory()),
            tr("Data files (*.csv *.xlsx *.xls);;CSV files (*.csv);;Excel files (*.xlsx *.xls)", self.language),
        )

        if not file_path:
            return

        self._start_preview_loading(file_path)

    def _start_preview_loading(self, file_path: str) -> None:
        """Start loading a file preview in a background thread."""
        if any(thread is not None for thread in (self.preview_thread, self.analysis_thread, self.export_thread)):
            return

        self._set_loading_state(file_path)

        self.preview_thread = QThread(self)
        self.preview_worker = FilePreviewWorker(file_path, language=self.language)
        self.preview_worker.moveToThread(self.preview_thread)

        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.status_changed.connect(self.status_label.setText)
        self.preview_worker.loaded.connect(self._handle_preview_loaded)
        self.preview_worker.failed.connect(self._handle_preview_failed)
        self.preview_worker.finished.connect(self.preview_thread.quit, Qt.ConnectionType.DirectConnection)
        self.preview_thread.finished.connect(self.preview_worker.deleteLater)
        self.preview_thread.finished.connect(self._finish_preview_loading)

        self.preview_thread.start()

    def _set_loading_state(self, file_path: str) -> None:
        """Update controls while a preview is loading."""
        path = Path(file_path)
        size_text = ""
        if path.is_file():
            size_text = f" ({format_file_size(path.stat().st_size)})"

        self.load_button.setEnabled(False)
        _set_ui_text(self.load_button, "Loading...", self.language)
        self.configure_columns_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.analysis_options.setEnabled(False)
        self.analysis_options.profile_widget.setEnabled(False)
        self.export_button.setEnabled(False)
        _set_ui_text(self.status_label, "Loading preview for {name}{size}...", self.language, name=path.name, size=size_text)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()

    @Slot()
    def _finish_preview_loading(self) -> None:
        """Restore controls after the preview worker finishes."""
        if self.preview_thread is not None:
            self.preview_thread.wait()
            self.preview_thread.deleteLater()
        self.load_button.setEnabled(True)
        _set_ui_text(self.load_button, "Load Excel/CSV", self.language)
        has_loaded_file = self.current_loaded_file is not None
        self.configure_columns_button.setEnabled(has_loaded_file)
        self.analyze_button.setEnabled(has_loaded_file)
        self.analysis_options.setEnabled(True)
        self.analysis_options.profile_widget.setEnabled(True)
        self.export_button.setEnabled(True)
        self.progress_bar.hide()
        self.preview_thread = None
        self.preview_worker = None
        self._maybe_close()

    def _handle_preview_loaded(self, loaded_file: LoadedFile) -> None:
        """Display the loaded preview returned by the worker."""
        self._remember_file_directory(loaded_file.path)
        self._show_loaded_file(loaded_file)
        self.sidebar.nav_buttons[1].click()
        _set_ui_text(self.status_label, "Preview loaded: {name}", self.language, name=loaded_file.file_name)

    def _handle_preview_failed(self, message: str) -> None:
        """Display a preview loading error returned by the worker."""
        _set_ui_text(self.status_label, "Could not load preview.", self.language)
        self._show_load_error(message)

    def _get_initial_file_directory(self) -> Path:
        """Return the directory that should be opened in the file picker."""
        saved_directory = self.settings.value("last_file_directory", "", str)
        if saved_directory:
            path = Path(saved_directory)
            if path.is_dir():
                return path

        return Path.home()

    def _remember_file_directory(self, file_path: Path) -> None:
        """Save the directory of the last successfully loaded file."""
        self.settings.setValue("last_file_directory", str(file_path.parent))

    def _create_table_preview_area(self) -> QFrame:
        """Create the file information and table preview area."""
        frame = QFrame(self)
        frame.setProperty('role', 'card')
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumWidth(360)
        frame.setMinimumHeight(330)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = _ui_widget(QLabel(), "Table preview", self.language)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.file_info_label = _ui_widget(QLabel(), "No file loaded.", self.language)
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setTextFormat(Qt.TextFormat.PlainText)
        self.file_info_label.setProperty('tone', 'muted')
        self.file_info_label.hide()
        self.file_summary_label = _ui_widget(QLabel(), 'No file loaded.', self.language)
        self.file_summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.file_summary_label.setWordWrap(True)
        self.file_summary_label.setProperty('tone', 'muted')
        self.file_details_button = _ui_widget(QPushButton(), 'File details', self.language)
        self.file_details_button.setCheckable(True)
        self.file_details_button.setEnabled(False)
        self.file_details_button.toggled.connect(self.file_info_label.setVisible)

        self.status_label = _ui_widget(QLabel(), "Ready.", self.language)
        self.status_label.setProperty('tone', 'muted')

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.cancel_button = _ui_widget(QPushButton(), 'Cancel analysis', self.language)
        self.cancel_button.clicked.connect(self._cancel_analysis)
        self.cancel_button.hide()
        self.browse_table_button = _ui_widget(QPushButton(), 'View all rows...', self.language)
        self.browse_table_button.setEnabled(False)
        self.browse_table_button.clicked.connect(self._browse_all_rows)

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.verticalHeader().setVisible(False)

        layout.addWidget(title_label)
        layout.addWidget(self.file_summary_label)
        layout.addWidget(self.file_details_button)
        layout.addWidget(self.file_info_label)
        layout.addWidget(self.browse_table_button)
        layout.addWidget(self.table_widget, stretch=1)

        return frame

    def _create_placeholder_area(self, title: str, message: str) -> QFrame:
        """Create an empty framed area reserved for a future UI section."""
        frame = QFrame(self)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumWidth(300)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setProperty('tone', 'muted')

        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(message_label)
        layout.addStretch()

        return frame

    def _show_loaded_file(self, loaded_file: LoadedFile) -> None:
        """Display loaded file metadata and the first 100 rows."""
        self.current_loaded_file = loaded_file
        self.file_details_button.setEnabled(True)
        self.browse_table_button.setEnabled(bool(loaded_file.column_names))
        self.analysis_options.save_button.setEnabled(bool(loaded_file.column_names))
        self.forecast_label.clear()
        self.current_metrics = None
        self.current_metrics_text = ""
        self.current_time_series = None
        self.current_anomalies = None
        self.current_forecast = None
        self.current_analysis_result = None
        self._update_dashboard(None)
        self.export_button.hide()
        self.open_report_folder_button.hide()
        self.current_anomalies = None
        self._update_file_info(loaded_file)
        self._update_table_preview(loaded_file.column_names, loaded_file.preview_rows)
        self._update_detected_columns(loaded_file)
        _set_ui_text(self.metrics_label, "Select one or more columns and click Analyze File.", self.language)
        self.metrics_details_button.hide()
        _set_ui_text(self.anomalies_label, "Analyze a file to see anomalies.", self.language)
        self._set_detected_columns_visible(True)
        self._clear_chart()
        self.analyze_button.setEnabled(True)

    def _update_file_info(self, loaded_file: LoadedFile) -> None:
        """Display the loaded file name, shape, columns, and encoding."""
        columns = ", ".join(loaded_file.column_names) if loaded_file.column_names else tr("No columns", self.language)
        encoding_text = self.tr("\nCSV encoding: {value}", value=loaded_file.encoding) if loaded_file.encoding else ""
        delimiter_text = self.tr("\nCSV delimiter: {value}", value=loaded_file.delimiter) if loaded_file.delimiter else ""
        reader_text = self.tr("\nReader: {value}", value=loaded_file.reader) if loaded_file.reader else ""
        rows = loaded_file.row_count_text
        if loaded_file.total_rows is None and loaded_file.preview_row_count >= 100:
            rows = self.tr("{count}+ (fast preview)", count=loaded_file.preview_row_count)
        _set_ui_text(self.file_summary_label, '{name} · {rows} rows · {count} columns', self.language,
                     name=loaded_file.file_name, rows=rows, count=loaded_file.column_count)
        self.file_info_label.setText(self.tr(
            "File: {name}\nSize: {size}\nRows: {rows}\nColumns: {count}\nPreview rows: {preview}\nColumn names: {columns}{encoding}{delimiter}{reader}",
            name=loaded_file.file_name, size=loaded_file.file_size_text,
            rows=rows, count=loaded_file.column_count, preview=loaded_file.preview_row_count,
            columns=columns, encoding=encoding_text, delimiter=delimiter_text, reader=reader_text,
        ))

    def _update_table_preview(self, column_names: list[str], rows: list[list[str]]) -> None:
        """Render preview rows in the table widget."""
        self.table_widget.clear()
        self.table_widget.setRowCount(len(rows))
        self.table_widget.setColumnCount(len(column_names))
        self.table_widget.setHorizontalHeaderLabels(column_names)

        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row[: len(column_names)]):
                self.table_widget.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

        self.table_widget.resizeColumnsToContents()

    def _show_load_error(self, message: str) -> None:
        """Show a user-friendly file loading error."""
        QMessageBox.warning(self, tr("Could not load file", self.language), message)

    def _create_analysis_area(self) -> QFrame:
        """Create working controls once, grouped for their persistent pages."""
        self.mapping_area, mapping = self._card('Column selection')
        self.detected_columns_title_label = mapping.itemAt(0).widget()

        self.detection_warning_label = QLabel("")
        self.detection_warning_label.setWordWrap(True)
        self.detection_warning_label.setProperty('tone', 'warning')
        self.detection_warning_label.hide()

        self.detected_columns_label = _ui_widget(QLabel(), "Load a file to detect columns.", self.language)
        self.detected_columns_label.setTextFormat(Qt.TextFormat.PlainText)
        self.detected_columns_label.setWordWrap(True)
        self.detected_columns_label.setProperty('tone', 'muted')

        self.configure_columns_button = _ui_widget(QPushButton(), "Configure Columns...", self.language)
        self.configure_columns_button.setEnabled(False)
        self.configure_columns_button.clicked.connect(self._open_column_selection_dialog)

        frame, layout = self._card('Financial summary')
        self.metric_values = {}
        cards = QHBoxLayout()
        for key, title in [('revenue', 'Revenue'), ('expenses', 'Expenses'), ('profit', 'Profit')]:
            card, card_layout = self._card(title)
            value = QLabel('—')
            value.setProperty('role', 'metric')
            value.setTextFormat(Qt.TextFormat.PlainText)
            card_layout.addWidget(value)
            self.metric_values[key] = value
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        self.metrics_label = _ui_widget(QLabel(), "Metrics will be calculated in the next step.", self.language)
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setProperty('tone', 'muted')

        self.metrics_details_button = _ui_widget(QPushButton(), "Show Details...", self.language)
        self.metrics_details_button.clicked.connect(self._show_metrics_details)
        self.metrics_details_button.hide()

        self.anomalies_area, anomalies = self._card('Analysis settings and results')
        self.anomalies_label = _ui_widget(QLabel(), "Analyze a file to see anomalies.", self.language)
        self.anomalies_label.setWordWrap(True)
        self.anomalies_label.setProperty('tone', 'muted')

        self.analyze_button = _ui_widget(QPushButton(), "Analyze File", self.language)
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._start_analysis)
        self.analyze_button.setProperty('primary', True)
        self.analysis_options = AnalysisOptionsWidget(self, self.language)
        self.analysis_options.set_profiles(self.mapping_profiles.names())
        self.analysis_options.save_button.setEnabled(False)
        self.analysis_options.save_requested.connect(self._save_mapping_profile)
        self.analysis_options.apply_requested.connect(self._apply_mapping_profile)
        self.analysis_options.delete_requested.connect(self._delete_mapping_profile)
        self.forecast_label = QLabel()
        self.forecast_label.setWordWrap(True)
        self.forecast_label.setTextFormat(Qt.TextFormat.PlainText)

        self.export_button = _ui_widget(QPushButton(), "Export Report...", self.language)
        self.export_button.clicked.connect(self._start_export)
        self.export_button.hide()

        self.open_report_folder_button = _ui_widget(QPushButton(), "Open Folder", self.language)
        self.open_report_folder_button.clicked.connect(self._open_report_folder)
        self.open_report_folder_button.hide()
        self.reports_area, reports = self._card('Export Report')
        self.report_hint = _ui_widget(QLabel(), 'Analyze a file to enable report export.', self.language)
        self.report_hint.setWordWrap(True)
        self.report_hint.setProperty('tone', 'muted')
        reports.addWidget(self.report_hint)
        reports.addWidget(self.export_button)
        reports.addWidget(self.open_report_folder_button)
        for widget in (self.detection_warning_label,
                       self.detected_columns_label, self.configure_columns_button):
            mapping.addWidget(widget)
        layout.addWidget(self.metrics_label)
        layout.addWidget(self.metrics_details_button)
        anomalies.addWidget(self.analysis_options)
        anomalies.addWidget(self.anomalies_label)
        anomalies.addWidget(self.forecast_label)
        mode_help = _ui_widget(QPushButton(), 'Mode help', self.language)
        mode_help.clicked.connect(lambda: self.sidebar.nav_buttons[4].click())
        anomalies.addWidget(mode_help)
        return frame

    def _create_chart_area(self) -> QFrame:
        """Create the time-series chart area."""
        frame = QFrame(self)
        frame.setProperty('role', 'card')
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumHeight(240)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        title_label = _ui_widget(QLabel(), "Charts", self.language)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        grouping_label = _ui_widget(QLabel(), "Group by:", self.language)
        self.grouping_combo = QComboBox()
        for value, label in TIME_GROUPINGS.items():
            self.grouping_combo.addItem(self.tr(label), value)
        self.grouping_combo.setCurrentIndex(self.grouping_combo.findData("day"))
        self.grouping_combo.currentIndexChanged.connect(self._update_week_start_enabled)

        self.week_start_label = _ui_widget(QLabel(), "Week starts:", self.language)
        self.week_start_combo = QComboBox()
        for value, (label, _index) in WEEK_START_DAYS.items():
            self.week_start_combo.addItem(self.tr(label), value)
        self.week_start_combo.setCurrentIndex(self.week_start_combo.findData("monday"))

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(grouping_label)
        filter_layout.addWidget(self.grouping_combo)
        filter_layout.addWidget(self.week_start_label)
        filter_layout.addWidget(self.week_start_combo)
        filter_layout.addStretch()

        self.open_chart_button = _ui_widget(QPushButton(), "Open Fullscreen", self.language)
        self.open_chart_button.setEnabled(False)
        self.open_chart_button.clicked.connect(self._open_chart_fullscreen)
        header_layout.addWidget(self.open_chart_button)

        self.chart_message_label = _ui_widget(QLabel(), "Analyze a file to see charts.", self.language)
        self.chart_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_message_label.setProperty('tone', 'muted')

        layout.addLayout(header_layout)
        layout.addLayout(filter_layout)

        if Figure is None or FigureCanvas is None:
            _set_ui_text(self.chart_message_label, "Install matplotlib to show charts.", self.language)
            layout.addWidget(self.chart_message_label, stretch=1)
        else:
            self.chart_figure = Figure(figsize=(7, 3), tight_layout=True)
            self.chart_axes = self.chart_figure.add_subplot(111)
            self.chart_canvas = FigureCanvas(self.chart_figure)
            layout.addWidget(self.chart_canvas, stretch=1)
            layout.addWidget(self.chart_message_label)
            self._clear_chart()

        self._update_week_start_enabled()
        return frame

    def _update_week_start_enabled(self) -> None:
        """Show week start selector only for weekly grouping."""
        is_weekly = self._current_time_grouping() == "week"
        self.week_start_label.setVisible(is_weekly)
        self.week_start_combo.setVisible(is_weekly)
        self.week_start_combo.setEnabled(is_weekly and self.analysis_thread is None)

    def _current_time_grouping(self) -> str:
        """Return the selected time grouping."""
        return self.grouping_combo.currentData() or "day"

    def _current_week_start(self) -> str:
        """Return the selected week start day."""
        return self.week_start_combo.currentData() or "monday"

    def _clear_chart(self, message: str = "Analyze a file to see charts.") -> None:
        """Clear the chart and show a state message."""
        self._disconnect_chart_tooltip()
        self.current_time_series = None
        if self.chart_axes is not None:
            self.chart_axes.clear()
            self.chart_axes.set_axis_off()
            style_chart(self.chart_figure, self.chart_axes, self.theme)
        if self.chart_canvas is not None:
            self.chart_canvas.draw_idle()
        self.open_chart_button.setEnabled(False)
        _set_ui_text(self.chart_message_label, message, self.language)
        self.chart_message_label.show()

    def _update_chart(self, time_series: TimeSeriesResult) -> None:
        """Render the aggregated chart."""
        if self.chart_axes is None or self.chart_canvas is None:
            self.chart_message_label.show()
            return

        self._disconnect_chart_tooltip()
        self.current_time_series = None
        self.chart_axes.clear()
        if not time_series.points:
            self._clear_chart(time_series.message or "No chart data.")
            return

        if not time_series.visible_series:
            self._clear_chart("No non-zero chart values for selected columns.")
            return

        chart_lines = _draw_time_series_chart(
            self.chart_axes,
            self.chart_figure,
            time_series,
        )
        draw_forecast(self.chart_axes, time_series, self.current_forecast, chart_lines)
        draw_anomaly_markers(self.chart_axes, time_series, self.current_anomalies)
        _localize_chart(self.chart_axes, time_series, self.language)
        style_chart(self.chart_figure, self.chart_axes, self.theme)
        self.current_time_series = time_series
        self._connect_chart_tooltip(chart_lines, time_series.grouping)
        self.open_chart_button.setEnabled(True)
        self.chart_canvas.draw_idle()
        self.chart_message_label.hide()

    def _connect_chart_tooltip(
        self,
        chart_lines: list[tuple[object, str]],
        grouping: str,
    ) -> None:
        """Connect hover tooltip handling for the main chart."""
        if self.chart_canvas is None or self.chart_axes is None:
            return

        self.chart_hover_state = _create_chart_hover_state(
            self.chart_canvas,
            self.chart_axes,
            chart_lines,
            grouping,
            self.language,
        )
        self.chart_motion_connection = self.chart_canvas.mpl_connect(
            "motion_notify_event",
            lambda event: _update_chart_hover(event, self.chart_hover_state),
        )

    def _disconnect_chart_tooltip(self) -> None:
        """Disconnect previous chart tooltip handler."""
        if self.chart_hover_state is not None:
            _hide_chart_hover(self.chart_hover_state)
            self.chart_hover_state = None

        if self.chart_canvas is None or self.chart_motion_connection is None:
            return

        self.chart_canvas.mpl_disconnect(self.chart_motion_connection)
        self.chart_motion_connection = None

    def _open_chart_fullscreen(self) -> None:
        """Open the current chart in a maximized dialog."""
        if self.current_time_series is None:
            return

        dialog = ChartDialog(
            self.current_time_series,
            self.current_anomalies,
            self.current_forecast,
            self,
            language=self.language,
        )
        dialog.exec()

    def _update_detected_columns(self, loaded_file: LoadedFile) -> None:
        """Run keyword-based column detection and render the result."""
        result = detect_columns(loaded_file.column_names, loaded_file.preview_rows)
        self.current_detection_result = result
        self.available_column_names = loaded_file.column_names
        self.selected_columns = self._selected_columns_from_detection(result)
        self.detected_columns_label.setText(self._format_selected_columns_summary())
        self._update_detection_warning(result)
        self.configure_columns_button.setEnabled(bool(loaded_file.column_names))

    def _update_detection_warning(self, result: ColumnDetectionResult) -> None:
        """Display a confirmation warning when automatic detection is uncertain."""
        if not result.needs_user_confirmation:
            self.detection_warning_label.hide()
            return

        self.detection_warning_label.setText(_detection_warning_text(result, self.language))
        self.detection_warning_label.show()

    def _selected_columns_from_detection(
        self,
        result: ColumnDetectionResult,
    ) -> SelectedColumns:
        """Build initial selected columns from automatic detection."""
        selected = {}
        for role in COLUMN_ROLES:
            match = result.get(role)
            selected[role] = (match.column_name,) if match.column_name else ()
        return SelectedColumns(**selected)

    def _format_selected_columns_summary(self) -> str:
        """Format currently selected columns for the compact right panel."""
        lines = []
        for role in SELECTION_ROLES:
            selected = getattr(self.selected_columns, role)
            label = self.tr(SELECTION_LABELS[role])
            if selected:
                lines.append(f"{label}: {', '.join(selected)}")
            else:
                lines.append(f"{label}: {self.tr('not selected')}")
        return "\n".join(lines)

    def _open_column_selection_dialog(self) -> None:
        """Open a dialog for manual column configuration."""
        if self.current_detection_result is None:
            return

        dialog = ColumnSelectionDialog(
            self.available_column_names,
            self.current_detection_result,
            self.selected_columns,
            self,
            language=self.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.selected_columns = dialog.selected_columns()
        self.detected_columns_label.setText(self._format_selected_columns_summary())
        self._invalidate_analysis()
        _set_ui_text(self.metrics_label, "Selected columns updated. Click Analyze File.", self.language)
        self.metrics_details_button.hide()
        self.current_metrics = None
        self.current_metrics_text = ""
        self.current_anomalies = None
        _set_ui_text(self.anomalies_label, "Analyze a file to see anomalies.", self.language)
        self._set_detected_columns_visible(True)
        self._clear_chart()

    def _start_analysis(self) -> None:
        """Start full-file metric analysis using selected optional columns."""
        if self.analysis_thread is not None or self.preview_thread is not None or self.export_thread is not None or self.current_loaded_file is None:
            return

        selected_columns = self._get_selected_columns()
        if not selected_columns.has_money_column:
            self._show_load_error(tr("Select at least a Revenue, Expenses, or Amount column before analysis.", self.language))
            return

        try:
            cash_balance = self.analysis_options.cash_balance()
        except ValueError as error:
            self._show_load_error(str(error))
            return
        self._set_analysis_state(True)

        self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(
            str(self.current_loaded_file.path),
            selected_columns,
            self._current_time_grouping(),
            self._current_week_start(),
            language=self.language,
            cash_balance=cash_balance,
            anomaly_method=self.analysis_options.anomaly_method(),
        )
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.status_changed.connect(self.status_label.setText)
        self.analysis_worker.completed.connect(self._handle_analysis_completed)
        self.analysis_worker.failed.connect(self._handle_analysis_failed)
        self.analysis_worker.cancelled.connect(self._handle_analysis_cancelled)
        self.analysis_worker.progress_changed.connect(self._handle_analysis_progress)
        self.analysis_worker.finished.connect(self.analysis_thread.quit, Qt.ConnectionType.DirectConnection)
        self.analysis_thread.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self._finish_analysis)

        self.analysis_thread.start()

    def _start_export(self) -> None:
        """Ask for export options and write the report in the background."""
        if self.export_thread is not None or self.current_analysis_result is None:
            return
        if self.current_loaded_file is None:
            return

        result = self.current_analysis_result
        has_chart = bool(result.time_series.points and result.time_series.visible_series)

        dialog = ExportDialog(self, has_chart=has_chart, initial=self.last_export_options, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        options = dialog.options()
        report_format = WRITERS[options.format_key]
        source_path = Path(self.current_loaded_file.path)
        suggested = source_path.with_name(
            f"{source_path.stem}_report{report_format.extension}"
        )

        target_text, _selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("Save Report", self.language),
            str(suggested),
            f"{self.tr(report_format.label)} (*{report_format.extension})",
        )
        if not target_text:
            return

        target_path = Path(target_text)
        if target_path.suffix.lower() != report_format.extension:
            target_path = target_path.with_suffix(report_format.extension)

        self.last_export_options = options
        self._set_export_state(True)

        self.export_thread = QThread(self)
        self.export_worker = ExportWorker(
            target_path,
            options,
            result,
            source_path.name,
            language=self.language,
        )
        self.export_worker.moveToThread(self.export_thread)

        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.status_changed.connect(self.status_label.setText)
        self.export_worker.completed.connect(self._handle_export_completed)
        self.export_worker.failed.connect(self._handle_export_failed)
        self.export_worker.finished.connect(self.export_thread.quit, Qt.ConnectionType.DirectConnection)
        self.export_thread.finished.connect(self.export_worker.deleteLater)
        self.export_thread.finished.connect(self._finish_export)

        self.export_thread.start()

    def _set_export_state(self, is_running: bool) -> None:
        """Show that an export is in progress."""
        self.export_button.setEnabled(not is_running)
        self.load_button.setEnabled(not is_running)
        self.analyze_button.setEnabled(not is_running and self.current_loaded_file is not None)
        self.configure_columns_button.setEnabled(not is_running and self.current_loaded_file is not None)
        self.analysis_options.setEnabled(not is_running)
        self.analysis_options.profile_widget.setEnabled(not is_running)
        _set_ui_text(self.export_button, "Exporting..." if is_running else "Export Report...", self.language)
        if is_running:
            self.open_report_folder_button.hide()

    @Slot()
    def _finish_export(self) -> None:
        """Release the export thread."""
        if self.export_thread is not None:
            self.export_thread.wait()
            self.export_thread.deleteLater()
        self.export_thread = None
        self.export_worker = None
        self._set_export_state(False)
        self._maybe_close()

    def _handle_export_completed(self, target_path: str) -> None:
        """Report a written file and offer to reveal it."""
        self.last_export_path = Path(target_path)
        _set_ui_text(self.status_label, "Report saved to {path}", self.language, path=target_path)
        self.open_report_folder_button.show()

    def _handle_export_failed(self, message: str) -> None:
        """Report an export failure without taking the window down."""
        _set_ui_text(self.status_label, "Export failed.", self.language)
        self.open_report_folder_button.hide()
        QMessageBox.warning(self, tr("Export failed", self.language), message)

    def _open_report_folder(self) -> None:
        """Open the folder holding the most recent report."""
        if self.last_export_path is None:
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_export_path.parent)))

    def _get_selected_columns(self) -> SelectedColumns:
        """Return currently selected columns."""
        return self.selected_columns

    def _browse_all_rows(self) -> None:
        if self.current_loaded_file is not None:
            TableBrowserDialog(self.current_loaded_file.path, self, self.language).exec()

    def _save_mapping_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, self.tr('Save column mapping'), self.tr('Profile name:'))
        if not accepted:
            return
        try:
            self.mapping_profiles.save(name, self.selected_columns)
        except ValueError as error:
            self._show_load_error(self.tr(str(error)))
            return
        self.analysis_options.set_profiles(self.mapping_profiles.names())
        self.analysis_options.profile_combo.setCurrentText(name.strip())
        _set_ui_text(self.status_label, 'Column mapping saved.', self.language)

    def _apply_mapping_profile(self, name: str) -> None:
        if self.current_loaded_file is None:
            return
        try:
            selected = self.mapping_profiles.load(name, self.available_column_names)
        except MissingProfileColumns as error:
            self._show_load_error(self.tr('Missing columns: {columns}', columns=', '.join(error.columns)))
            return
        except ValueError as error:
            self._show_load_error(self.tr(str(error)))
            return
        self.selected_columns = selected
        self.detected_columns_label.setText(self._format_selected_columns_summary())
        self._invalidate_analysis()
        _set_ui_text(self.status_label, 'Column mapping applied. Analyze the file again.', self.language)

    def _delete_mapping_profile(self, name: str) -> None:
        self.mapping_profiles.delete(name)
        self.analysis_options.set_profiles(self.mapping_profiles.names())

    def _invalidate_analysis(self) -> None:
        """A new mapping cannot leave an export button for old results behind."""
        self.current_analysis_result = None
        self._update_dashboard(None)
        self.current_metrics = None
        self.current_metrics_text = ''
        self.current_anomalies = None
        self.current_forecast = None
        self.metrics_details_button.hide()
        self.export_button.hide()
        self.open_report_folder_button.hide()
        self.forecast_label.clear()
        _set_ui_text(self.metrics_label, 'Selected columns updated. Click Analyze File.', self.language)
        _set_ui_text(self.anomalies_label, 'Analyze a file to see anomalies.', self.language)
        self._set_detected_columns_visible(True)
        self._clear_chart()

    def _cancel_analysis(self) -> None:
        if self.analysis_worker is not None:
            self.analysis_worker.cancel()
            self.cancel_button.setEnabled(False)
            _set_ui_text(self.status_label, 'Cancelling analysis...', self.language)

    def _handle_analysis_cancelled(self) -> None:
        if self.current_analysis_result is not None:
            self._handle_analysis_completed(self.current_analysis_result)
        else:
            self._invalidate_analysis()
        _set_ui_text(self.status_label, 'Analysis cancelled.', self.language)

    def _handle_analysis_progress(self, done: int, total: int, unit: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(min(1000, round(done / total * 1000)))
        else:
            self.progress_bar.setRange(0, 0)
        if unit == 'bytes':
            _set_ui_text(self.status_label, 'Read {done} / {total}', self.language, done=format_file_size(done), total=format_file_size(total))
        else:
            _set_ui_text(self.status_label, 'Read rows: {done} / {total}', self.language, done=format_number(done), total=format_number(total))

    def _forecast_text(self, result: AnalysisResult) -> str:
        lines = []
        forecast = result.forecast
        if forecast is not None and forecast.has_forecast:
            lines.append(self.tr('Forecast for the next period:'))
            for item in forecast.forecasts:
                if item.points:
                    point = item.points[0]
                    lines.append(f'{series_label(self.language, item.series_key)} ({_format_chart_period(point.period, result.time_series.grouping)}): {format_money(point.value)}')
        elif forecast is not None:
            lines.append(self.tr('Forecast requires at least six valid periods.'))
        cash = calculate_cash_flow(result.metrics, result.cash_balance)
        if cash.cash_balance is not None:
            lines.append(f"{report_label(self.language, 'metric_cash_balance')}: {format_money(cash.cash_balance)}")
            if cash.runway_days is not None:
                lines.append(f"{report_label(self.language, 'metric_runway')}: {format_number(cash.runway_days)}")
            elif cash.daily_net_burn == 0:
                lines.append(self.tr('No cash depletion at the historical average.'))
            if cash.projected_balance_30_days is not None:
                lines.append(f"{report_label(self.language, 'metric_balance_30_days')}: {format_money(cash.projected_balance_30_days)}")
            if cash.daily_net_burn is None:
                lines.append(self.tr('Cash runway requires all money rows to have valid dates.') if result.metrics.undated_money_rows else self.tr('Cash runway requires dated revenue and expenses.'))
        if lines:
            lines.append(self.tr('Estimates use historical data; future results may differ.'))
        return '\n'.join(lines)

    def _update_forecast_summary(self, result: AnalysisResult) -> None:
        self.forecast_label.setText(self._forecast_text(result))

    def closeEvent(self, event) -> None:
        if any(thread is not None for thread in (self.preview_thread, self.analysis_thread, self.export_thread)):
            self._close_pending = True
            self._cancel_analysis()
            _set_ui_text(self.status_label, 'Waiting for background work to finish...', self.language)
            event.ignore()
            return
        super().closeEvent(event)

    def _maybe_close(self) -> None:
        if self._close_pending and all(thread is None for thread in (self.preview_thread, self.analysis_thread, self.export_thread)):
            QTimer.singleShot(0, self.close)

    def _set_analysis_state(self, is_running: bool) -> None:
        """Update controls while analysis is running."""
        self.analyze_button.setEnabled(not is_running)
        self.analysis_options.setEnabled(not is_running)
        self.analysis_options.profile_widget.setEnabled(not is_running)
        self.analysis_options.profile_widget.setEnabled(not is_running)
        self.browse_table_button.setEnabled(not is_running and self.current_loaded_file is not None)
        self.cancel_button.setVisible(is_running)
        self.cancel_button.setEnabled(is_running)
        self.export_button.setEnabled(not is_running)
        self.load_button.setEnabled(not is_running)
        self.configure_columns_button.setEnabled(
            not is_running and self.current_loaded_file is not None
        )
        self.grouping_combo.setEnabled(not is_running)
        self.week_start_combo.setEnabled(
            not is_running and self._current_time_grouping() == "week"
        )
        if is_running:
            _set_ui_text(self.analyze_button, "Analyzing...", self.language)
            _set_ui_text(self.metrics_label, "Analyzing selected columns...", self.language)
            _set_ui_text(self.anomalies_label, "Looking for unusual periods...", self.language)
            self.progress_bar.setRange(0, 0)
            self.progress_bar.show()
        else:
            _set_ui_text(self.analyze_button, "Analyze File", self.language)
            self.progress_bar.hide()

    @Slot()
    def _finish_analysis(self) -> None:
        """Restore controls after analysis finishes."""
        if self.analysis_thread is not None:
            self.analysis_thread.wait()
            self.analysis_thread.deleteLater()
        self.analysis_thread = None
        self.analysis_worker = None
        self._set_analysis_state(False)
        self._maybe_close()

    def _handle_analysis_completed(self, result: AnalysisResult) -> None:
        """Display calculated metrics."""
        self.current_metrics = result.metrics
        self.current_anomalies = result.anomalies
        self.current_forecast = result.forecast
        self.current_analysis_result = result
        self._update_dashboard(result.metrics)
        self._update_forecast_summary(result)
        self.current_metrics_text = self._format_analysis_details(
            result.metrics,
            result.anomalies,
            result.time_series.grouping,
        )
        self.metrics_label.setText(self._format_metrics_compact(result.metrics))
        self.anomalies_label.setText(
            self._format_anomalies_compact(result.anomalies, result.time_series.grouping)
        )
        self.metrics_details_button.show()
        self.export_button.show()
        self._set_detected_columns_visible(True)
        self._update_chart(result.time_series)
        _set_ui_text(self.status_label, "Analysis complete.", self.language)

    def _handle_analysis_failed(self, message: str) -> None:
        """Display an analysis error."""
        self._invalidate_analysis()
        _set_ui_text(self.metrics_label, "Analysis failed.", self.language)
        _set_ui_text(self.anomalies_label, "Anomaly detection failed.", self.language)
        self.metrics_details_button.hide()
        self.export_button.hide()
        self.open_report_folder_button.hide()
        self.current_analysis_result = None
        _set_ui_text(self.status_label, "Analysis failed.", self.language)
        self._show_load_error(message)

    def _set_detected_columns_visible(self, is_visible: bool) -> None:
        """Keep the selected mapping reviewable on the Data page after analysis."""
        self.detected_columns_title_label.setVisible(is_visible)
        self.detection_warning_label.setVisible(
            is_visible
            and self.current_detection_result is not None
            and self.current_detection_result.needs_user_confirmation
        )
        self.detected_columns_label.setVisible(is_visible)
        self.configure_columns_button.setVisible(is_visible)

    def _show_metrics_details(self) -> None:
        """Show full metrics in a dialog."""
        if not self.current_metrics_text:
            return

        QMessageBox.information(self, tr("Analysis Details", self.language), self.current_metrics_text)

    def _format_analysis_details(
        self,
        metrics: BasicMetrics,
        anomalies: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format full metrics and anomaly details."""
        sections = [self._format_metrics(metrics), self._format_anomalies_details(anomalies, grouping)]
        if self.current_analysis_result is not None:
            sections.append(self._forecast_text(self.current_analysis_result))
        return "\n\n".join(section for section in sections if section)

    def _format_metrics_compact(self, metrics: BasicMetrics) -> str:
        """Format only the highest-signal metrics for the compact panel."""
        lines = [self.tr("Transactions: {value}", value=self.tr(format_number(metrics.transaction_count)))]

        amount_only = (
            bool(self.selected_columns.amount)
            and not self.selected_columns.revenue
            and not self.selected_columns.expense
        )
        if amount_only:
            lines.append(self.tr("Amount: {value}", value=self.tr(format_money(metrics.total_profit))))
        else:
            if metrics.total_profit is not None:
                lines.append(self.tr("Profit: {value}", value=self.tr(format_money(metrics.total_profit))))
            elif metrics.total_revenue is not None:
                lines.append(self.tr("Revenue: {value}", value=self.tr(format_money(metrics.total_revenue))))
            elif metrics.total_expenses is not None:
                lines.append(self.tr("Expenses: {value}", value=self.tr(format_money(metrics.total_expenses))))

        if metrics.date_min is not None and metrics.date_max is not None:
            lines.append(self.tr("Period: {start} - {end}", start=f"{metrics.date_min:%Y-%m-%d}", end=f"{metrics.date_max:%Y-%m-%d}"))

        return "\n".join(lines[:3])

    def _format_metrics(self, metrics: BasicMetrics) -> str:
        """Format metrics for the right panel."""
        lines = [
            self.tr("Transactions: {value}", value=self.tr(format_number(metrics.transaction_count))),
            self.tr("Revenue fields: {value}", value=self.tr(format_number(metrics.revenue_column_count))),
            self.tr("Revenue: {value}", value=self.tr(format_money(metrics.total_revenue))),
            self.tr("Expense fields: {value}", value=self.tr(format_number(metrics.expense_column_count))),
            self.tr("Expenses: {value}", value=self.tr(format_money(metrics.total_expenses))),
            self.tr("Amount fields: {value}", value=self.tr(format_number(metrics.amount_column_count))),
            self.tr("Category fields: {value}", value=self.tr(format_number(metrics.category_column_count))),
            self.tr("Profit: {value}", value=self.tr(format_money(metrics.total_profit))),
            self.tr("Average revenue: {value}", value=self.tr(format_money(metrics.average_revenue))),
            self.tr("Average expense: {value}", value=self.tr(format_money(metrics.average_expense))),
        ]

        if metrics.date_min is not None and metrics.date_max is not None:
            lines.extend(
                [
                    self.tr("Period: {start} - {end}", start=f"{metrics.date_min:%Y-%m-%d}", end=f"{metrics.date_max:%Y-%m-%d}"),
                    self.tr("Period days: {value}", value=self.tr(format_number(metrics.period_days))),
                    self.tr("Average daily revenue: {value}", value=self.tr(format_money(metrics.average_daily_revenue))),
                    self.tr("Average daily expense: {value}", value=self.tr(format_money(metrics.average_daily_expense))),
                    self.tr("Average daily profit: {value}", value=self.tr(format_money(metrics.average_daily_profit))),
                ]
            )

        if metrics.top_categories:
            lines.append("")
            lines.append(tr("Top categories by profit:", self.language))
            for category in metrics.top_categories[:UI_CATEGORY_LIMIT]:
                lines.append(
                    self.tr("{category}: {profit} ({count} tx)", category=category.name, profit=self.tr(format_money(category.profit)), count=format_number(category.transaction_count))
                )

        if metrics.derived_categories:
            lines.extend(['', report_label(self.language, 'section_derived_categories') + ':'])
            for category in metrics.derived_categories:
                name = report_label(self.language, 'category_' + category.name)
                lines.append(self.tr('{category}: {profit} ({count} tx)', category=name, profit=format_money(category.profit), count=format_number(category.transaction_count)))

        return "\n".join(lines)

    def _format_anomalies_compact(
        self,
        result: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format a compact anomaly summary for the right panel."""
        if not result.has_anomalies:
            return self.tr(result.message)

        lines = [
            self.tr("{count} {noun} found.", count=format_number(result.total_found), noun=_pluralize_anomaly(result.total_found, self.language))
        ]
        for anomaly in result.anomalies[:3]:
            lines.append(self._format_anomaly_short(anomaly, grouping))

        if result.total_found > len(result.anomalies[:3]):
            lines.append(tr("Open details to see more.", self.language))

        return "\n".join(lines)

    def _format_anomalies_details(
        self,
        result: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format detailed anomaly text for the details dialog."""
        if not result.has_anomalies:
            return self.tr("Anomalies:\n{message}", message=self.tr(result.message))

        lines = [
            self.tr("Anomalies: {count} {noun} found", count=format_number(result.total_found), noun=_pluralize_anomaly(result.total_found, self.language))
        ]
        for anomaly in result.anomalies:
            period = _format_chart_period(anomaly.period, grouping)
            lines.append(
                self.tr("{severity}: {series} {kind} on {period}: {value} (usual {baseline}, rule: {rule})", severity=self.tr(anomaly.severity), series=self.tr(CHART_SERIES_LABELS[anomaly.series_key]), kind=self.tr(anomaly.kind), period=period, value=self.tr(format_money(anomaly.value)), baseline=self.tr(format_money(anomaly.baseline)), rule=anomaly.rule)
            )
            if anomaly.category:
                lines.append(self.tr('Largest category change: {category}', category=anomaly.category))

        return "\n".join(lines)

    def _format_anomaly_short(self, anomaly: FinancialAnomaly, grouping: str) -> str:
        """Format one anomaly for the compact panel."""
        period = _format_chart_period(anomaly.period, grouping)
        return (
            f"{period}: {self.tr(CHART_SERIES_LABELS[anomaly.series_key])} {self.tr(anomaly.kind)} "
            f"({self.tr(format_money(anomaly.value))})"
        )


def _pluralize_anomaly(count: int, language: str = "en") -> str:
    """Return an English singular or plural label for anomalies."""
    if language == "ru":
        return "аномалия" if count % 10 == 1 and count % 100 != 11 else "аномалии" if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14) else "аномалий"
    return "anomaly" if count == 1 else "anomalies"
