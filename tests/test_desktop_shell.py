"""Desktop navigation must preserve real file/analysis state and worker controls."""

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.analytics.metrics import SelectedColumns
from app.services.file_loader import load_file_preview
from app.ui import main_window


@pytest.fixture
def window(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'shell.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, 'QSettings', lambda *args: settings)
    widget = main_window.MainWindow(language='ru')
    widget.show()
    application.processEvents()
    yield widget
    widget.close()
    application.processEvents()


def load_result(window, tmp_path):
    path = tmp_path / 'shop.csv'
    path.write_text('Date,Revenue,Expenses,Category,Description\n' + '\n'.join(
        f'2026-06-{day:02d},100,40,Raw category,Rent' for day in range(1, 11)), encoding='utf-8')
    window._show_loaded_file(load_file_preview(path))
    window.selected_columns = SelectedColumns(date='Date', revenue='Revenue', expense='Expenses',
                                             category='Category', description='Description')
    results = []
    worker = main_window.AnalysisWorker(str(path), window.selected_columns, 'day', 'monday')
    worker.completed.connect(results.append)
    worker.run()
    assert results
    window._handle_analysis_completed(results[0])
    return results[0]


def test_navigation_collapse_theme_and_language_preserve_loaded_analysis(window, tmp_path):
    result = load_result(window, tmp_path)
    table = window.table_widget
    table.selectRow(2)
    window.analysis_options.balance_edit.setText('500')
    assert window.page_stack.count() == 5
    assert not window.sidebar.collapsed
    for i, button in enumerate(window.sidebar.nav_buttons):
        button.click()
        assert window.page_stack.currentIndex() == i
        assert sum(b.isChecked() for b in window.sidebar.nav_buttons) == 1
    wide = window.sidebar.width()
    window.sidebar.toggle_button.click()
    assert window.sidebar.collapsed
    assert window.sidebar.width() < wide
    assert all(not b.text() and b.toolTip() and b.accessibleName() for b in window.sidebar.nav_buttons)
    window.sidebar.theme_button.click()
    assert window.theme == 'dark'
    assert window.page_stack.currentIndex() == 4
    window.set_language('en')
    assert window.sidebar.nav_buttons[0].toolTip() == 'Overview'
    assert window.current_analysis_result is result
    assert window.table_widget is table
    assert table.currentRow() == 2
    assert window.analysis_options.cash_balance() == 500
    assert window.configure_columns_button.isVisibleTo(window.page_stack.widget(1))
    assert window.metric_values['revenue'].text() == '1 000.00'
    assert window.metric_values['profit'].text() == '600.00'
    assert window.category_table.item(0, 0).text() == 'Raw category'
    assert window.derived_category_table.item(0, 0).text() == 'Rent'
    window.sidebar.toggle_button.click()
    assert window.sidebar.nav_buttons[0].text() == 'Overview'
    assert window.page_stack.currentIndex() == 4


def test_sidebar_preferences_are_restored_without_changing_language(window):
    window.sidebar.toggle_button.click()
    window.sidebar.theme_button.click()
    window.set_language('en')
    second = main_window.MainWindow()
    try:
        assert second.sidebar.collapsed
        assert second.theme == 'dark'
        assert second.language == 'en'
        assert second.sidebar.nav_buttons[0].toolTip() == 'Overview'
        assert second.sidebar.theme_button.toolTip() == 'Light theme'
    finally:
        second.close()


def test_navigation_keyboard_and_bottom_theme_placement(window):
    sidebar = window.sidebar
    sidebar.nav_buttons[0].setFocus()
    QTest.keyClick(sidebar.nav_buttons[0], Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is sidebar.nav_buttons[1]
    QTest.keyClick(sidebar.nav_buttons[1], Qt.Key.Key_Space)
    assert window.page_stack.currentIndex() == 1
    assert sidebar.theme_button.parentWidget() is sidebar
    assert sidebar.theme_button.y() > sidebar.nav_buttons[-1].y()


def test_progress_and_cancel_remain_accessible_on_every_page(window):
    window._set_analysis_state(True)
    try:
        for button in window.sidebar.nav_buttons:
            button.click()
            QApplication.processEvents()
            assert window.progress_bar.isVisible()
            assert window.cancel_button.isVisible()
            assert not window.analysis_options.profile_widget.isEnabled()
            assert not window.load_button.isEnabled()
    finally:
        window._set_analysis_state(False)


def test_profile_change_and_new_file_clear_all_old_visual_results(window, tmp_path):
    load_result(window, tmp_path)
    assert window.category_table.rowCount() == 1
    window._invalidate_analysis()
    assert window.metric_values['profit'].text() == '—'
    assert window.category_table.rowCount() == 0
    assert window.derived_category_table.rowCount() == 0
    assert window.current_analysis_result is None
    assert window.export_button.isHidden()
    load_result(window, tmp_path)
    path = tmp_path / 'other.csv'
    path.write_text('Amount\n1', encoding='utf-8')
    window._show_loaded_file(load_file_preview(path))
    assert window.metric_values['revenue'].text() == '—'
    assert window.category_table.rowCount() == 0
    assert window.export_button.isHidden()


def test_dark_chart_and_fullscreen_use_ui_theme_without_mutating_series(window, tmp_path):
    result = load_result(window, tmp_path)
    window.sidebar.theme_button.click()
    assert window.chart_axes.get_facecolor()[0] < 0.2
    assert window.current_time_series is result.time_series
    dialog = main_window.ChartDialog(result.time_series, parent=window, language='ru')
    try:
        assert dialog.axes.get_facecolor()[0] < 0.2
    finally:
        dialog.close()
    window.sidebar.theme_button.click()
    assert window.chart_axes.get_facecolor()[0] > 0.9


def test_preview_opens_data_for_mapping_review_without_running_analysis(window, tmp_path):
    path = tmp_path / 'review.csv'
    path.write_text('Revenue\n500', encoding='utf-8')
    window._handle_preview_loaded(load_file_preview(path))
    assert window.page_stack.currentIndex() == 1
    assert window.sidebar.nav_buttons[1].isChecked()
    assert window.current_analysis_result is None
    assert window.current_loaded_file.path == path


def test_saved_mappings_are_locked_during_export(window, tmp_path):
    load_result(window, tmp_path)
    window.mapping_profiles.save('Shop', window.selected_columns)
    window.analysis_options.set_profiles(['Shop'])
    window._set_export_state(True)
    try:
        assert not window.analysis_options.profile_widget.isEnabled()
        assert not window.analysis_options.apply_button.isEnabled()
    finally:
        window._set_export_state(False)
    assert window.analysis_options.apply_button.isEnabled()


def test_dark_theme_covers_the_all_rows_table_view(window, tmp_path):
    from time import monotonic
    from PySide6.QtGui import QPalette
    from app.ui.table_browser import TableBrowserDialog
    load_result(window, tmp_path)
    window.sidebar.theme_button.click()
    dialog = TableBrowserDialog(window.current_loaded_file.path, window)
    dialog.show()
    deadline = monotonic() + 5
    while dialog.worker_thread is not None and monotonic() < deadline:
        QApplication.processEvents()
        QTest.qWait(5)
    try:
        assert dialog.worker_thread is None
        assert dialog.table_view.palette().color(QPalette.ColorRole.Base).lightness() < 100
        assert dialog.table_view.palette().color(QPalette.ColorRole.Text).lightness() > 180
    finally:
        dialog.close()


def test_category_panel_bounds_large_results_without_losing_full_report_data(window, tmp_path):
    from dataclasses import replace
    from app.analytics.metrics import CategoryMetric
    result = load_result(window, tmp_path)
    categories = tuple(CategoryMetric(str(i), 1, 10, 5, 5) for i in range(150))
    result = replace(result, metrics=replace(result.metrics, top_categories=categories))
    window._handle_analysis_completed(result)
    assert window.category_table.rowCount() == 100
    assert '150' in window.category_summary.text()
    assert len(window.current_analysis_result.metrics.top_categories) == 150
