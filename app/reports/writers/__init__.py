"""Report writers, one per export format.

Every writer takes a finished `ReportModel` and a path. Adding a format means
adding one module and one registry entry; nothing else in the application needs
to know about it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.reports.model import ReportModel
from app.reports.writers import (
    csv_writer,
    html_writer,
    pdf_writer,
    png_writer,
    xlsx_writer,
)
from app.reports.writers.errors import ReportExportError


@dataclass(frozen=True)
class ReportFormat:
    """One export format the user can choose."""

    key: str
    label: str
    extension: str
    write: Callable[[ReportModel, Path], None]
    needs_chart: bool = False

    @property
    def file_filter(self) -> str:
        """Return a Qt file dialog filter for this format."""
        return f"{self.label} (*{self.extension})"


WRITERS: dict[str, ReportFormat] = {
    "pdf": ReportFormat("pdf", "PDF document", ".pdf", pdf_writer.write),
    "xlsx": ReportFormat("xlsx", "Excel workbook", ".xlsx", xlsx_writer.write),
    "html": ReportFormat("html", "HTML page", ".html", html_writer.write),
    "png": ReportFormat("png", "Chart image", ".png", png_writer.write, needs_chart=True),
    "csv": ReportFormat("csv", "CSV file", ".csv", csv_writer.write),
}


def write_report(model: ReportModel, path: Path, format_key: str) -> None:
    """Write a report in the requested format."""
    report_format = WRITERS.get(format_key)
    if report_format is None:
        raise ReportExportError(f"Unknown export format: {format_key}")

    report_format.write(model, Path(path))


__all__ = ["ReportExportError", "ReportFormat", "WRITERS", "write_report"]
