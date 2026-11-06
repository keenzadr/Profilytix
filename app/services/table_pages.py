"""Bounded pages from the first table sheet without retaining all data rows."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from app.services.file_loader import (
    SUPPORTED_EXTENSIONS,
    FileLoadError,
    _normalize_row,
    _open_excel_rows,
    _read_csv_schema,
)


@dataclass(frozen=True)
class TablePage:
    """One page of display-safe rows and a lookahead flag."""

    column_names: list[str]
    rows: list[list[str]]
    page: int
    has_next: bool


def load_table_page(file_path: str | Path, page: int = 0, page_size: int = 1000) -> TablePage:
    """Read at most one page plus one lookahead row into memory.

    Reaching later CSV/XLSX pages scans preceding records, but skipped rows are
    discarded immediately and never turned into table cells.
    """
    if not isinstance(page, int) or page < 0:
        raise ValueError("Page must be a non-negative integer.")
    if not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("Page size must be a positive integer.")
    path = Path(file_path)
    if not path.is_file():
        raise FileLoadError("Selected path is not a readable file.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise FileLoadError("Unsupported file type. Please choose a CSV, XLSX, or XLS file.")
    try:
        if path.suffix.lower() == ".csv":
            schema = _read_csv_schema(path)
            with path.open("r", encoding=schema.encoding, newline="") as source:
                records = (row for row in csv.reader(source, delimiter=schema.delimiter) if row)
                if schema.has_header:
                    next(records, None)
                rows = _take_page(records, len(schema.column_names), page, page_size)
        else:
            with _open_excel_rows(path) as (schema, records, _):
                rows = _take_page(records, len(schema.column_names), page, page_size)
    except FileLoadError:
        raise
    except Exception as error:
        raise FileLoadError(f"Could not read table page: {error}") from error
    return TablePage(schema.column_names, rows[:page_size], page, len(rows) > page_size)


def _take_page(records, width, page, page_size):
    start = page * page_size
    return [_normalize_row(row, width) for row in islice(records, start, start + page_size + 1)]
