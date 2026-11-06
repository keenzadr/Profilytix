import os
import time
import threading
import subprocess
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def test_browser_reads_all_pages_without_loading_full_table(tmp_path):
    from app.ui.table_browser import TableBrowserDialog
    app = QApplication.instance() or QApplication([])
    path = tmp_path / 'table.csv'
    path.write_text('name,amount\n' + '\n'.join(f'row{i},{i}' for i in range(7)), encoding='utf-8')
    dialog = TableBrowserDialog(path, language='en', page_size=3)

    def ready():
        deadline = time.monotonic() + 5
        while dialog.worker_thread is not None and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(5)
        assert dialog.worker_thread is None

    ready()
    assert dialog.model.rowCount() == 3
    assert dialog.model.data(dialog.model.index(0, 0), Qt.ItemDataRole.DisplayRole) == 'row0'
    dialog.next_button.click()
    ready()
    assert dialog.model.data(dialog.model.index(0, 0)) == 'row3'
    dialog.next_button.click()
    ready()
    assert dialog.model.rowCount() == 1
    assert not dialog.next_button.isEnabled()
    assert dialog.previous_button.isEnabled()
    dialog.close()


def test_browser_waits_for_native_worker_exit_before_thread_deletion(tmp_path):
    """A delivered finished signal can precede native/Python thread cleanup."""
    # Isolate the native deadlock: restoring the unsafe deletion order should
    # fail with a timeout rather than leave the entire test suite stuck.
    script = ("import runpy,sys; from pathlib import Path; "
              "runpy.run_path(sys.argv[1])['_exercise_native_thread_cleanup'](Path(sys.argv[2]))")
    result = subprocess.run([sys.executable, '-c', script, str(Path(__file__).resolve()), str(tmp_path)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise_native_thread_cleanup(tmp_path):
    from app.ui import table_browser

    app = QApplication.instance() or QApplication([])
    path = tmp_path / 'cleanup.csv'
    path.write_text('amount\n1\n2\n', encoding='utf-8')
    release = threading.Event()
    cleanup_completed = threading.Event()
    reader_threads = []
    original_loader = table_browser.load_table_page

    def read_page(*args, **kwargs):
        reader_threads.append(threading.get_ident())
        assert release.wait(5)
        return original_loader(*args, **kwargs)

    table_browser.load_table_page = read_page
    dialog = table_browser.TableBrowserDialog(path, language='en', page_size=1)

    def finish_native_cleanup():
        # Represent Python thread-local/destructor work still running after
        # QThread.finished has queued its GUI handlers.
        time.sleep(0.05)
        cleanup_completed.set()

    dialog.worker_thread.finished.connect(finish_native_cleanup, Qt.ConnectionType.DirectConnection)
    release.set()
    deadline = time.monotonic() + 5
    while dialog.worker_thread is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert dialog.worker_thread is None
    assert cleanup_completed.is_set()
    assert reader_threads and reader_threads[0] != threading.get_ident()
    assert dialog.model.data(dialog.model.index(0, 0)) == '1'
    dialog.close()
