"""Small local analysis controls, separate from the main-window orchestration."""

from math import isfinite

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QLabel


TEXT = {
    'ru': {
        'balance':'Текущий остаток:', 'placeholder':'Необязательно, например 100 000',
        'method':'Поиск аномалий:', 'rules':'Правила IQR / Z-score',
        'forest':'Isolation Forest (ML)', 'profile':'Схема колонок:',
        'save':'Сохранить', 'apply':'Применить', 'delete':'Удалить',
        'hint':'Остаток и метод применяются при следующем анализе. Оценка запаса денег основана на средней дневной прибыли.',
        'invalid':'Введите конечный неотрицательный остаток денег или оставьте поле пустым.',
    },
    'en': {
        'balance':'Current cash:', 'placeholder':'Optional, e.g. 100 000',
        'method':'Anomaly method:', 'rules':'IQR / Z-score rules',
        'forest':'Isolation Forest (ML)', 'profile':'Column mapping:',
        'save':'Save', 'apply':'Apply', 'delete':'Delete',
        'hint':'Balance and method apply on the next analysis. Cash runway uses historical average daily profit.',
        'invalid':'Enter a finite nonnegative cash balance or leave the field empty.',
    },
}


class AnalysisOptionsWidget(QWidget):
    save_requested = Signal()
    apply_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent=None, language='ru'):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.balance_label = QLabel()
        self.balance_edit = QLineEdit()
        self.balance_edit.setMaxLength(50)
        form.addRow(self.balance_label, self.balance_edit)
        self.method_label = QLabel()
        self.method_combo = QComboBox()
        self.method_combo.addItem('', 'rules')
        self.method_combo.addItem('', 'isolation_forest')
        form.addRow(self.method_label, self.method_combo)
        self.profile_label = QLabel()
        self.profile_combo = QComboBox()
        form.addRow(self.profile_label, self.profile_combo)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.save_button = QPushButton()
        self.apply_button = QPushButton()
        self.delete_button = QPushButton()
        for button in (self.save_button, self.apply_button, self.delete_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet('color: #666666; font-size: 11px;')
        layout.addWidget(self.hint_label)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.apply_button.clicked.connect(lambda: self.apply_requested.emit(self.profile_combo.currentText()))
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.profile_combo.currentText()))
        self.profile_combo.currentIndexChanged.connect(self._update_profile_buttons)
        self.set_language(language)
        self._update_profile_buttons()

    def set_language(self, language):
        self.language = language if language in TEXT else 'ru'
        text = TEXT[self.language]
        self.balance_label.setText(text['balance'])
        self.balance_edit.setPlaceholderText(text['placeholder'])
        self.method_label.setText(text['method'])
        self.method_combo.setItemText(0, text['rules'])
        self.method_combo.setItemText(1, text['forest'])
        self.profile_label.setText(text['profile'])
        for button, key in [(self.save_button,'save'), (self.apply_button,'apply'), (self.delete_button,'delete')]:
            button.setText(text[key])
        self.hint_label.setText(text['hint'])

    def cash_balance(self):
        text = self.balance_edit.text().strip()
        if not text:
            return None
        try:
            value = float(text.replace(' ', '').replace('\u00a0', '').replace(',', '.'))
        except ValueError:
            raise ValueError(TEXT[self.language]['invalid']) from None
        if not isfinite(value) or value < 0:
            raise ValueError(TEXT[self.language]['invalid'])
        return value

    def anomaly_method(self):
        return self.method_combo.currentData() or 'rules'

    def set_profiles(self, names):
        current = self.profile_combo.currentText()
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if current in names:
            self.profile_combo.setCurrentText(current)
        self._update_profile_buttons()

    def _update_profile_buttons(self):
        available = self.profile_combo.count() > 0
        self.apply_button.setEnabled(available)
        self.delete_button.setEnabled(available)
