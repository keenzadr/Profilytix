"""Offline dependency/resource smoke test executed inside the frozen application."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys


def run_smoke_test(output: Path) -> None:
    """Exercise Qt, binary imports, the bundled example, Agg and all five exports."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import pandas as pd
    import polars as pl
    import xlrd
    from openpyxl import load_workbook
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from sklearn.ensemble import IsolationForest

    from app.analytics.time_series import TimeSeriesPoint, TimeSeriesResult
    from app.reports.chart_image import render_chart_png
    from app.reports.model import ReportModel, ReportSection
    from app.reports.writers import WRITERS, write_report
    from app.ui.main_window import MainWindow

    output.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        sample = Path(sys._MEIPASS) / "demo" / "demo_finances.csv"
    else:
        from generate_demo import generate_demo

        sample = generate_demo(output / "demo_finances.csv")
    data = pd.read_csv(sample, sep=";", encoding="utf-8-sig")
    if len(data) != 180 or pl.read_csv(sample, separator=";").height != 180:
        raise RuntimeError("Bundled demo did not load through pandas and Polars")
    IsolationForest(random_state=42, n_estimators=8).fit_predict(data[["Доход", "Расход"]])
    application = QApplication.instance() or QApplication([])
    # Release verification must not touch an existing user's language/mappings.
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    window = MainWindow()
    window.show()
    application.processEvents()
    window.close()
    points = [
        TimeSeriesPoint(datetime(2026, 1, day), day * 100.0, day * 30.0, day * 70.0, day * 70.0)
        for day in range(1, 6)
    ]
    chart = render_chart_png(TimeSeriesResult(points, "day", "monday", ("revenue", "profit")), None)
    model = ReportModel(
        title="Проверка отчёта Profilytix",
        generated_at=datetime(2026, 1, 5),
        source=ReportSection("Источник", (("Файл", sample.name),)),
        summary=ReportSection("Показатели", (("Выручка", "1 500"), ("Прибыль", "1 050"))),
        insights=("Кириллица: выручка и расходы.",),
        categories=None,
        anomalies=None,
        periods=None,
        chart_png=chart,
        language="ru",
        depth="summary",
    )
    exports = {}
    for key, writer in WRITERS.items():
        target = output / f"smoke_report{writer.extension}"
        write_report(model, target, key)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f"Empty export: {key}")
        exports[key] = target.stat().st_size
    if (output / "smoke_report.pdf").read_bytes()[:5] != b"%PDF-":
        raise RuntimeError("Invalid PDF export")
    workbook = load_workbook(output / "smoke_report.xlsx")
    workbook.close()
    (output / "smoke-results.json").write_text(
        json.dumps({"status": "passed", "frozen": bool(getattr(sys, "frozen", False)),
                    "demo_rows": len(data), "exports": exports, "xlrd": xlrd.__version__}, indent=2),
        encoding="utf-8",
    )
