"""Native desktop navigation and styling; no application or analysis state lives here."""

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from app.ui.strings import tr


PAGES = ('Overview', 'Data', 'Categories', 'Anomalies and forecast', 'Reports and help')
LIGHT = dict(bg='#F3F6F8', surface='#FFFFFF', text='#172B38', muted='#617581',
             border='#DFE7EB', accent='#087F78', tint='#E5F4F0', grid='#E8EEF1',
             sidebar='#142D3A', warning='#9B5D11')
DARK = dict(bg='#14212B', surface='#1C2E3A', text='#E8F0F4', muted='#A0B5C0',
            border='#344955', accent='#64D5C2', tint='#24473F', grid='#344955',
            sidebar='#10212C', warning='#F5C578')


def icon(kind: str, color: str) -> QIcon:
    """Small vector icons scale with Qt's device pixel ratio."""
    paths = {
        'Overview': '<path d="m3 11 9-8 9 8M5 10v11h5v-7h4v7h5V10"/>',
        'Data': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10M15 10v10"/>',
        'Categories': '<path d="M3 4h8l10 10-7 7L3 10Z"/><circle cx="7.5" cy="7.5" r="1"/>',
        'Anomalies and forecast': '<path d="m3 17 5-6 4 3 8-10M15 4h5v5M3 21h18"/>',
        'Reports and help': '<path d="M6 3h9l4 4v14H6Z M14 3v5h5M9 12h7M9 16h5"/>',
        'collapse': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m7-12-4 4 4 4"/>',
        'expand': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m4-12 4 4-4 4"/>',
        'moon': '<path d="M20 14A9 9 0 0 1 10 4a9 9 0 1 0 10 10Z"/>',
        'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>',
    }
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths[kind]}</g></svg>'
    # QIcon's SVG engine renders at the target DPR instead of stretching a bitmap.
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (24, 48, 72):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


class Sidebar(QFrame):
    page_requested = Signal(int)
    collapsed_changed = Signal(bool)
    theme_requested = Signal()

    def __init__(self, language='ru', collapsed=False, theme='light', parent=None):
        super().__init__(parent)
        self.setObjectName('sidebar')
        self.language = language
        self.collapsed = collapsed
        self.theme = theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(8)
        self.brand = QLabel('Profilytix')
        self.brand.setObjectName('brand')
        layout.addWidget(self.brand)
        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName('sidebar_toggle')
        self.toggle_button.setMinimumHeight(40)
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button)
        layout.addSpacing(14)
        self.nav_buttons = []
        for i, title in enumerate(PAGES):
            button = QPushButton()
            button.setObjectName('nav_button')
            button.setCheckable(True)
            button.setMinimumHeight(46)
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda checked=False, index=i: self.select_page(index))
            self.nav_buttons.append(button)
            layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        layout.addStretch()
        self.local_label = QLabel()
        self.local_label.setWordWrap(True)
        self.local_label.setObjectName('sidebar_caption')
        layout.addWidget(self.local_label)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName('theme_toggle')
        self.theme_button.setMinimumHeight(42)
        self.theme_button.setIconSize(QSize(20, 20))
        self.theme_button.clicked.connect(self.theme_requested.emit)
        layout.addWidget(self.theme_button)
        self.refresh()

    def refresh(self):
        self.setFixedWidth(56 if self.collapsed else 216)
        self.setProperty('collapsed', self.collapsed)
        margin = 10 if self.collapsed else 12
        self.layout().setContentsMargins(margin, 18, margin, 14)
        for button, height in [(self.toggle_button, 40), (self.theme_button, 42),
                               *((button, 46) for button in self.nav_buttons)]:
            button.setFixedHeight(36 if self.collapsed else height)
            button.setIconSize(QSize(18, 18) if self.collapsed else QSize(20, 20))
            button.style().unpolish(button)
            button.style().polish(button)
        self.brand.setVisible(not self.collapsed)
        self.local_label.setVisible(not self.collapsed)
        self.local_label.setText(tr('Local app · data stays on this device', self.language))
        for title, button in zip(PAGES, self.nav_buttons):
            self._label(button, title)
            button.setIcon(icon(title, '#C2D4DE'))
        self._label(self.toggle_button, 'Expand sidebar' if self.collapsed else 'Collapse sidebar')
        self.toggle_button.setIcon(icon('expand' if self.collapsed else 'collapse', '#C2D4DE'))
        self._label(self.theme_button, 'Light theme' if self.theme == 'dark' else 'Dark theme')
        self.theme_button.setIcon(icon('sun' if self.theme == 'dark' else 'moon', '#C2D4DE'))

    def _label(self, button, title):
        text = tr(title, self.language)
        button.setText('' if self.collapsed else text)
        button.setToolTip(text)
        button.setAccessibleName(text)

    def toggle(self):
        self.collapsed = not self.collapsed
        self.refresh()
        self.collapsed_changed.emit(self.collapsed)

    def select_page(self, index):
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.page_requested.emit(index)

    def set_language(self, language):
        self.language = language
        self.refresh()

    def set_theme(self, theme):
        self.theme = theme
        self.refresh()


def stylesheet(theme):
    p = DARK if theme == 'dark' else LIGHT
    arrow = (Path(__file__).parent / 'assets' / f'chevron_{"dark" if theme == "dark" else "light"}.svg').as_posix()
    return f'''
        QWidget {{ color: {p['text']}; font-family: "Segoe UI"; font-size: 13px; }}
        QMainWindow, QDialog, QWidget#workspace, QWidget#page {{ background: {p['bg']}; }}
        QLabel {{ background: transparent; }}
        QLabel[tone="muted"] {{ color: {p['muted']}; }}
        QLabel[tone="warning"] {{ color: {p['warning']}; }}
        QLabel[role="heading"] {{ font-size: 25px; font-weight: 700; }}
        QLabel[role="card_title"] {{ font-size: 15px; font-weight: 600; }}
        QLabel[role="metric"] {{ font-size: 26px; font-weight: 700; }}
        QFrame[role="card"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; }}
        QFrame#sidebar {{ background: {p['sidebar']}; border: none; }}
        QFrame#sidebar QLabel {{ color: #C2D4DE; }}
        QFrame#sidebar QLabel#brand {{ color: #F0F7FA; font-size: 24px; font-weight: 700; padding: 4px; }}
        QFrame#sidebar QLabel#sidebar_caption {{ color: #A0B5C0; font-size: 11px; padding: 5px; }}
        QPushButton {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 9px 12px; }}
        QPushButton:hover {{ background: {p['tint']}; border-color: {p['accent']}; }}
        QPushButton:focus {{ border: 2px solid {p['accent']}; }}
        QPushButton:disabled {{ color: {p['muted']}; background: {p['bg']}; }}
        QPushButton[primary="true"] {{ background: {p['accent']}; color: {p['bg']}; font-weight: 600; }}
        QPushButton[primary="true"]:disabled {{ background: {p['border']}; color: {p['muted']}; }}
        QFrame#sidebar QPushButton {{ background: transparent; color: #C2D4DE; border: 1px solid transparent; padding: 8px 4px; text-align: left; }}
        QFrame#sidebar QPushButton:hover, QFrame#sidebar QPushButton:checked {{ background: #28534F; color: #E8FFFA; }}
        QFrame#sidebar QPushButton:focus {{ border: 1px solid #64D5C2; }}
        QFrame#sidebar[collapsed="true"] QPushButton {{ padding: 0; text-align: center; }}
        QComboBox, QLineEdit {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 7px 10px; selection-background-color: {p['accent']}; }}
        QComboBox {{ padding-right: 32px; min-height: 18px; combobox-popup: 0; }}
        QComboBox:hover, QComboBox:focus {{ border-color: {p['accent']}; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; background: transparent; }}
        QComboBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
        QComboBox QAbstractItemView {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 4px; outline: none; selection-background-color: {p['tint']}; selection-color: {p['text']}; }}
        QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 3px 10px; border: none; }}
        QComboBox QAbstractItemView::item:selected {{ background: {p['tint']}; color: {p['text']}; border-radius: 4px; }}
        QComboBox:disabled, QLineEdit:disabled {{ color: {p['muted']}; }}
        QTableView {{ background: {p['surface']}; alternate-background-color: {p['bg']}; gridline-color: {p['border']}; border: none; selection-background-color: {p['tint']}; selection-color: {p['text']}; }}
        QHeaderView::section {{ background: {p['bg']}; color: {p['muted']}; padding: 9px; border: none; border-bottom: 1px solid {p['border']}; }}
        QScrollArea {{ border: none; background: {p['bg']}; }}
        QScrollArea > QWidget > QWidget {{ background: {p['bg']}; }}
        QProgressBar {{ background: {p['border']}; border: none; border-radius: 3px; max-height: 6px; }}
        QProgressBar::chunk {{ background: {p['accent']}; border-radius: 3px; }}
        QToolTip {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 5px; }}
    '''


def style_chart(figure, axes, theme):
    """Style desktop figures only, preserving values, artists, exports and hover."""
    p = DARK if theme == 'dark' else LIGHT
    figure.set_facecolor(p['surface'])
    axes.set_facecolor(p['surface'])
    axes.tick_params(colors=p['muted'])
    for label in (axes.title, axes.xaxis.label, axes.yaxis.label,
                  axes.xaxis.get_offset_text(), axes.yaxis.get_offset_text()):
        label.set_color(p['muted'])
    for spine in axes.spines.values():
        spine.set_color(p['border'])
    for line in (*axes.get_xgridlines(), *axes.get_ygridlines()):
        line.set_color(p['grid'])
    legend = axes.get_legend()
    if legend:
        legend.get_frame().set_facecolor(p['surface'])
        legend.get_frame().set_edgecolor(p['border'])
        for text in legend.get_texts():
            text.set_color(p['text'])
