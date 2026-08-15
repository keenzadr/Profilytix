"""Write the report chart as a standalone PNG image.

This format carries only the chart. Exporting it without a chart is a mistake
worth naming rather than a blank file worth writing.
"""

from __future__ import annotations

from pathlib import Path

from app.reports.model import ReportModel
from app.reports.writers.errors import ReportExportError


def write(model: ReportModel, path: Path) -> None:
    """Write the rendered chart image to disk."""
    if not model.has_chart:
        raise ReportExportError(
            "There is no chart to export. Select a date column and analyze the file "
            "again, or choose a format that does not need a chart."
        )

    Path(path).write_bytes(model.chart_png)
