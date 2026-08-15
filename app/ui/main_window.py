"""Main application window for Profilytix."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
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
from app.ml.anomaly_detection import (
    AnomalyDetectionResult,
    FinancialAnomaly,
    detect_financial_anomalies,
)
from app.reports.chart_image import (
    CHART_SERIES_LABELS,
    draw_anomaly_markers,
    draw_time_series_chart as _draw_time_series_chart,
    format_chart_axis_value as _format_chart_axis_value,
)
from app.services.analysis_loader import load_selected_columns
from app.services.file_loader import (
    FileLoadError,
    LoadedFile,
    format_file_size,
    load_file_preview,
)


# Analysis keeps a wider category breakdown than the panel shows, because a
# detailed exported report wants the full list.
ANALYSIS_CATEGORY_LIMIT = 25
UI_CATEGORY_LIMIT = 5


@dataclass(frozen=True)
class AnalysisResult:
    """Metrics and chart data calculated for a file."""

    metrics: BasicMetrics
    time_series: TimeSeriesResult
    anomalies: AnomalyDetectionResult


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
    is_visible: bool = False


class FilePreviewWorker(QObject):
    """Load a file preview outside the UI thread."""

    loaded = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)
    finished = Signal()

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path

    @Slot()
    def run(self) -> None:
        """Load the selected file preview and report the result."""
        try:
            path = Path(self.file_path)
            self.status_changed.emit(f"Loading preview for {path.name}...")
            loaded_file = load_file_preview(path)
        except FileLoadError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(f"Unexpected error while loading file: {error}")
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

    def __init__(
        self,
        file_path: str,
        selected_columns: SelectedColumns,
        grouping: str,
        week_start: str,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.selected_columns = selected_columns
        self.grouping = grouping
        self.week_start = week_start

    @Slot()
    def run(self) -> None:
        """Load selected columns and calculate metrics."""
        try:
            path = Path(self.file_path)
            self.status_changed.emit(f"Analyzing {path.name}...")
            data = load_selected_columns(path, self.selected_columns)
            prepared = prepare_financial_data(data, self.selected_columns)
            metrics = calculate_basic_metrics_from_prepared(
                prepared,
                category_limit=ANALYSIS_CATEGORY_LIMIT,
            )
            time_series = calculate_time_series(prepared, self.grouping, self.week_start)
            anomalies = detect_financial_anomalies(time_series)
        except FileLoadError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(f"Unexpected error while analyzing file: {error}")
        else:
            self.completed.emit(
                AnalysisResult(
                    metrics=metrics,
                    time_series=time_series,
                    anomalies=anomalies,
                )
            )
        finally:
            self.finished.emit()


def _detection_warning_text(result: ColumnDetectionResult) -> str:
    """Return a short warning for uncertain automatic detection."""
    if result.weak_headers:
        return "Column names look generic. Please confirm the selected columns."
    return "Please confirm detected columns before analysis."


def _format_detection_summary(result: ColumnDetectionResult) -> str:
    """Format automatic detection results."""
    lines = []
    for role in COLUMN_ROLES:
        match = result.get(role)
        label = ROLE_LABELS[role]
        if match.column_name is None:
            lines.append(f"{label}: not found")
        else:
            confidence = int(match.confidence * 100)
            lines.append(f"{label}: {match.column_name} ({confidence}%)")
    return "\n".join(lines)


def _format_detection_candidates(result: ColumnDetectionResult) -> str:
    """Format useful alternative candidates."""
    lines = []

    if result.money_candidates:
        lines.append(f"Money candidates: {_format_candidates(result.money_candidates)}")

    if result.direction_candidates:
        lines.append(f"Direction candidates: {_format_candidates(result.direction_candidates)}")

    for role in COLUMN_ROLES:
        if result.get(role).column_name is not None:
            continue
        candidates = result.candidates.get(role, [])
        if candidates:
            lines.append(f"{ROLE_LABELS[role]} candidates: {_format_candidates(candidates)}")

    return "\n".join(lines)


def _format_candidates(candidates: list[ColumnCandidate]) -> str:
    """Format column candidates with compact confidence labels."""
    formatted = []
    for candidate in candidates[:5]:
        confidence = int(candidate.confidence * 100)
        reason = f", {candidate.reason}" if candidate.reason else ""
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


def _format_chart_tooltip(series_key: str, period: object, value: float, grouping: str) -> str:
    """Format hover tooltip text for a chart point."""
    return (
        f"Date: {_format_chart_period(period, grouping)}\n"
        f"{CHART_SERIES_LABELS[series_key]}: {_format_chart_hover_value(value)}"
    )


def _create_chart_hover_state(
    canvas: QWidget,
    axes: object,
    chart_lines: list[tuple[object, str]],
    grouping: str,
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
            f"{_format_chart_hover_value(y_value)} {CHART_SERIES_LABELS[series_key]}"
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.time_series = time_series
        self.anomalies = anomalies
        self.motion_connection: int | None = None
        self.hover_state: ChartHoverState | None = None
        self.setWindowTitle("Charts")
        self.resize(1280, 800)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build and render the fullscreen chart."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        if Figure is None or FigureCanvas is None:
            label = QLabel("Install matplotlib to show charts.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label, stretch=1)
            return

        self.figure = Figure(figsize=(12, 7), tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.axes.clear()
        chart_lines = _draw_time_series_chart(self.axes, self.figure, self.time_series)
        draw_anomaly_markers(self.axes, self.time_series, self.anomalies)
        self.hover_state = _create_chart_hover_state(
            self.canvas,
            self.axes,
            chart_lines,
            self.time_series.grouping,
        )
        self.motion_connection = self.canvas.mpl_connect(
            "motion_notify_event",
            lambda event: _update_chart_hover(event, self.hover_state),
        )
        layout.addWidget(self.canvas, stretch=1)


class ColumnSelectionDialog(QDialog):
    """Dialog for reviewing and manually selecting analysis columns."""

    def __init__(
        self,
        column_names: list[str],
        detection_result: ColumnDetectionResult,
        selected_columns: SelectedColumns,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.column_names = column_names
        self.detection_result = detection_result
        self.role_layouts: dict[str, QVBoxLayout] = {}
        self.role_rows: dict[str, list[tuple[QWidget, QComboBox, QPushButton]]] = {
            role: [] for role in COLUMN_ROLES
        }
        self.setWindowTitle("Configure Columns")
        self.resize(720, 520)
        self._setup_ui(selected_columns)

    def _setup_ui(self, selected_columns: SelectedColumns) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel("Configure Columns")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        warning_label = QLabel("")
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #8a5a00;")
        if self.detection_result.needs_user_confirmation:
            warning_label.setText(_detection_warning_text(self.detection_result))
        else:
            warning_label.hide()

        detected_label = QLabel(_format_detection_summary(self.detection_result))
        detected_label.setWordWrap(True)
        detected_label.setStyleSheet("color: #444444;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        selector_widget = QWidget()
        selector_layout = QGridLayout(selector_widget)
        selector_layout.setHorizontalSpacing(12)
        selector_layout.setVerticalSpacing(10)

        for row_index, role in enumerate(COLUMN_ROLES):
            label = QLabel(f"{ROLE_LABELS[role]}:")
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

        candidates_text = _format_detection_candidates(self.detection_result)
        candidates_label = QLabel(candidates_text)
        candidates_label.setWordWrap(True)
        candidates_label.setStyleSheet("color: #666666;")
        if not candidates_text:
            candidates_label.hide()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
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
        combo.addItem("Not selected", None)
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

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("Profilytix", "Profilytix")
        self.preview_thread: QThread | None = None
        self.preview_worker: FilePreviewWorker | None = None
        self.analysis_thread: QThread | None = None
        self.analysis_worker: AnalysisWorker | None = None
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
        self.setWindowTitle("Profilytix")
        self.resize(1000, 700)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the initial application layout."""
        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title_label = QLabel("Profilytix")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-size: 24px; font-weight: 600;")

        self.load_button = QPushButton("Load Excel/CSV")
        self.load_button.setMinimumHeight(36)
        self.load_button.clicked.connect(self._choose_file)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.load_button)

        table_preview_area = self._create_table_preview_area()
        metrics_area = self._create_analysis_area()
        chart_area = self._create_chart_area()

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(table_preview_area)
        self.content_splitter.addWidget(metrics_area)
        self.content_splitter.setStretchFactor(0, 4)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([760, 300])

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.content_splitter)
        self.main_splitter.addWidget(chart_area)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([480, 280])

        root_layout.addLayout(header_layout)
        root_layout.addWidget(self.main_splitter, stretch=1)

        self.setCentralWidget(central_widget)

    def _choose_file(self) -> None:
        """Open a file picker and load the selected spreadsheet."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Excel/CSV",
            str(self._get_initial_file_directory()),
            "Data files (*.csv *.xlsx *.xls);;CSV files (*.csv);;Excel files (*.xlsx *.xls)",
        )

        if not file_path:
            return

        self._start_preview_loading(file_path)

    def _start_preview_loading(self, file_path: str) -> None:
        """Start loading a file preview in a background thread."""
        if self.preview_thread is not None:
            return

        self._set_loading_state(file_path)

        self.preview_thread = QThread(self)
        self.preview_worker = FilePreviewWorker(file_path)
        self.preview_worker.moveToThread(self.preview_thread)

        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.status_changed.connect(self.status_label.setText)
        self.preview_worker.loaded.connect(self._handle_preview_loaded)
        self.preview_worker.failed.connect(self._handle_preview_failed)
        self.preview_worker.finished.connect(self.preview_thread.quit)
        self.preview_worker.finished.connect(self.preview_worker.deleteLater)
        self.preview_thread.finished.connect(self.preview_thread.deleteLater)
        self.preview_thread.finished.connect(self._finish_preview_loading)

        self.preview_thread.start()

    def _set_loading_state(self, file_path: str) -> None:
        """Update controls while a preview is loading."""
        path = Path(file_path)
        size_text = ""
        if path.is_file():
            size_text = f" ({format_file_size(path.stat().st_size)})"

        self.load_button.setEnabled(False)
        self.load_button.setText("Loading...")
        self.configure_columns_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.status_label.setText(f"Loading preview for {path.name}{size_text}...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()

    def _finish_preview_loading(self) -> None:
        """Restore controls after the preview worker finishes."""
        self.load_button.setEnabled(True)
        self.load_button.setText("Load Excel/CSV")
        has_loaded_file = self.current_loaded_file is not None
        self.configure_columns_button.setEnabled(has_loaded_file)
        self.analyze_button.setEnabled(has_loaded_file)
        self.progress_bar.hide()
        self.preview_thread = None
        self.preview_worker = None

    def _handle_preview_loaded(self, loaded_file: LoadedFile) -> None:
        """Display the loaded preview returned by the worker."""
        self._remember_file_directory(loaded_file.path)
        self._show_loaded_file(loaded_file)
        self.status_label.setText(f"Preview loaded: {loaded_file.file_name}")

    def _handle_preview_failed(self, message: str) -> None:
        """Display a preview loading error returned by the worker."""
        self.status_label.setText("Could not load preview.")
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
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumWidth(360)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel("Table preview")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.file_info_label = QLabel("No file loaded.")
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setStyleSheet("color: #444444;")

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #666666;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.verticalHeader().setVisible(False)

        layout.addWidget(title_label)
        layout.addWidget(self.file_info_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
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
        message_label.setStyleSheet("color: #666666;")

        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(message_label)
        layout.addStretch()

        return frame

    def _show_loaded_file(self, loaded_file: LoadedFile) -> None:
        """Display loaded file metadata and the first 100 rows."""
        self.current_loaded_file = loaded_file
        self.current_metrics = None
        self.current_metrics_text = ""
        self.current_time_series = None
        self.current_anomalies = None
        self.current_anomalies = None
        self._update_file_info(loaded_file)
        self._update_table_preview(loaded_file.column_names, loaded_file.preview_rows)
        self._update_detected_columns(loaded_file)
        self.metrics_label.setText("Select one or more columns and click Analyze File.")
        self.metrics_details_button.hide()
        self.anomalies_label.setText("Analyze a file to see anomalies.")
        self._set_detected_columns_visible(True)
        self._clear_chart()
        self.analyze_button.setEnabled(True)

    def _update_file_info(self, loaded_file: LoadedFile) -> None:
        """Display the loaded file name, shape, columns, and encoding."""
        columns = ", ".join(loaded_file.column_names) if loaded_file.column_names else "No columns"
        encoding_text = f"\nCSV encoding: {loaded_file.encoding}" if loaded_file.encoding else ""
        delimiter_text = f"\nCSV delimiter: {loaded_file.delimiter}" if loaded_file.delimiter else ""
        reader_text = f"\nReader: {loaded_file.reader}" if loaded_file.reader else ""
        self.file_info_label.setText(
            f"File: {loaded_file.file_name}\n"
            f"Size: {loaded_file.file_size_text}\n"
            f"Rows: {loaded_file.row_count_text}\n"
            f"Columns: {loaded_file.column_count}\n"
            f"Preview rows: {loaded_file.preview_row_count}\n"
            f"Column names: {columns}"
            f"{encoding_text}"
            f"{delimiter_text}"
            f"{reader_text}"
        )

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
        QMessageBox.warning(self, "Could not load file", message)

    def _create_analysis_area(self) -> QFrame:
        """Create the detected columns and metrics area."""
        frame = QFrame(self)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumHeight(240)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.detected_columns_title_label = QLabel("Detected columns")
        self.detected_columns_title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.detection_warning_label = QLabel("")
        self.detection_warning_label.setWordWrap(True)
        self.detection_warning_label.setStyleSheet("color: #8a5a00;")
        self.detection_warning_label.hide()

        self.detected_columns_label = QLabel("Load a file to detect columns.")
        self.detected_columns_label.setWordWrap(True)
        self.detected_columns_label.setStyleSheet("color: #444444;")

        self.configure_columns_button = QPushButton("Configure Columns...")
        self.configure_columns_button.setEnabled(False)
        self.configure_columns_button.clicked.connect(self._open_column_selection_dialog)

        metrics_title_label = QLabel("Metrics")
        metrics_title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.metrics_label = QLabel("Metrics will be calculated in the next step.")
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setStyleSheet("color: #666666;")

        self.metrics_details_button = QPushButton("Show Details...")
        self.metrics_details_button.clicked.connect(self._show_metrics_details)
        self.metrics_details_button.hide()

        anomalies_title_label = QLabel("Anomalies")
        anomalies_title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.anomalies_label = QLabel("Analyze a file to see anomalies.")
        self.anomalies_label.setWordWrap(True)
        self.anomalies_label.setStyleSheet("color: #666666;")

        self.analyze_button = QPushButton("Analyze File")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._start_analysis)

        layout.addWidget(self.detected_columns_title_label)
        layout.addWidget(self.detection_warning_label)
        layout.addWidget(self.detected_columns_label)
        layout.addWidget(self.configure_columns_button)
        layout.addSpacing(12)
        layout.addWidget(metrics_title_label)
        layout.addWidget(self.metrics_label)
        layout.addWidget(self.metrics_details_button)
        layout.addSpacing(8)
        layout.addWidget(anomalies_title_label)
        layout.addWidget(self.anomalies_label)
        layout.addStretch()
        layout.addWidget(self.analyze_button)

        return frame

    def _create_chart_area(self) -> QFrame:
        """Create the time-series chart area."""
        frame = QFrame(self)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setMinimumHeight(240)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        title_label = QLabel("Charts")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        grouping_label = QLabel("Group by:")
        self.grouping_combo = QComboBox()
        for value, label in TIME_GROUPINGS.items():
            self.grouping_combo.addItem(label, value)
        self.grouping_combo.setCurrentIndex(self.grouping_combo.findData("day"))
        self.grouping_combo.currentIndexChanged.connect(self._update_week_start_enabled)

        self.week_start_label = QLabel("Week starts:")
        self.week_start_combo = QComboBox()
        for value, (label, _index) in WEEK_START_DAYS.items():
            self.week_start_combo.addItem(label, value)
        self.week_start_combo.setCurrentIndex(self.week_start_combo.findData("monday"))

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(grouping_label)
        header_layout.addWidget(self.grouping_combo)
        header_layout.addWidget(self.week_start_label)
        header_layout.addWidget(self.week_start_combo)

        self.open_chart_button = QPushButton("Open Fullscreen")
        self.open_chart_button.setEnabled(False)
        self.open_chart_button.clicked.connect(self._open_chart_fullscreen)
        header_layout.addWidget(self.open_chart_button)

        self.chart_message_label = QLabel("Analyze a file to see charts.")
        self.chart_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_message_label.setStyleSheet("color: #666666;")

        layout.addLayout(header_layout)

        if Figure is None or FigureCanvas is None:
            self.chart_message_label.setText("Install matplotlib to show charts.")
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
        if self.chart_canvas is not None:
            self.chart_canvas.draw_idle()
        self.open_chart_button.setEnabled(False)
        self.chart_message_label.setText(message)
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
        draw_anomaly_markers(self.chart_axes, time_series, self.current_anomalies)
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

        dialog = ChartDialog(self.current_time_series, self.current_anomalies, self)
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

        self.detection_warning_label.setText(_detection_warning_text(result))
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
        for role in COLUMN_ROLES:
            selected = getattr(self.selected_columns, role)
            label = ROLE_LABELS[role]
            if selected:
                lines.append(f"{label}: {', '.join(selected)}")
            else:
                lines.append(f"{label}: not selected")
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
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.selected_columns = dialog.selected_columns()
        self.detected_columns_label.setText(self._format_selected_columns_summary())
        self.metrics_label.setText("Selected columns updated. Click Analyze File.")
        self.metrics_details_button.hide()
        self.current_metrics = None
        self.current_metrics_text = ""
        self.current_anomalies = None
        self.anomalies_label.setText("Analyze a file to see anomalies.")
        self._set_detected_columns_visible(True)
        self._clear_chart()

    def _start_analysis(self) -> None:
        """Start full-file metric analysis using selected optional columns."""
        if self.analysis_thread is not None or self.current_loaded_file is None:
            return

        selected_columns = self._get_selected_columns()
        if not selected_columns.has_money_column:
            self._show_load_error("Select at least a Revenue, Expenses, or Amount column before analysis.")
            return

        self._set_analysis_state(True)

        self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(
            str(self.current_loaded_file.path),
            selected_columns,
            self._current_time_grouping(),
            self._current_week_start(),
        )
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.status_changed.connect(self.status_label.setText)
        self.analysis_worker.completed.connect(self._handle_analysis_completed)
        self.analysis_worker.failed.connect(self._handle_analysis_failed)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_thread.finished.connect(self._finish_analysis)

        self.analysis_thread.start()

    def _get_selected_columns(self) -> SelectedColumns:
        """Return currently selected columns."""
        return self.selected_columns

    def _set_analysis_state(self, is_running: bool) -> None:
        """Update controls while analysis is running."""
        self.analyze_button.setEnabled(not is_running)
        self.load_button.setEnabled(not is_running)
        self.configure_columns_button.setEnabled(
            not is_running and self.current_loaded_file is not None
        )
        self.grouping_combo.setEnabled(not is_running)
        self.week_start_combo.setEnabled(
            not is_running and self._current_time_grouping() == "week"
        )
        if is_running:
            self.analyze_button.setText("Analyzing...")
            self.metrics_label.setText("Analyzing selected columns...")
            self.anomalies_label.setText("Looking for unusual periods...")
            self.progress_bar.setRange(0, 0)
            self.progress_bar.show()
        else:
            self.analyze_button.setText("Analyze File")
            self.progress_bar.hide()

    def _finish_analysis(self) -> None:
        """Restore controls after analysis finishes."""
        self.analysis_thread = None
        self.analysis_worker = None
        self._set_analysis_state(False)

    def _handle_analysis_completed(self, result: AnalysisResult) -> None:
        """Display calculated metrics."""
        self.current_metrics = result.metrics
        self.current_anomalies = result.anomalies
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
        self._set_detected_columns_visible(False)
        self._update_chart(result.time_series)
        self.status_label.setText("Analysis complete.")

    def _handle_analysis_failed(self, message: str) -> None:
        """Display an analysis error."""
        self.metrics_label.setText("Analysis failed.")
        self.anomalies_label.setText("Anomaly detection failed.")
        self.metrics_details_button.hide()
        self.status_label.setText("Analysis failed.")
        self._show_load_error(message)

    def _set_detected_columns_visible(self, is_visible: bool) -> None:
        """Show column selection controls before analysis and hide them after analysis."""
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

        QMessageBox.information(self, "Analysis Details", self.current_metrics_text)

    def _format_analysis_details(
        self,
        metrics: BasicMetrics,
        anomalies: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format full metrics and anomaly details."""
        sections = [self._format_metrics(metrics), self._format_anomalies_details(anomalies, grouping)]
        return "\n\n".join(section for section in sections if section)

    def _format_metrics_compact(self, metrics: BasicMetrics) -> str:
        """Format only the highest-signal metrics for the compact panel."""
        lines = [f"Transactions: {format_number(metrics.transaction_count)}"]

        amount_only = (
            bool(self.selected_columns.amount)
            and not self.selected_columns.revenue
            and not self.selected_columns.expense
        )
        if amount_only:
            lines.append(f"Amount: {format_money(metrics.total_profit)}")
        else:
            if metrics.total_profit is not None:
                lines.append(f"Profit: {format_money(metrics.total_profit)}")
            elif metrics.total_revenue is not None:
                lines.append(f"Revenue: {format_money(metrics.total_revenue)}")
            elif metrics.total_expenses is not None:
                lines.append(f"Expenses: {format_money(metrics.total_expenses)}")

        if metrics.date_min is not None and metrics.date_max is not None:
            lines.append(f"Period: {metrics.date_min:%Y-%m-%d} - {metrics.date_max:%Y-%m-%d}")

        return "\n".join(lines[:3])

    def _format_metrics(self, metrics: BasicMetrics) -> str:
        """Format metrics for the right panel."""
        lines = [
            f"Transactions: {format_number(metrics.transaction_count)}",
            f"Revenue fields: {format_number(metrics.revenue_column_count)}",
            f"Revenue: {format_money(metrics.total_revenue)}",
            f"Expense fields: {format_number(metrics.expense_column_count)}",
            f"Expenses: {format_money(metrics.total_expenses)}",
            f"Amount fields: {format_number(metrics.amount_column_count)}",
            f"Category fields: {format_number(metrics.category_column_count)}",
            f"Profit: {format_money(metrics.total_profit)}",
            f"Average revenue: {format_money(metrics.average_revenue)}",
            f"Average expense: {format_money(metrics.average_expense)}",
        ]

        if metrics.date_min is not None and metrics.date_max is not None:
            lines.extend(
                [
                    f"Period: {metrics.date_min:%Y-%m-%d} - {metrics.date_max:%Y-%m-%d}",
                    f"Period days: {format_number(metrics.period_days)}",
                    f"Average daily revenue: {format_money(metrics.average_daily_revenue)}",
                    f"Average daily expense: {format_money(metrics.average_daily_expense)}",
                    f"Average daily profit: {format_money(metrics.average_daily_profit)}",
                ]
            )

        if metrics.top_categories:
            lines.append("")
            lines.append("Top categories by profit:")
            for category in metrics.top_categories[:UI_CATEGORY_LIMIT]:
                lines.append(
                    f"{category.name}: {format_money(category.profit)} "
                    f"({format_number(category.transaction_count)} tx)"
                )

        return "\n".join(lines)

    def _format_anomalies_compact(
        self,
        result: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format a compact anomaly summary for the right panel."""
        if not result.has_anomalies:
            return result.message

        lines = [
            f"{format_number(result.total_found)} {_pluralize_anomaly(result.total_found)} found."
        ]
        for anomaly in result.anomalies[:3]:
            lines.append(self._format_anomaly_short(anomaly, grouping))

        if result.total_found > len(result.anomalies[:3]):
            lines.append("Open details to see more.")

        return "\n".join(lines)

    def _format_anomalies_details(
        self,
        result: AnomalyDetectionResult,
        grouping: str,
    ) -> str:
        """Format detailed anomaly text for the details dialog."""
        if not result.has_anomalies:
            return f"Anomalies:\n{result.message}"

        lines = [
            f"Anomalies: {format_number(result.total_found)} "
            f"{_pluralize_anomaly(result.total_found)} found"
        ]
        for anomaly in result.anomalies:
            period = _format_chart_period(anomaly.period, grouping)
            lines.append(
                f"{anomaly.severity}: {anomaly.series_label} {anomaly.kind} on {period}: "
                f"{format_money(anomaly.value)} "
                f"(usual {format_money(anomaly.baseline)}, rule: {anomaly.rule})"
            )

        return "\n".join(lines)

    def _format_anomaly_short(self, anomaly: FinancialAnomaly, grouping: str) -> str:
        """Format one anomaly for the compact panel."""
        period = _format_chart_period(anomaly.period, grouping)
        return (
            f"{period}: {anomaly.series_label} {anomaly.kind} "
            f"({format_money(anomaly.value)})"
        )


def _pluralize_anomaly(count: int) -> str:
    """Return an English singular or plural label for anomalies."""
    return "anomaly" if count == 1 else "anomalies"
