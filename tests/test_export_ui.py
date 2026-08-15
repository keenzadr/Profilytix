"""Tests for the export dialog and the background export worker.

Qt runs on the offscreen platform here, so these exercise the real widgets and
the real worker without opening a window.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.analytics.metrics import CategoryMetric, build_basic_metrics  # noqa: E402
from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult  # noqa: E402
from app.ml.anomaly_detection import AnomalyDetectionResult, FinancialAnomaly  # noqa: E402
from app.reports.builder import DEPTH_BRIEF, DEPTH_DETAILED  # noqa: E402
from app.ui.export_dialog import ExportDialog, ExportOptions  # noqa: E402
from app.ui.main_window import AnalysisResult, ExportWorker  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    """Provide the single QApplication these tests share."""
    app = QApplication.instance() or QApplication([])
    yield app


def make_result(with_chart: bool = True) -> AnalysisResult:
    points = [
        TimeSeriesPoint(
            period=datetime(2026, 1, day),
            revenue=100.0 * day,
            expenses=40.0 * day,
            profit=60.0 * day,
            amount=60.0 * day,
        )
        for day in range(1, 7)
    ]
    series = TimeSeriesResult(
        points=points if with_chart else [],
        grouping="day",
        week_start="monday",
        visible_series=("revenue", "expenses", "profit") if with_chart else (),
    )
    metrics = build_basic_metrics(
        transaction_count=42,
        total_revenue=2100.0,
        total_expenses=840.0,
        revenue_column_count=1,
        expense_column_count=1,
        category_column_count=1,
        date_min=datetime(2026, 1, 1),
        date_max=datetime(2026, 1, 6),
        top_categories=(CategoryMetric("Продажи", 20, 2100.0, 0.0, 2100.0),),
    )
    anomalies = AnomalyDetectionResult(
        anomalies=(
            FinancialAnomaly(
                period=datetime(2026, 1, 6),
                series_key="revenue",
                series_label="Revenue",
                kind="spike",
                value=600.0,
                baseline=300.0,
                score=3.0,
                rule="IQR",
                severity="High",
            ),
        ),
        total_found=1,
    )
    return AnalysisResult(metrics=metrics, time_series=series, anomalies=anomalies)


# Dialog.


def test_dialog_defaults_to_brief_russian_pdf(qt_app):
    dialog = ExportDialog(has_chart=True)

    assert dialog.options() == ExportOptions("pdf", DEPTH_BRIEF, "ru")


def test_dialog_returns_the_selection(qt_app):
    dialog = ExportDialog(
        has_chart=True,
        initial=ExportOptions("xlsx", DEPTH_DETAILED, "en"),
    )

    assert dialog.options() == ExportOptions("xlsx", DEPTH_DETAILED, "en")


def test_dialog_offers_every_registered_format(qt_app):
    dialog = ExportDialog(has_chart=True)
    offered = {dialog.format_combo.itemData(row) for row in range(dialog.format_combo.count())}

    from app.reports.writers import WRITERS

    assert offered == set(WRITERS)


def test_chart_only_format_is_disabled_without_a_chart(qt_app):
    dialog = ExportDialog(has_chart=False)
    model = dialog.format_combo.model()

    for row in range(dialog.format_combo.count()):
        if dialog.format_combo.itemData(row) == "png":
            assert not model.item(row).isEnabled()
            break
    else:  # pragma: no cover - the registry always contains png
        pytest.fail("png format was not offered")


def test_chart_only_format_stays_enabled_with_a_chart(qt_app):
    dialog = ExportDialog(has_chart=True)
    model = dialog.format_combo.model()

    for row in range(dialog.format_combo.count()):
        if dialog.format_combo.itemData(row) == "png":
            assert model.item(row).isEnabled()
            break


# Worker.


def run_worker(worker: ExportWorker) -> tuple[list[str], list[str]]:
    """Run the worker in the calling thread and collect its signals."""
    completed: list[str] = []
    failed: list[str] = []
    worker.completed.connect(completed.append)
    worker.failed.connect(failed.append)
    worker.run()
    return completed, failed


def test_worker_writes_a_pdf(qt_app, tmp_path):
    target = tmp_path / "report.pdf"
    worker = ExportWorker(
        target,
        ExportOptions("pdf", DEPTH_BRIEF, "ru"),
        make_result(),
        "transactions.csv",
    )

    completed, failed = run_worker(worker)

    assert failed == []
    assert completed == [str(target)]
    assert target.read_bytes()[:5] == b"%PDF-"


def test_worker_writes_a_detailed_workbook(qt_app, tmp_path):
    target = tmp_path / "report.xlsx"
    worker = ExportWorker(
        target,
        ExportOptions("xlsx", DEPTH_DETAILED, "en"),
        make_result(),
        "transactions.csv",
    )

    completed, failed = run_worker(worker)

    assert failed == []
    assert target.stat().st_size > 0


def test_worker_reports_a_missing_chart_instead_of_raising(qt_app, tmp_path):
    target = tmp_path / "report.png"
    worker = ExportWorker(
        target,
        ExportOptions("png", DEPTH_BRIEF, "ru"),
        make_result(with_chart=False),
        "transactions.csv",
    )

    completed, failed = run_worker(worker)

    assert completed == []
    assert len(failed) == 1
    assert "chart" in failed[0].lower()


def test_worker_reports_an_unwritable_path_instead_of_raising(qt_app, tmp_path):
    unwritable = tmp_path / "missing_folder" / "report.pdf"
    worker = ExportWorker(
        unwritable,
        ExportOptions("pdf", DEPTH_BRIEF, "ru"),
        make_result(),
        "transactions.csv",
    )

    completed, failed = run_worker(worker)

    assert completed == []
    assert len(failed) == 1


# Main window wiring.


def test_main_window_builds(qt_app):
    from app.ui.main_window import MainWindow

    window = MainWindow()

    assert window.windowTitle() == "Profilytix"
    window.close()


def test_export_button_appears_only_after_a_successful_analysis(qt_app):
    """The failure path is not exercised here: it opens a modal box that would block."""
    from app.ui.main_window import MainWindow

    window = MainWindow()
    assert window.export_button.isHidden()
    assert window.current_analysis_result is None

    window._handle_analysis_completed(make_result())

    assert not window.export_button.isHidden()
    assert window.current_analysis_result is not None
    window.close()


def test_loading_a_new_file_withdraws_the_previous_report_state(qt_app):
    from app.services.file_loader import LoadedFile
    from app.ui.main_window import MainWindow

    window = MainWindow()
    window._handle_analysis_completed(make_result())
    assert not window.export_button.isHidden()

    window._show_loaded_file(
        LoadedFile(
            path=Path("other.csv"),
            column_names=["a", "b"],
            preview_rows=[["1", "2"]],
            file_size_bytes=128,
            total_rows=1,
        )
    )

    assert window.export_button.isHidden()
    assert window.current_analysis_result is None
    window.close()


def test_worker_names_the_source_file_in_the_report(qt_app, tmp_path):
    target = tmp_path / "report.html"
    worker = ExportWorker(
        target,
        ExportOptions("html", DEPTH_BRIEF, "ru"),
        make_result(),
        "quarterly.csv",
    )

    run_worker(worker)

    assert "quarterly.csv" in target.read_text(encoding="utf-8")
