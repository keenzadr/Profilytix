"""Write a report as a PDF document.

ReportLab's built-in fonts cannot render Cyrillic, and category names in real
data are Cyrillic no matter which language the report is written in. DejaVuSans
ships inside matplotlib, which is already a dependency, so the font is taken
from there rather than vendored into the repository or downloaded.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports.model import ReportModel, ReportSection, ReportTable
from app.reports.strings import label
from app.reports.writers.errors import ReportExportError

try:
    from io import BytesIO

    import matplotlib
except ImportError:  # pragma: no cover - matplotlib is a hard dependency
    matplotlib = None


FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

PAGE_MARGIN = 18 * mm
HEADER_BACKGROUND = colors.HexColor("#f0f3f6")
GRID_COLOR = colors.HexColor("#d8dde3")
MUTED_COLOR = colors.HexColor("#5b6470")

# At this many columns a table stops leading with a name and starts leading
# with a date, and the cells need to be tighter to avoid wrapping mid-word.
WIDE_TABLE_COLUMNS = 5

_fonts_registered = False


def write(model: ReportModel, path: Path) -> None:
    """Write the report as a paginated PDF."""
    _register_fonts()
    styles = _build_styles()

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title=model.title,
    )
    available_width = document.width

    story = [
        Paragraph(model.title, styles["title"]),
        Paragraph(
            f'{label(model.language, "generated_at")}: {model.generated_at:%d.%m.%Y %H:%M}',
            styles["muted"],
        ),
        Spacer(1, 8),
    ]

    story.extend(_render_section(model.source, styles, available_width))
    story.extend(_render_section(model.summary, styles, available_width))
    story.extend(_render_insights(model, styles))
    story.extend(_render_chart(model, styles, available_width))

    for table in model.tables():
        story.extend(_render_table(table, styles, available_width))

    document.build(story)


def _register_fonts() -> None:
    """Register DejaVuSans from matplotlib so Cyrillic renders."""
    global _fonts_registered
    if _fonts_registered:
        return

    if matplotlib is None:
        raise ReportExportError(
            "matplotlib is required for PDF export because the report font is taken "
            "from it. Install matplotlib and try again."
        )

    font_directory = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    regular = font_directory / "DejaVuSans.ttf"
    bold = font_directory / "DejaVuSans-Bold.ttf"

    missing = [str(path) for path in (regular, bold) if not path.exists()]
    if missing:
        raise ReportExportError(
            "The DejaVuSans font shipped with matplotlib was not found, so Cyrillic "
            f'text could not be rendered. Expected it at: {", ".join(missing)}'
        )

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
    pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD)
    _fonts_registered = True


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build the paragraph styles used across the document."""
    body = ParagraphStyle(
        "body",
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName=FONT_BOLD, fontSize=18, leading=22
        ),
        "heading": ParagraphStyle(
            "heading",
            parent=body,
            fontName=FONT_BOLD,
            fontSize=12,
            leading=16,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "muted": ParagraphStyle("muted", parent=body, textColor=MUTED_COLOR, fontSize=8.5),
        "body": body,
        "cell": body,
        "cell_header": ParagraphStyle("cell_header", parent=body, fontName=FONT_BOLD),
        "cell_compact": ParagraphStyle(
            "cell_compact", parent=body, fontSize=8, leading=10
        ),
        "cell_header_compact": ParagraphStyle(
            "cell_header_compact",
            parent=body,
            fontName=FONT_BOLD,
            fontSize=8,
            leading=10,
        ),
    }


def _render_section(
    section: ReportSection,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> list[object]:
    """Render a label/value block as a two-column table."""
    if section.is_empty:
        return []

    rows = [
        [
            Paragraph(row_label, styles["cell"]),
            Paragraph(value, styles["cell"]),
        ]
        for row_label, value in section.rows
    ]
    table = Table(rows, colWidths=[width * 0.55, width * 0.45], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [Paragraph(section.title, styles["heading"]), table]


def _render_insights(model: ReportModel, styles: dict[str, ParagraphStyle]) -> list[object]:
    """Render the insight sentences as a bulleted list."""
    if not model.insights:
        return []

    items = [
        ListItem(Paragraph(text, styles["body"]), leftIndent=12)
        for text in model.insights
    ]
    return [
        Paragraph(label(model.language, "section_insights"), styles["heading"]),
        ListFlowable(items, bulletType="bullet", start="•", leftIndent=12),
    ]


def _render_chart(
    model: ReportModel,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> list[object]:
    """Place the chart image scaled to the page width."""
    if not model.has_chart:
        return []

    reader = ImageReader(BytesIO(model.chart_png))
    source_width, source_height = reader.getSize()
    height = width * source_height / source_width

    image = Image(BytesIO(model.chart_png), width=width, height=height)
    image.hAlign = "LEFT"
    return [Paragraph(label(model.language, "section_chart"), styles["heading"]), image]


def _render_table(
    table: ReportTable,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> list[object]:
    """Render one data table with a header that repeats across pages."""
    column_count = len(table.headers)
    cell_style = styles["cell_compact"] if column_count >= 6 else styles["cell"]
    header_style = (
        styles["cell_header_compact"] if column_count >= 6 else styles["cell_header"]
    )

    header = [Paragraph(text, header_style) for text in table.headers]
    body = [
        [Paragraph(cell, cell_style) for cell in row]
        for row in table.rows
    ]

    flowable = Table(
        [header] + body,
        colWidths=_column_widths(len(table.headers), width),
        repeatRows=1,
        hAlign="LEFT",
    )
    flowable.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BACKGROUND),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [Paragraph(table.title, styles["heading"]), flowable]


def _column_widths(column_count: int, width: float) -> list[float]:
    """Share the page width across columns.

    Narrow tables lead with a category name, which deserves extra room. Wide
    tables lead with a date, which does not, and stealing width from five other
    columns there is what makes headers wrap mid-word.
    """
    if column_count <= 1:
        return [width]

    if column_count >= WIDE_TABLE_COLUMNS:
        return [width / column_count] * column_count

    first_share = 2.0
    total_shares = first_share + (column_count - 1)
    unit = width / total_shares
    return [unit * first_share] + [unit] * (column_count - 1)
