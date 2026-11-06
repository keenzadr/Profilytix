"""Disposable, native Qt design study; never imports or changes the production app.

Launch: python prototypes/ui_preview.py
Render: python prototypes/ui_preview.py --render-dir prototypes/previews
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QByteArray, Qt, QSize
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter


PAGES = ["Обзор", "Данные", "Категории", "Аномалии и прогноз", "Отчёты и справка"]
SLUGS = ["overview", "data", "categories", "anomalies_forecast", "reports_help"]
LIGHT = dict(bg="#F3F6F8", surface="#FFFFFF", text="#172B38", muted="#617581",
             border="#DFE7EB", accent="#087F78", tint="#E5F4F0", grid="#E8EEF1",
             expense="#6888AA", orange="#A76012", warning="#FFF4DF", sidebar="#142D3A")
DARK = dict(bg="#14212B", surface="#1C2E3A", text="#E8F0F4", muted="#A0B5C0",
            border="#344955", accent="#64D5C2", tint="#24473F", grid="#344955",
            expense="#91ADCF", orange="#F5C578", warning="#41372C", sidebar="#10212C")


def money(value: float, suffix: str = " ₽") -> str:
    return f"{value:,.0f}".replace(",", " ") + suffix


def allocate(total: int, weights: np.ndarray) -> np.ndarray:
    values = np.floor(total * weights / weights.sum()).astype(int)
    values[-1] += total - int(values.sum())
    return values


def demo_data() -> pd.DataFrame:
    """180 synthetic June transactions; all displayed totals derive from this table."""
    rows = []
    weights = np.array([1 + .14 * np.sin(i / 4) + .10 * (i % 7 == 5) for i in range(90)])
    revenues = allocate(1_248_000, weights)
    for i, value in enumerate(revenues):
        rows.append([pd.Timestamp(2026, 6, i // 3 + 1), f"Продажа · заказ {1201+i}",
                     "Продажи", int(value), 0])
    categories = [("Закупки", 336_000, 30), ("Оплата труда", 280_000, 20),
                  ("Аренда", 150_000, 10), ("Маркетинг", 63_000, 20), ("Прочее", 35_000, 10)]
    for category, total, count in categories:
        values = allocate(total, np.ones(count))
        if category == "Закупки":
            values = np.append(allocate(total - 126_000, np.ones(count - 1)), 126_000)
        for i, value in enumerate(values):
            day = (i * 3 + len(category)) % 30 + 1
            description = f"{category} · платёж {i+1:02d}"
            if category == "Закупки" and i == count - 1:
                day, description = 18, "Закупка оборудования"
            rows.append([pd.Timestamp(2026, 6, day), description, category, 0, int(value)])
    return pd.DataFrame(rows, columns=["date", "description", "category", "revenue", "expense"]).sort_values(
        ["date", "expense"], ascending=[False, False], ignore_index=True)


def icon(kind: int, color: str) -> QIcon:
    paths = [
        '<path d="M4 19V12h4v7m2 0V8h4v11m2 0V4h4v15"/>',
        '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10M15 10v10"/>',
        '<path d="M3 4h8l10 10-7 7L3 10Z"/><circle cx="7.5" cy="7.5" r="1"/>',
        '<path d="m3 17 5-6 4 3 8-10M15 4h5v5"/><path d="M3 21h18"/>',
        '<path d="M6 3h9l4 4v14H6Z M14 3v5h5M9 12h7M9 16h5"/>',
        '<path d="M20 14A9 9 0 0 1 10 4a9 9 0 1 0 10 10Z"/>',
        '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m4-12 4 4-4 4"/>',
    ]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths[kind]}</g></svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)


class Preview(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = demo_data()
        # Earlier months are intentionally synthetic aggregates, not hidden files.
        self.history = pd.DataFrame({"month": ["Апрель", "Май", "Июнь"],
                                     "revenue": [1_016_000, 1_108_000, int(self.data.revenue.sum())],
                                     "expense": [746_000, 781_000, int(self.data.expense.sum())]})
        self.dark = False
        self.collapsed = False
        self.palette_tokens = LIGHT
        self.current_page = 0
        self.scrolls: list[QScrollArea] = []
        self.setWindowTitle("Profilytix — макет интерфейса")
        self.setMinimumSize(960, 640)
        self.resize(1280, 850)
        self.build()

    def text(self, value, role="body", wrap=False):
        label = QLabel(value)
        label.setProperty("role", role)
        label.setWordWrap(wrap)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def button(self, text, *, disabled=False, primary=False):
        button = QPushButton(text)
        button.setEnabled(not disabled)
        button.setProperty("primary", primary)
        button.setCursor(Qt.CursorShape.PointingHandCursor if not disabled else Qt.CursorShape.ArrowCursor)
        button.setMinimumHeight(34)
        return button

    def card(self, title=None, subtitle=None):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(10)
        if title:
            layout.addWidget(self.text(title, "cardtitle"))
        if subtitle:
            layout.addWidget(self.text(subtitle, "muted", True))
        return frame, layout

    def build(self):
        self.palette_tokens = DARK if self.dark else LIGHT
        p = self.palette_tokens
        old = self.takeCentralWidget()
        if old:
            old.deleteLater()
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        self.sidebar = side
        side.setFixedWidth(72 if self.collapsed else 216)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(15, 28, 15, 22)
        sl.setSpacing(8)
        brand = self.text("Profilytix", "brand")
        brand.setContentsMargins(12, 0, 0, 0)
        sl.addWidget(brand)
        note = self.text("Финансы в ясной картине", "sidecaption")
        note.setContentsMargins(12, 0, 0, 30)
        sl.addWidget(note)
        self.sidebar_labels = [brand, note]
        self.collapse_button = self.button('')
        self.collapse_button.setIcon(icon(6, '#B7CCD4'))
        self.collapse_button.clicked.connect(self.toggle_sidebar)
        sl.addWidget(self.collapse_button)
        self.nav_buttons = []
        for index, title in enumerate(PAGES):
            button = self.button(title)
            button.setCheckable(True)
            button.setObjectName(f"nav_{SLUGS[index]}")
            button.setProperty("nav", True)
            button.setMinimumHeight(46)
            button.setIcon(icon(index, "#B7CCD4"))
            button.setIconSize(QSize(20, 20))
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            sl.addWidget(button)
            self.nav_buttons.append(button)
        sl.addStretch()
        for text, role in [('ДЕМОНСТРАЦИОННЫЙ НАБОР', 'sideeyebrow'), ('Магазин «Точка»', 'sidetitle'), ('Июнь 2026 · 180 операций', 'sidecaption')]:
            label = self.text(text, role)
            self.sidebar_labels.append(label)
            sl.addWidget(label)
        sl.addSpacing(12)
        label = self.text("Локальное приложение\nДанные остаются на устройстве", "sidecaption", True)
        self.sidebar_labels.append(label)
        sl.addWidget(label)
        self.theme_button = self.button('')
        self.theme_button.setObjectName('theme_toggle')
        self.theme_button.setIcon(icon(5, '#B7CCD4'))
        self.theme_button.clicked.connect(self.toggle_theme)
        sl.addWidget(self.theme_button)
        self.update_sidebar()
        layout.addWidget(side)
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(28, 15, 28, 15)
        tl.addWidget(self.text("РАБОЧЕЕ ПРОСТРАНСТВО", "eyebrow"))
        tl.addStretch()
        tl.addWidget(self.text("Макет · демонстрационные данные", "badge"))
        tl.addSpacing(10)
        ml.addWidget(top)
        self.stack = QStackedWidget()
        self.scrolls = []
        builders = [self.overview, self.data_page, self.categories, self.analysis, self.reports]
        for builder in builders:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            page = QWidget()
            page.setObjectName("page")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(28, 24, 28, 24)
            page_layout.setSpacing(18)
            builder(page_layout)
            page_layout.addStretch()
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            self.scrolls.append(scroll)
        ml.addWidget(self.stack)
        layout.addWidget(main, 1)
        self.setStyleSheet(self.styles(p))
        self.navigate(self.current_page)

    @staticmethod
    def styles(p):
        return f"""
        QWidget {{ font-family: 'Segoe UI'; font-size: 13px; color: {p['text']}; }}
        QMainWindow, QWidget#page, QScrollArea, QStackedWidget {{ background: {p['bg']}; }}
        QFrame#sidebar {{ background: {p['sidebar']}; }}
        QFrame#topbar {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}
        QFrame#card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 11px; }}
        QLabel {{ background: transparent; border: none; }}
        QLabel[role=brand] {{ font-size: 26px; font-weight: 700; color: #F4FAFB; }}
        QLabel[role=sidecaption] {{ font-size: 11px; color: #A4BDC9; line-height: 1.4; }}
        QLabel[role=sideeyebrow] {{ font-size: 9px; color: #87A8B7; font-weight: 600; }}
        QLabel[role=sidetitle] {{ color: #F4FAFB; font-weight: 600; }}
        QLabel[role=eyebrow] {{ font-size: 10px; color: {p['muted']}; font-weight: 600; }}
        QLabel[role=badge] {{ color: {p['accent']}; background: {p['tint']}; padding: 6px 10px; border-radius: 6px; font-size: 11px; }}
        QLabel[role=title] {{ font-size: 27px; font-weight: 650; }}
        QLabel[role=cardtitle] {{ font-size: 15px; font-weight: 600; }}
        QLabel[role=muted] {{ color: {p['muted']}; font-size: 12px; }}
        QLabel[role=metric] {{ font-size: 29px; font-weight: 650; }}
        QLabel[role=positive] {{ color: {p['accent']}; font-size: 12px; }}
        QLabel[role=warning] {{ color: {p['orange']}; background: {p['warning']}; padding: 12px; border-radius: 6px; }}
        QPushButton {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 12px; }}
        QPushButton:hover {{ background: {p['tint']}; border-color: {p['accent']}; }}
        QPushButton:focus {{ border: 2px solid {p['accent']}; }}
        QPushButton:disabled {{ color: {p['muted']}; background: {p['bg']}; border: 1px solid {p['border']}; }}
        QPushButton[primary=true] {{ background: {p['accent']}; color: {p['surface']}; border: 0; }}
        QPushButton[nav=true] {{ text-align: left; color: #B7CCD4; border: 0; background: transparent; padding: 10px 9px; font-size: 12px; }}
        QPushButton[nav=true]:hover {{ background: #254552; }}
        QPushButton[nav=true]:checked {{ background: #28544F; color: #E3FFF7; font-weight: 600; }}
        QComboBox {{ background: {p['surface']}; border: 1px solid {p['border']}; padding: 7px 12px; border-radius: 6px; min-height: 20px; }}
        QComboBox:disabled {{ color: {p['muted']}; background: {p['bg']}; }}
        QComboBox QAbstractItemView {{ background: {p['surface']}; color: {p['text']}; selection-background-color: {p['tint']}; }}
        QTableWidget {{ background: {p['surface']}; alternate-background-color: {p['bg']}; border: 0; gridline-color: {p['border']}; selection-background-color: {p['tint']}; selection-color: {p['text']}; }}
        QTableWidget::item {{ padding: 7px 10px; border-bottom: 1px solid {p['border']}; }}
        QHeaderView::section {{ background: {p['bg']}; color: {p['muted']}; border: 0; border-bottom: 1px solid {p['border']}; padding: 10px; font-size: 11px; font-weight: 600; }}
        QTableCornerButton::section {{ background: {p['bg']}; border: 0; }}
        QScrollBar:vertical {{ background: {p['bg']}; width: 9px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """

    def heading(self, layout, title, subtitle):
        heading = QVBoxLayout()
        heading.setSpacing(5)
        heading.addWidget(self.text(title, "title"))
        heading.addWidget(self.text(subtitle, "muted", True))
        layout.addLayout(heading)

    def scope(self, layout):
        row = QHBoxLayout()
        period = self.button("01 — 30 июня 2026", disabled=True)
        period.setToolTip("Период фиксирован для демонстрационного набора.")
        row.addWidget(period)
        row.addWidget(self.button("По дням", disabled=True))
        row.addStretch()
        row.addWidget(self.text("Все категории · RUB", "muted"))
        layout.addLayout(row)

    def metrics(self, layout, values):
        row = QHBoxLayout()
        row.setSpacing(14)
        for name, value, detail in values:
            frame, card_layout = self.card()
            card_layout.addWidget(self.text(name, "muted"))
            card_layout.addWidget(self.text(value, "metric"))
            card_layout.addWidget(self.text(detail, "muted" if name == "Расходы" else "positive", True))
            row.addWidget(frame, 1)
        layout.addLayout(row)

    def chart(self, height=246):
        p = self.palette_tokens
        fig = Figure(figsize=(8, 2.6), dpi=100, facecolor=p['surface'])
        ax = fig.add_subplot(111)
        ax.set_facecolor(p['surface'])
        daily = self.data.groupby("date")[["revenue", "expense"]].sum().sort_index()
        xs = np.arange(1, 31)
        ax.plot(xs, daily.revenue / 1000, color=p['accent'], linewidth=2.4, label="Выручка")
        ax.plot(xs, daily.expense / 1000, color=p['expense'], linewidth=1.8, label="Расходы")
        ax.fill_between(xs, daily.revenue / 1000, color=p['accent'], alpha=.07)
        ax.scatter([18], [daily.expense.iloc[17]/1000], color=p['orange'], s=30, zorder=5)
        ax.annotate("18 июн · закупка", (18, daily.expense.iloc[17]/1000), xytext=(21, 115),
                    fontsize=8, color=p['muted'], arrowprops=dict(arrowstyle="-", color=p['muted']))
        ax.set_xticks([1, 7, 14, 21, 30], ["1 июн", "7 июн", "14 июн", "21 июн", "30 июн"])
        ax.set_ylabel("тыс. ₽", fontsize=8, color=p['muted'])
        ax.set_ylim(0, 155)
        ax.set_xlim(1, 30)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}"))
        ax.grid(axis="y", color=p['grid'], linewidth=.8)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", colors=p['muted'], labelsize=8, length=0, pad=8)
        ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=p['text'], ncol=2)
        fig.subplots_adjust(left=.09, right=.95, top=.92, bottom=.18)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(height)
        canvas.setMaximumHeight(height)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return canvas

    def overview(self, layout):
        self.heading(layout, "Обзор финансов", "Магазин «Точка» · как прошёл июнь и на что обратить внимание")
        self.scope(layout)
        revenue, expense = self.data[["revenue", "expense"]].sum()
        self.metrics(layout, [("Выручка", money(revenue), "+12,6% к маю"),
                              ("Расходы", money(expense), "+10,6% к маю"),
                              ("Прибыль", money(revenue-expense), "+17,4% к маю · маржа 30,8%")])
        frame, cl = self.card("Движение выручки и расходов", "По дням · 30 дней в выбранном периоде")
        cl.addWidget(self.chart(height=216))
        layout.addWidget(frame)
        row = QHBoxLayout()
        row.setSpacing(14)
        frame, cl = self.card("Прибыль растёт быстрее выручки")
        cl.addWidget(self.text("В июне заработано на 57 000 ₽ больше, чем в мае. Маржа выросла с 29,5% до 30,8%.", "muted", True))
        row.addWidget(frame, 3)
        frame, cl = self.card("Нужно проверить")
        cl.addWidget(self.text("18 июня · закупка оборудования\n126 000 ₽ — необычно высокий расход.", "muted", True))
        row.addWidget(frame, 2)
        layout.addLayout(row)
        layout.addWidget(self.text("Основа сводки: 180 демонстрационных операций · сравнение с маем 2026", "muted"))

    def table(self, headers, rows, height=300, right_columns=()):
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)
        table.setWordWrap(False)
        for i, row in enumerate(rows):
            table.setRowHeight(i, 41)
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                if j in right_columns:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, j, item)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1 if len(headers) > 1 else 0, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(70)
        return table

    def data_page(self, layout):
        self.heading(layout, "Данные", "Понятная структура файла — основа достоверных показателей")
        frame, cl = self.card()
        row = QHBoxLayout()
        info = QVBoxLayout()
        info.addWidget(self.text("Магазин_июнь_2026.csv", "cardtitle"))
        info.addWidget(self.text("Синтетический набор · UTF-8 · 180 строк · 5 столбцов", "muted"))
        row.addLayout(info)
        row.addStretch()
        row.addWidget(self.button("Открыть файл · макет", disabled=True))
        cl.addLayout(row)
        layout.addWidget(frame)
        frame, cl = self.card("Соответствие столбцов", "В макете схема фиксирована. Исходные файлы не открываются и не изменяются.")
        row = QHBoxLayout()
        for title, value in [("Дата", "date"), ("Выручка", "revenue"), ("Расходы", "expense"), ("Категория", "category")]:
            col = QVBoxLayout()
            col.addWidget(self.text(title, "muted"))
            combo = QComboBox()
            combo.addItem(value)
            combo.setEnabled(False)
            col.addWidget(combo)
            row.addLayout(col, 1)
        cl.addLayout(row)
        layout.addWidget(frame)
        frame, cl = self.card("Предпросмотр операций", "Первые 100 из 180 строк · сортировка по дате, новые сверху")
        rows = [[r.date.strftime("%d.%m.%Y"), r.description, money(r.revenue) if r.revenue else "—",
                 money(r.expense) if r.expense else "—"] for r in self.data.head(100).itertuples()]
        cl.addWidget(self.table(["Дата", "Описание", "Выручка", "Расходы"], rows, 268, (2, 3)))
        cl.addWidget(self.text("Качество демонабора: 0 пропусков дат · 0 ошибок сумм · 0 исключённых строк", "positive", True))
        layout.addWidget(frame)

    def categories(self, layout):
        self.heading(layout, "Категории расходов", "Какие статьи формируют расходы бизнеса")
        self.scope(layout)
        frame, cl = self.card("Структура расходов", "864 000 ₽ за июнь · 90 расходных операций")
        totals = self.data.groupby("category").expense.sum().sort_values(ascending=False)
        colors = [self.palette_tokens['accent'], "#5F9EA8", "#7899BC", "#A5B6CE", "#C8D5DE"]
        for i, (name, value) in enumerate(totals[totals > 0].items()):
            row = QHBoxLayout()
            label = self.text(name)
            label.setFixedWidth(120)
            row.addWidget(label)
            bar = QFrame()
            bar.setFixedHeight(9)
            bar.setStyleSheet(f"background:{colors[i]}; border-radius:4px;")
            row.addWidget(bar, max(1, int(value / 1000)))
            row.addStretch(max(1, int((336000-value) / 1000)))
            val = self.text(f"{money(value)}    {value/864000:.1%}".replace(".", ","))
            val.setFixedWidth(175)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(val)
            cl.addLayout(row)
            cl.addSpacing(6)
        layout.addWidget(frame)
        frame, cl = self.card("Категоризация по описанию", "Визуальный пример существующего подхода с правилами RU / EN")
        cl.addWidget(self.table(["Фрагмент описания", "Категория", "Источник"], [
            ["Закупка оборудования", "Закупки", "Демонстрационный набор"],
            ["Аренда · платёж", "Аренда", "Демонстрационный набор"],
            ["Маркетинг · платёж", "Маркетинг", "Демонстрационный набор"],
        ], 167))
        cl.addWidget(self.text("Редактор пользовательских правил — предложение для будущего этапа.", "muted", True))
        cl.addWidget(self.button("Добавить правило · макет", disabled=True))
        layout.addWidget(frame)

    def analysis(self, layout):
        self.heading(layout, "Аномалии и прогноз", "Объяснимые сигналы и ориентир на следующий месяц")
        frame, cl = self.card()
        row = QHBoxLayout()
        row.addWidget(self.text("Метод поиска аномалий", "cardtitle"))
        row.addStretch()
        selector = QComboBox()
        selector.setObjectName("anomaly_method")
        selector.addItems(["IQR", "Z-score", "Isolation Forest"])
        selector.setMinimumWidth(190)
        row.addWidget(selector)
        cl.addLayout(row)
        explanation = self.text("", "muted", True)
        descriptions = ["IQR: значения за границами межквартильного размаха. Для анализа нужно от 4 периодов.",
                        "Z-score: отклонение от среднего в стандартных отклонениях. Для анализа нужно от 4 периодов.",
                        "Isolation Forest: поиск редких значений. Для анализа нужно от 8 периодов; проверяется каждый финансовый ряд."]
        def explain(index):
            explanation.setText(descriptions[index] + " Переключение меняет справку; результаты ниже — фиксированный пример.")
        selector.currentIndexChanged.connect(explain)
        explain(0)
        cl.addWidget(explanation)
        cl.addWidget(self.text("Пример сигнала · 18 июня · расходы 126 000 ₽ на закупку оборудования.\nАномалия — повод проверить операцию, а не доказательство ошибки.", "warning", True))
        layout.addWidget(frame)
        frame, cl = self.card("Ориентир на июль", "Демонстрационный расчёт · скользящее среднее за апрель–июнь · горизонт 30 дней")
        row = QHBoxLayout()
        forecast = self.history[["revenue", "expense"]].mean()
        forecast_profit = forecast.revenue - forecast.expense
        for title, value in [("Выручка", money(forecast.revenue)), ("Расходы", money(forecast.expense)), ("Прибыль", money(forecast_profit))]:
            col = QVBoxLayout()
            col.addWidget(self.text(title, "muted"))
            col.addWidget(self.text(value, "cardtitle"))
            row.addLayout(col, 1)
        cl.addLayout(row)
        cl.addWidget(self.text("Средние месячные значения за апрель, май и июнь. Это ориентир на основе истории; новые модели ML в макет не подключены.", "muted", True))
        layout.addWidget(frame)
        frame, cl = self.card("Денежный остаток")
        cl.addWidget(self.text(f"620 000 ₽ сейчас  →  {money(620_000 + forecast_profit)} через 30 дней", "cardtitle", True))
        cl.addWidget(self.text("Демонстрационный начальный остаток + прогнозируемая прибыль 327 000 ₽. Остаток учитывается отдельно от прибыли; будущие разовые платежи не учтены.", "muted", True))
        layout.addWidget(frame)

    def reports(self, layout):
        self.heading(layout, "Отчёты и справка", "Результаты анализа и пояснения рядом с рабочими инструментами")
        frame, cl = self.card("Отчёт за июнь 2026", "Магазин «Точка» · 01–30 июня · демонстрационный набор")
        cl.addWidget(self.text("В составе: финансовая сводка, график, категории, аномалии и прогноз.", "body", True))
        row = QHBoxLayout()
        for name in ["PDF", "XLSX", "HTML", "PNG", "CSV"]:
            row.addWidget(self.button(f"{name} · макет", disabled=True))
        cl.addLayout(row)
        cl.addWidget(self.text("Экспорт доступен в рабочем приложении. Этот прототип показывает расположение элементов и не создаёт отчёты.", "muted", True))
        layout.addWidget(frame)
        frame, cl = self.card("Как читать показатели")
        explanations = [
            ("Прибыль и денежный остаток", "Прибыль = выручка − расходы за выбранный период. Текущий денежный остаток задаётся отдельно."),
            ("Аномалии", "Сигнал указывает на необычное значение. Сначала проверьте исходную операцию и контекст бизнеса."),
            ("Прогноз", "Расчёт использует только прошлые периоды. Он не знает о будущих закупках, акциях и разовых платежах."),
            ("Ограничения макета", "Навигация, тема и справка методов работают. Загрузка, фильтры, правила и экспорт показаны как макет."),
        ]
        for title, detail in explanations:
            cl.addWidget(self.text(title, "cardtitle"))
            cl.addWidget(self.text(detail, "muted", True))
            cl.addSpacing(6)
        layout.addWidget(frame)

    def navigate(self, index):
        self.current_page = index
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def toggle_theme(self):
        self.dark = not self.dark
        self.build()

    def toggle_sidebar(self):
        self.collapsed = not self.collapsed
        self.update_sidebar()

    def update_sidebar(self):
        self.sidebar.setFixedWidth(72 if self.collapsed else 216)
        for label in self.sidebar_labels:
            label.setVisible(not self.collapsed)
        for title, button in zip(PAGES, self.nav_buttons):
            button.setText('' if self.collapsed else title)
        for button, title in [(self.collapse_button, 'Развернуть панель' if self.collapsed else 'Свернуть панель'),
                              (self.theme_button, 'Светлая тема' if self.dark else 'Тёмная тема')]:
            button.setText('' if self.collapsed else title)
            button.setToolTip(title)
            button.setAccessibleName(title)

    def evidence(self):
        scroll = self.scrolls[self.current_page]
        return {"page": SLUGS[self.current_page], "theme": "dark" if self.dark else "light",
                "window_logical": [self.width(), self.height()],
                "device_pixel_ratio": self.devicePixelRatioF(),
                "viewport_logical": [scroll.viewport().width(), scroll.viewport().height()],
                "horizontal_scroll_max": scroll.horizontalScrollBar().maximum(),
                "vertical_scroll_max": scroll.verticalScrollBar().maximum()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--size", default="1280x850", help="Logical window dimensions; default 1280x850")
    parser.add_argument("--scale", type=float, help="Set QT_SCALE_FACTOR before creating QApplication")
    parser.add_argument('--collapsed', action='store_true', help='Preview the compact icon-only sidebar')
    args = parser.parse_args()
    if args.scale:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    if args.render_dir:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication(sys.argv[:1])
    # The Windows offscreen platform does not discover system fonts itself.
    # Register installed fonts for faithful RU / EN screenshot rendering.
    if args.render_dir and sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuisl.ttf"):
            font_file = fonts / filename
            if font_file.exists():
                QFontDatabase.addApplicationFont(str(font_file))
    application.setFont(QFont("Segoe UI", 10))
    window = Preview()
    if args.collapsed:
        window.toggle_sidebar()
    width, height = map(int, args.size.lower().split("x"))
    window.resize(width, height)
    window.show()
    if args.render_dir:
        args.render_dir.mkdir(parents=True, exist_ok=True)
        evidence = []
        for page in range(len(PAGES)):
            window.navigate(page)
            application.processEvents()
            application.processEvents()
            filename = args.render_dir / f"{page+1:02d}_{SLUGS[page]}_light.png"
            if not window.grab().save(str(filename)):
                raise RuntimeError(f"Cannot save {filename}")
            evidence.append(window.evidence() | {"screenshot": filename.name})
        window.toggle_theme()
        window.navigate(0)
        application.processEvents()
        application.processEvents()
        filename = args.render_dir / "06_overview_dark.png"
        if not window.grab().save(str(filename)):
            raise RuntimeError(f"Cannot save {filename}")
        evidence.append(window.evidence() | {"screenshot": filename.name})
        manifest = {"synthetic_data": True, "rows": len(window.data),
                    "revenue": int(window.data.revenue.sum()), "expense": int(window.data.expense.sum()),
                    "captures": evidence}
        (args.render_dir / "render_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        window.close()
        return 0
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
