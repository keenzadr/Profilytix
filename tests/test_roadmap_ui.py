import os
import time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.analytics.column_detection import detect_columns
from app.analytics.metrics import SelectedColumns
from app.services.file_loader import load_file_preview
from app.ui import main_window


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def path(tmp_path):
    path = tmp_path / 'bank.csv'
    path.write_text('Date,Amount,Description\n' + '\n'.join(f'2026-01-{day:02d},-10,Rent' for day in range(1, 11)), encoding='utf-8')
    return path


def test_worker_emits_real_progress_and_enriched_result(app, path):
    worker = main_window.AnalysisWorker(str(path), SelectedColumns(date='Date', amount='Amount', description='Description'), 'day', 'monday', cash_balance=200, anomaly_method='isolation_forest')
    results, errors, progress = [], [], []
    worker.completed.connect(results.append)
    worker.failed.connect(errors.append)
    worker.progress_changed.connect(lambda *args: progress.append(args))
    worker.run()
    assert errors == []
    assert results[0].metrics.derived_categories[0].name == 'Rent'
    assert results[0].cash_balance == 200
    assert progress[-1][0] == progress[-1][1] == path.stat().st_size


def test_worker_cancels_without_publishing_partial_results(app, path):
    worker = main_window.AnalysisWorker(str(path), SelectedColumns(amount='Amount'), 'day', 'monday')
    results, errors, cancelled = [], [], []
    worker.completed.connect(results.append)
    worker.failed.connect(errors.append)
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.progress_changed.connect(lambda *args: worker.cancel())
    worker.run()
    assert cancelled == [True]
    assert results == errors == []


def test_description_is_explicitly_selectable(app):
    columns = ['Amount', 'Description']
    dialog = main_window.ColumnSelectionDialog(columns, detect_columns(columns, [['-10', 'Rent']]), SelectedColumns(amount='Amount'))
    combo = dialog.role_rows['description'][0][1]
    combo.setCurrentIndex(combo.findData('Description'))
    assert dialog.selected_columns().description == ('Description',)
    dialog.close()


def test_window_analysis_profiles_forecast_and_cash(app, path, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / 'ui.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, 'QSettings', lambda *args: settings)
    window = main_window.MainWindow()
    window._show_loaded_file(load_file_preview(path))
    selected = SelectedColumns(date='Date', amount='Amount', description='Description')
    window.selected_columns = selected
    window.analysis_options.balance_edit.setText('200')
    window._start_analysis()
    deadline = time.monotonic() + 10
    while window.analysis_thread is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert window.analysis_thread is None
    assert window.current_analysis_result.cash_balance == 200
    assert '20' in window.forecast_label.text()
    assert 'Аренда' in window.current_metrics_text
    window.mapping_profiles.save('Bank', selected)
    window._apply_mapping_profile('Bank')
    assert window.selected_columns == selected
    assert window.current_analysis_result is None
    assert window.export_button.isHidden()
    window.close()


def test_closing_during_analysis_waits_for_native_thread_cleanup(app, path, tmp_path, monkeypatch):
    # A regression here deadlocks inside Qt, so bound it at the process level.
    if os.environ.get('PROFILYTIX_NATIVE_CLEANUP_TEST') != '1':
        import subprocess
        import sys
        environment = {**os.environ, 'PROFILYTIX_NATIVE_CLEANUP_TEST':'1', 'PYTHONIOENCODING':'utf-8'}
        result = subprocess.run([sys.executable, '-m', 'pytest', __file__ + '::test_closing_during_analysis_waits_for_native_thread_cleanup', '-q', '--basetemp', str(tmp_path / 'child')], env=environment, capture_output=True, encoding='utf-8', errors='replace', timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        return
    from threading import Event
    from PySide6.QtCore import Qt
    settings = QSettings(str(tmp_path / 'close.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, 'QSettings', lambda *args: settings)
    original_load = main_window.load_selected_columns
    entered, release = Event(), Event()
    def slow_load(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original_load(*args, **kwargs)
    monkeypatch.setattr(main_window, 'load_selected_columns', slow_load)
    window = main_window.MainWindow()
    window._show_loaded_file(load_file_preview(path))
    window.selected_columns = SelectedColumns(amount='Amount')
    window.show()
    window._start_analysis()
    assert entered.wait(3)
    window.analysis_thread.finished.connect(lambda: time.sleep(0.05), Qt.ConnectionType.DirectConnection)
    window.close()
    assert window._close_pending
    release.set()
    deadline = time.monotonic() + 5
    while window.analysis_thread is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert window.analysis_thread is None
    app.processEvents()
    assert not window.isVisible()
