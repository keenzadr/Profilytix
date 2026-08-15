"""Print-ready report structures shared by every export format.

A `ReportModel` arrives at a writer already finished: numbers formatted, labels
in the target language, and sections dropped according to the requested depth.
A writer only lays the model out in its own format, which is why adding a
format costs one small file.

Any section may be absent. An analysis without a date column produces no chart
and no period table, and the report is still valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReportSection:
    """A titled list of label/value pairs."""

    title: str
    rows: tuple[tuple[str, str], ...]

    @property
    def is_empty(self) -> bool:
        """Return whether the section has nothing to show."""
        return not self.rows


@dataclass(frozen=True)
class ReportTable:
    """A titled table with a header row."""

    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def is_empty(self) -> bool:
        """Return whether the table has no data rows."""
        return not self.rows


@dataclass(frozen=True)
class ReportModel:
    """Everything one exported report contains."""

    title: str
    generated_at: datetime
    source: ReportSection
    summary: ReportSection
    insights: tuple[str, ...]
    categories: ReportTable | None
    anomalies: ReportTable | None
    periods: ReportTable | None
    chart_png: bytes | None
    language: str
    depth: str
    forecast: ReportTable | None = None

    @property
    def has_chart(self) -> bool:
        """Return whether a chart image was rendered for this report."""
        return bool(self.chart_png)

    def tables(self) -> tuple[ReportTable, ...]:
        """Return the present, non-empty tables in display order.

        Every writer walks this, so a table added here reaches all five formats.
        """
        candidates = (self.forecast, self.categories, self.anomalies, self.periods)
        return tuple(table for table in candidates if table is not None and not table.is_empty)
