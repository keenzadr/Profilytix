"""Desktop language choices preserve analysis and original spreadsheet values."""

import os
from datetime import datetime
from pathlib import Path
from string import Formatter

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel

from app.analytics.metrics import build_basic_metrics
from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
from app.ml.anomaly_detection import AnomalyDetectionResult
from app.services.file_loader import LoadedFile
from app.ui import main_window
from app.ui.export_dialog import ExportDialog, ExportOptions


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *args: settings)
    widget = main_window.MainWindow()
    yield widget
    widget.close()
    app.processEvents()


def test_default_language_is_russian_and_choice_is_persisted(window):
    assert window.language == "ru"
    assert window.load_button.text() == "Загрузить Excel/CSV"
    assert window.language_combo.currentData() == "ru"
    window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
    assert window.load_button.text() == "Load Excel/CSV"
    assert window.settings.value("ui_language") == "en"
    second = main_window.MainWindow()
    assert second.language == "en"
    second.close()


def test_language_switch_preserves_table_selection_and_analysis(window):
    loaded = LoadedFile(Path("Revenue.csv"), ["Revenue", "Category"], [["300", "Sales"]], 50, 1)
    window._show_loaded_file(loaded)
    selected = window.selected_columns
    metrics = build_basic_metrics(transaction_count=1, total_revenue=300, total_expenses=100)
    series = TimeSeriesResult([TimeSeriesPoint(datetime(2026, 1, 1), 300, 100, 200, 0)], "day", "monday", ("revenue", "profit"))
    result = main_window.AnalysisResult(metrics, series, AnomalyDetectionResult((), 0, "No unusual periods found with the current grouping."))
    window._handle_analysis_completed(result)
    window.set_language("en")
    assert "Transactions: 1" in window.metrics_label.text()
    window.set_language("ru")
    assert window.current_loaded_file is loaded
    assert window.current_analysis_result is result
    assert window.selected_columns == selected
    assert window.table_widget.item(0, 1).text() == "Sales"
    assert window.table_widget.horizontalHeaderItem(0).text() == "Revenue"
    assert "Операции: 1" in window.metrics_label.text()
    assert "Revenue.csv" in window.file_info_label.text()
    assert "Выручка" in window.chart_axes.get_legend_handles_labels()[1]
    assert window.status_label.text() == "Анализ завершён."


def test_export_ui_language_is_independent_of_report_language(window):
    dialog = ExportDialog(language="ru", initial=ExportOptions("xlsx", "detailed", "en"))
    assert dialog.windowTitle() == "Экспорт отчёта"
    assert dialog.options().language == "en"
    assert any(label.text() == "Формат:" for label in dialog.findChildren(QLabel))
    dialog.close()


def test_ui_catalog_has_matching_templates_and_preserves_parameters():
    from app.ui.strings import STRINGS, tr

    assert STRINGS["ru"].keys() == STRINGS["en"].keys()
    for key in STRINGS["en"]:
        fields = lambda text: {field for _, field, _, _ in Formatter().parse(text) if field}
        assert fields(STRINGS["ru"][key]) == fields(STRINGS["en"][key]), key
    assert tr("Report saved to {path}", "ru", path="Revenue.csv") == "Отчёт сохранён: Revenue.csv"
    assert tr("Read {done} / {total}", "ru", done="1 MB", total="5 MB") == "Прочитано: 1 MB / 5 MB"
    assert tr("Description (categorisation)", "ru") == "Описание (категоризация)"
    assert tr("Largest category change: {category}", "ru", category="Sales") == "Наибольшее изменение категории: Sales"
    assert tr("Need at least 8 periods to detect anomalies.", "ru") == "Для поиска аномалий нужно не менее 8 периодов."


def test_localized_detection_and_hover_helpers(window):
    result = main_window.detect_columns(["Revenue"])
    assert "Выручка: Revenue" in main_window._format_detection_summary(result, language="ru")
    assert "Дата:" in main_window._format_chart_tooltip("profit", datetime(2026, 1, 1), 20, "day", language="ru")
    assert "Прибыль: 20" in main_window._format_chart_tooltip("profit", datetime(2026, 1, 1), 20, "day", language="ru")


def test_metadata_empty_values_and_chart_empty_state_follow_language(window):
    loaded = LoadedFile(Path("Revenue.csv"), ["Revenue"], [["300"]], 50, 1, "utf-8", ";", "csv")
    window._show_loaded_file(loaded)
    assert "Файл: Revenue.csv" in window.file_info_label.text()
    metrics = build_basic_metrics(transaction_count=1, total_revenue=None, total_expenses=None)
    assert "нет данных" in window._format_metrics(metrics)
    window._update_chart(TimeSeriesResult([], "day", "monday", message="Select a date column to build a chart."))
    assert window.chart_message_label.text() == "Выберите столбец даты для построения графика."
    window.set_language("en")
    assert window.chart_message_label.text() == "Select a date column to build a chart."


def test_unknown_error_detail_braces_are_preserved():
    from app.ui.strings import tr

    assert tr("Unknown field {custom}", "ru") == "Unknown field {custom}"
