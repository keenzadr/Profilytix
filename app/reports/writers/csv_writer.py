"""Write a report as a flat CSV file.

Uses a semicolon delimiter and a UTF-8 BOM, which is the combination Excel on a
Russian Windows opens correctly by double-click. Comma-delimited UTF-8 without
a BOM shows Cyrillic as mojibake there, which defeats the point of exporting.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.reports.model import ReportModel, ReportSection, ReportTable
from app.reports.strings import label


DELIMITER = ";"
ENCODING = "utf-8-sig"


def write(model: ReportModel, path: Path) -> None:
    """Write the whole report to one CSV file."""
    with Path(path).open("w", encoding=ENCODING, newline="") as handle:
        writer = csv.writer(handle, delimiter=DELIMITER)

        writer.writerow([model.title])
        writer.writerow(
            [
                label(model.language, "generated_at"),
                f"{model.generated_at:%d.%m.%Y %H:%M}",
            ]
        )

        _write_section(writer, model.source)
        _write_section(writer, model.summary)
        _write_insights(writer, model)

        for table in model.tables():
            _write_table(writer, table)


def _write_section(writer: object, section: ReportSection) -> None:
    """Write one label/value block."""
    if section.is_empty:
        return

    writer.writerow([])
    writer.writerow([section.title])
    for row_label, value in section.rows:
        writer.writerow([row_label, value])


def _write_insights(writer: object, model: ReportModel) -> None:
    """Write the insight sentences, one per line."""
    if not model.insights:
        return

    writer.writerow([])
    writer.writerow([label(model.language, "section_insights")])
    for text in model.insights:
        writer.writerow([text])


def _write_table(writer: object, table: ReportTable) -> None:
    """Write one table with its header row."""
    writer.writerow([])
    writer.writerow([table.title])
    writer.writerow(list(table.headers))
    for row in table.rows:
        writer.writerow(list(row))
