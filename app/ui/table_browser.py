"""A bounded Qt table model with background pagination for large local files."""

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout

from app.services.table_pages import TablePage, load_table_page


class PageTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = TablePage([], [], 0, False)

    def set_page(self, page):
        self.beginResetModel()
        self.page = page
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.page.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.page.column_names)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self.page.rows[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.page.column_names[section]
        return self.page.page * getattr(self, 'page_size', 1000) + section + 1


class TablePageWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path, page, page_size):
        super().__init__()
        self.path, self.page, self.page_size = path, page, page_size

    @Slot()
    def run(self):
        try:
            self.completed.emit(load_table_page(self.path, self.page, self.page_size))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class TableBrowserDialog(QDialog):
    def __init__(self, path, parent=None, language='ru', page_size=1000):
        super().__init__(parent)
        self.path = Path(path)
        self.language = language
        self.page_size = page_size
        self.worker_thread = None
        self.worker = None
        self._close_pending = False
        self.setWindowTitle(('Все строки — ' if language == 'ru' else 'All rows — ') + self.path.name)
        self.resize(1000, 650)
        layout = QVBoxLayout(self)
        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.table_view = QTableView()
        self.model = PageTableModel(self)
        self.model.page_size = page_size
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        layout.addWidget(self.table_view)
        buttons = QHBoxLayout()
        self.previous_button = QPushButton('Назад' if language == 'ru' else 'Previous')
        self.next_button = QPushButton('Далее' if language == 'ru' else 'Next')
        self.close_button = QPushButton('Закрыть' if language == 'ru' else 'Close')
        for button in (self.previous_button, self.next_button, self.close_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.previous_button.clicked.connect(lambda: self._load_page(self.model.page.page - 1))
        self.next_button.clicked.connect(lambda: self._load_page(self.model.page.page + 1))
        self.close_button.clicked.connect(self.reject)
        self._load_page(0)

    def _load_page(self, page):
        if self.worker_thread is not None:
            return
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.status_label.setText('Чтение страницы…' if self.language == 'ru' else 'Reading page…')
        self.worker_thread = QThread(self)
        self.worker = TablePageWorker(self.path, page, self.page_size)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.completed.connect(self._loaded)
        self.worker.failed.connect(self.status_label.setText)
        self.worker.finished.connect(self.worker_thread.quit, Qt.ConnectionType.DirectConnection)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self._finished)
        self.worker_thread.start()

    @Slot(object)
    def _loaded(self, page):
        self.model.set_page(page)
        start = page.page * self.page_size + 1 if page.rows else 0
        end = page.page * self.page_size + len(page.rows)
        text = f'Строки {start}–{end}. Страница {page.page + 1}.' if self.language == 'ru' else f'Rows {start}–{end}. Page {page.page + 1}.'
        self.status_label.setText(text)

    @Slot()
    def _finished(self):
        # finished is emitted before native/Python thread cleanup has ended.
        # Joining releases the GIL; deleting QThread directly from its queued
        # finished signal can block while the native thread still needs it.
        thread = self.worker_thread
        if thread is not None:
            thread.wait()
            thread.deleteLater()
        self.worker_thread = None
        self.worker = None
        self.previous_button.setEnabled(self.model.page.page > 0)
        self.next_button.setEnabled(self.model.page.has_next)
        if self._close_pending:
            super().reject()

    def reject(self):
        if self.worker_thread is not None:
            self._close_pending = True
            self.status_label.setText('Закрытие после чтения страницы…' if self.language == 'ru' else 'Closing after reading page…')
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker_thread is not None:
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)
