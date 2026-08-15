"""Write a report as one self-contained HTML file.

Everything is inlined, including the chart as a base64 data URI, so the file
can be emailed or copied to a flash drive and still open correctly. This is a
document, not a web application: no scripts, no external requests.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

from app.reports.model import ReportModel, ReportSection, ReportTable
from app.reports.strings import label


STYLE = """
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  padding: 32px 24px 64px;
  max-width: 960px;
  font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1c2024;
  background: #ffffff;
  line-height: 1.5;
}
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #e3e6ea; }
.generated { color: #6b7280; font-size: 13px; margin: 0 0 8px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 7px 10px; text-align: left; border-bottom: 1px solid #eceff2; }
th { background: #f5f7f9; font-weight: 600; }
tr:last-child td { border-bottom: none; }
td.value, th.value { text-align: right; white-space: nowrap; }
.facts td:first-child { color: #4b5563; width: 45%; }
.facts td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
ul.insights { margin: 0; padding-left: 20px; }
ul.insights li { margin-bottom: 6px; }
.chart { margin-top: 12px; }
.chart img { width: 100%; height: auto; border: 1px solid #e3e6ea; border-radius: 6px; }
.scroll { overflow-x: auto; }
"""


def write(model: ReportModel, path: Path) -> None:
    """Write the report as a single HTML document."""
    Path(path).write_text(_render(model), encoding="utf-8")


def _render(model: ReportModel) -> str:
    """Build the whole document."""
    language = escape(model.language)
    parts = [
        "<!doctype html>",
        f'<html lang="{language}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(model.title)}</title>",
        f"<style>{STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(model.title)}</h1>",
        (
            f'<p class="generated">{escape(label(model.language, "generated_at"))}: '
            f"{model.generated_at:%d.%m.%Y %H:%M}</p>"
        ),
    ]

    parts.append(_render_section(model.source))
    parts.append(_render_section(model.summary))
    parts.append(_render_insights(model))
    parts.append(_render_chart(model))

    for table in model.tables():
        parts.append(_render_table(table))

    parts.extend(["</body>", "</html>"])
    return "\n".join(part for part in parts if part)


def _render_section(section: ReportSection) -> str:
    """Render a label/value block as a two-column table."""
    if section.is_empty:
        return ""

    rows = "\n".join(
        f"<tr><td>{escape(row_label)}</td><td>{escape(value)}</td></tr>"
        for row_label, value in section.rows
    )
    return (
        f"<h2>{escape(section.title)}</h2>"
        f'<table class="facts"><tbody>{rows}</tbody></table>'
    )


def _render_insights(model: ReportModel) -> str:
    """Render the insight sentences as a list."""
    if not model.insights:
        return ""

    items = "\n".join(f"<li>{escape(text)}</li>" for text in model.insights)
    return (
        f'<h2>{escape(label(model.language, "section_insights"))}</h2>'
        f'<ul class="insights">{items}</ul>'
    )


def _render_chart(model: ReportModel) -> str:
    """Embed the chart as a data URI so the file stays self-contained."""
    if not model.has_chart:
        return ""

    encoded = base64.b64encode(model.chart_png).decode("ascii")
    title = escape(label(model.language, "section_chart"))
    return (
        f"<h2>{title}</h2>"
        f'<div class="chart"><img alt="{title}" src="data:image/png;base64,{encoded}"></div>'
    )


def _render_table(table: ReportTable) -> str:
    """Render one data table."""
    headers = "".join(f"<th>{escape(header)}</th>" for header in table.headers)
    body_rows = []
    for row in table.rows:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        f"<h2>{escape(table.title)}</h2>"
        f'<div class="scroll"><table>'
        f"<thead><tr>{headers}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        f"</table></div>"
    )
