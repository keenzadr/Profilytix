"""Dialog for choosing report format, depth, and language.

This lives apart from `main_window.py`, which is already long enough. The window
keeps the button, the worker, and the result handling; the choices live here.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.reports.builder import DEPTH_BRIEF, DEPTH_DETAILED
from app.reports.writers import WRITERS


DEPTH_CHOICES = (
    (DEPTH_BRIEF, "Brief", "Key metrics, insights, chart, top categories and anomalies."),
    (DEPTH_DETAILED, "Detailed", "Everything above plus all metrics, categories, anomalies, and a period table."),
)

LANGUAGE_CHOICES = (
    ("ru", "Russian"),
    ("en", "English"),
)

FORMAT_ORDER = ("pdf", "xlsx", "html", "png", "csv")


@dataclass(frozen=True)
class ExportOptions:
    """What the user chose in this dialog."""

    format_key: str
    depth: str
    language: str


class ExportDialog(QDialog):
    """Ask for the report format, depth, and language."""

    def __init__(
        self,
        parent: QWidget | None = None,
        has_chart: bool = True,
        initial: ExportOptions | None = None,
    ) -> None:
        super().__init__(parent)
        self.has_chart = has_chart
        self.setWindowTitle("Export Report")
        self.setMinimumWidth(420)
        self._setup_ui(initial or ExportOptions("pdf", DEPTH_BRIEF, "ru"))

    def _setup_ui(self, initial: ExportOptions) -> None:
        """Build the format, depth, and language controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        self.format_combo = QComboBox(self)
        for key in FORMAT_ORDER:
            report_format = WRITERS[key]
            text = report_format.label
            if report_format.needs_chart and not self.has_chart:
                text = f"{text} - needs a date column"
            self.format_combo.addItem(text, key)

        index = self.format_combo.findData(initial.format_key)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self._disable_formats_without_chart()
        form.addRow("Format:", self.format_combo)
        layout.addLayout(form)

        layout.addWidget(self._build_depth_group(initial.depth))
        layout.addWidget(self._build_language_group(initial.language))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_depth_group(self, selected_depth: str) -> QGroupBox:
        """Build the brief/detailed selector."""
        group = QGroupBox("Detail level", self)
        group_layout = QVBoxLayout(group)
        self.depth_buttons = QButtonGroup(self)

        for key, title, explanation in DEPTH_CHOICES:
            button = QRadioButton(title, group)
            button.setToolTip(explanation)
            button.setChecked(key == selected_depth)
            self.depth_buttons.addButton(button)
            button.setProperty("depth_key", key)
            group_layout.addWidget(button)

        return group

    def _build_language_group(self, selected_language: str) -> QGroupBox:
        """Build the report language selector."""
        group = QGroupBox("Report language", self)
        group_layout = QVBoxLayout(group)
        self.language_buttons = QButtonGroup(self)

        for key, title in LANGUAGE_CHOICES:
            button = QRadioButton(title, group)
            button.setChecked(key == selected_language)
            self.language_buttons.addButton(button)
            button.setProperty("language_key", key)
            group_layout.addWidget(button)

        return group

    def _disable_formats_without_chart(self) -> None:
        """Grey out chart-only formats when the analysis produced no chart."""
        if self.has_chart:
            return

        model = self.format_combo.model()
        for row in range(self.format_combo.count()):
            key = self.format_combo.itemData(row)
            if not WRITERS[key].needs_chart:
                continue
            item = model.item(row)
            if item is not None:
                item.setEnabled(False)
            if self.format_combo.currentIndex() == row:
                self.format_combo.setCurrentIndex(0)

    def options(self) -> ExportOptions:
        """Return the current selection."""
        return ExportOptions(
            format_key=self.format_combo.currentData() or "pdf",
            depth=self._checked_property(self.depth_buttons, "depth_key", DEPTH_BRIEF),
            language=self._checked_property(self.language_buttons, "language_key", "ru"),
        )

    @staticmethod
    def _checked_property(group: QButtonGroup, property_name: str, fallback: str) -> str:
        """Read a property off whichever radio button is checked."""
        button = group.checkedButton()
        if button is None:
            return fallback
        return button.property(property_name) or fallback
