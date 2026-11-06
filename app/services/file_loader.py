"""Fast file preview helpers for Excel and CSV files."""

from __future__ import annotations

import csv
import codecs
import re
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CSV_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251")
CSV_DELIMITERS = (",", ";", "\t", "|")
PREVIEW_ROW_LIMIT = 100
PREVIEW_READ_LIMIT = PREVIEW_ROW_LIMIT + 1
SAMPLE_BYTES = 64 * 1024
HEADER_HINTS = (
    "date",
    "time",
    "amount",
    "sum",
    "total",
    "category",
    "type",
    "status",
    "email",
    "phone",
    "name",
    "id",
    "created",
    "updated",
    "дата",
    "время",
    "сумма",
    "итого",
    "категория",
    "тип",
    "статус",
    "почта",
    "телефон",
    "имя",
    "номер",
)
BOOLEAN_VALUES = {"true", "false", "yes", "no", "да", "нет", "истина", "ложь"}


class FileLoadError(Exception):
    """Raised when a file cannot be previewed as a table."""


@dataclass(frozen=True)
class TableSchema:
    """Display names in physical-column order, independent of reader naming."""

    column_names: list[str]
    has_header: bool
    encoding: str | None = None
    delimiter: str | None = None


@dataclass(frozen=True)
class LoadedFile:
    """Preview rows and metadata for a selected spreadsheet file."""

    path: Path
    column_names: list[str]
    preview_rows: list[list[str]]
    file_size_bytes: int
    total_rows: int | None = None
    encoding: str | None = None
    delimiter: str | None = None
    reader: str = ""

    @property
    def file_name(self) -> str:
        """Return the display name for the loaded file."""
        return self.path.name

    @property
    def column_count(self) -> int:
        """Return the number of detected columns."""
        return len(self.column_names)

    @property
    def preview_row_count(self) -> int:
        """Return the number of rows available in the preview."""
        return len(self.preview_rows)

    @property
    def row_count_text(self) -> str:
        """Return a fast, user-friendly row count label."""
        if self.total_rows is not None and self.total_rows >= self.preview_row_count:
            return str(self.total_rows)
        if self.preview_row_count >= PREVIEW_ROW_LIMIT:
            return f"{PREVIEW_ROW_LIMIT}+ (fast preview)"
        return str(self.preview_row_count)

    @property
    def file_size_text(self) -> str:
        """Return the file size in a readable form."""
        return format_file_size(self.file_size_bytes)


def load_file_preview(file_path: str | Path) -> LoadedFile:
    """Read only the file metadata and first preview rows."""
    path = Path(file_path)
    extension = path.suffix.lower()

    if not path.is_file():
        raise FileLoadError("Selected path is not a readable file.")

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise FileLoadError(f"Unsupported file type. Please choose one of: {supported}.")

    if extension == ".csv":
        return _load_csv_preview(path)
    if extension == ".xlsx":
        return _load_xlsx_preview(path)

    return _load_xls_preview(path)


def format_file_size(size_bytes: int) -> str:
    """Format a file size using binary units."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def _load_csv_preview(path: Path) -> LoadedFile:
    """Load the first rows of a CSV file with the fastest available reader."""
    file_size = path.stat().st_size
    if file_size == 0:
        return LoadedFile(
            path=path,
            column_names=[],
            preview_rows=[],
            file_size_bytes=file_size,
            total_rows=0,
            encoding=CSV_ENCODINGS[0],
            reader="Polars CSV",
        )

    encoding, sample_text = _detect_csv_encoding(path)
    delimiter = _detect_csv_delimiter(sample_text)

    try:
        return _load_csv_preview_with_polars(path, file_size, encoding, delimiter)
    except FileLoadError:
        return _load_csv_preview_with_pandas(path, file_size, encoding, delimiter)


def _load_csv_preview_with_polars(
    path: Path,
    file_size: int,
    encoding: str,
    delimiter: str,
) -> LoadedFile:
    """Load CSV preview using Polars."""
    try:
        import polars as pl
    except ImportError as error:
        raise FileLoadError(
            "Missing fast CSV dependency: polars. Run `pip install -r requirements.txt`."
        ) from error

    if not hasattr(pl, "read_csv"):
        raise FileLoadError(
            "Polars is installed incorrectly. Reinstall dependencies with "
            "`pip install -r requirements.txt`."
        )

    schema = _read_csv_schema(path, encoding, delimiter)
    if not schema.column_names:
        return LoadedFile(path, [], [], file_size, total_rows=0, encoding=encoding,
                          delimiter=_display_delimiter(delimiter), reader="Polars CSV")
    try:
        frame = pl.read_csv(
            str(path),
            separator=delimiter,
            encoding=_polars_encoding(encoding),
            n_rows=PREVIEW_READ_LIMIT,
            infer_schema=False,
            infer_schema_length=PREVIEW_READ_LIMIT,
            try_parse_dates=False,
            truncate_ragged_lines=True,
            rechunk=False,
            has_header=schema.has_header,
        )
    except Exception as error:
        raise FileLoadError(f"Could not read CSV preview: {error}") from error

    has_more_rows = frame.height > PREVIEW_ROW_LIMIT
    preview_frame = frame.head(PREVIEW_ROW_LIMIT)
    preview_rows = _rows_from_iterable(preview_frame.iter_rows())
    total_rows = None if has_more_rows else preview_frame.height
    column_names = schema.column_names

    return LoadedFile(
        path=path,
        column_names=column_names,
        preview_rows=preview_rows,
        file_size_bytes=file_size,
        total_rows=total_rows,
        encoding=encoding,
        delimiter=_display_delimiter(delimiter),
        reader="Polars CSV",
    )


def _load_csv_preview_with_pandas(
    path: Path,
    file_size: int,
    encoding: str,
    delimiter: str,
) -> LoadedFile:
    """Fallback CSV preview reader using pandas without loading the whole file."""
    try:
        import pandas as pd
    except ImportError as error:
        raise FileLoadError(
            "Missing CSV dependency: pandas. Run `pip install -r requirements.txt`."
        ) from error

    schema = _read_csv_schema(path, encoding, delimiter)
    if not schema.column_names:
        return LoadedFile(path, [], [], file_size, total_rows=0, encoding=encoding,
                          delimiter=_display_delimiter(delimiter), reader="pandas CSV fallback")
    try:
        frame = pd.read_csv(
            path,
            sep=delimiter,
            encoding=encoding,
            nrows=PREVIEW_READ_LIMIT,
            dtype=str,
            keep_default_na=False,
            engine="c",
            on_bad_lines="skip",
            header=0 if schema.has_header else None,
        )
    except Exception as error:
        raise FileLoadError(f"Could not read CSV preview: {error}") from error

    has_more_rows = len(frame) > PREVIEW_ROW_LIMIT
    preview_frame = frame.head(PREVIEW_ROW_LIMIT)
    total_rows = None if has_more_rows else len(preview_frame)
    column_names = schema.column_names

    return LoadedFile(
        path=path,
        column_names=column_names,
        preview_rows=_rows_from_iterable(preview_frame.itertuples(index=False, name=None)),
        file_size_bytes=file_size,
        total_rows=total_rows,
        encoding=encoding,
        delimiter=_display_delimiter(delimiter),
        reader="pandas CSV fallback",
    )


def _load_xlsx_preview(path: Path) -> LoadedFile:
    """Load the first rows of an XLSX file using openpyxl read-only mode."""
    return _load_excel_preview(path, "openpyxl read-only")


def _load_xls_preview(path: Path) -> LoadedFile:
    """Load first-sheet XLS rows through the shared physical-column reader."""
    return _load_excel_preview(path, "xlrd first sheet")


def _load_excel_preview(path: Path, reader: str) -> LoadedFile:
    try:
        with _open_excel_rows(path) as (schema, records, total):
            rows = [_normalize_row(row, len(schema.column_names))
                    for row in islice(records, PREVIEW_ROW_LIMIT)]
            return LoadedFile(path, schema.column_names, rows, path.stat().st_size,
                              total_rows=total, reader=reader)
    except FileLoadError:
        raise
    except Exception as error:
        raise FileLoadError(f"Could not read Excel preview: {error}") from error


def _detect_csv_encoding(path: Path) -> tuple[str, str]:
    """Detect a supported CSV encoding from a small byte sample."""
    sample_bytes = _read_sample_bytes(path)
    last_error: UnicodeDecodeError | None = None

    for encoding in CSV_ENCODINGS:
        try:
            # The sample can stop halfway through a UTF-8 character.
            decoder = codecs.getincrementaldecoder(encoding)()
            return encoding, decoder.decode(sample_bytes, final=len(sample_bytes) < SAMPLE_BYTES)
        except UnicodeDecodeError as error:
            last_error = error

    message = "Could not decode CSV sample with utf-8, utf-8-sig, or cp1251."
    if last_error is not None:
        message = f"{message} Last error: {last_error}"
    raise FileLoadError(message)


def _read_sample_bytes(path: Path) -> bytes:
    """Read a small sample from the beginning of the file."""
    with path.open("rb") as file:
        return file.read(SAMPLE_BYTES)


def _detect_csv_delimiter(sample_text: str) -> str:
    """Detect a CSV delimiter using a small text sample."""
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=CSV_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        return _fallback_delimiter(sample_text)


def _fallback_delimiter(sample_text: str) -> str:
    """Choose the most frequent delimiter from the first non-empty lines."""
    lines = [line for line in sample_text.splitlines()[:20] if line.strip()]
    if not lines:
        return ","

    delimiter_counts = {
        delimiter: sum(line.count(delimiter) for line in lines)
        for delimiter in CSV_DELIMITERS
    }
    delimiter, count = max(delimiter_counts.items(), key=lambda item: item[1])
    return delimiter if count > 0 else ","


def _polars_encoding(encoding: str) -> str:
    """Map common Python encoding names to names accepted by Polars."""
    if encoding in {"utf-8", "utf-8-sig"}:
        return "utf8"
    return encoding


def _display_delimiter(delimiter: str) -> str:
    """Return a readable delimiter label."""
    if delimiter == "\t":
        return "tab"
    return delimiter


def _generic_column_names(column_count: int) -> list[str]:
    """Create generic column names for files without a header row."""
    return [f"Column {index + 1}" for index in range(column_count)]


def _headers_look_like_data(headers: list[str]) -> bool:
    """Return whether detected headers look like the first data row."""
    non_empty_headers = [header.strip() for header in headers if header.strip()]
    if not non_empty_headers:
        return False

    normalized_headers = [_normalize_header(header) for header in non_empty_headers]
    if any(_contains_header_hint(header) for header in normalized_headers):
        return False

    data_like_count = sum(_looks_like_data_value(header) for header in normalized_headers)
    return data_like_count >= max(1, len(non_empty_headers) // 2)


def _normalize_header(value: str) -> str:
    """Normalize text for lightweight header checks."""
    text = value.casefold().replace("ё", "е")
    text = re.sub(r"[_\-/\\|:;.,()\[\]{}]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _contains_header_hint(value: str) -> bool:
    """Return whether a value contains a known header-like word."""
    return any(f" {hint} " in f" {value} " for hint in HEADER_HINTS)


def _looks_like_data_value(value: str) -> bool:
    """Return whether a header candidate resembles a data value."""
    if not value:
        return False
    if value in BOOLEAN_VALUES:
        return True
    if "@" in value or value.startswith(("http ", "https ", "www ")):
        return True
    if re.match(r"^\d{4}\s\d{1,2}\s\d{1,2}", value):
        return True
    if re.match(r"^\d{1,2}\s\d{1,2}\s\d{2,4}", value):
        return True
    if re.fullmatch(r"[-+()]?[\d\s,.]+", value):
        return True
    return False


def _column_names_from_header(header: tuple[Any, ...], column_count: int) -> list[str]:
    """Create unique names while reserving all explicitly named columns."""
    raw_names = [_format_cell(header[index] if index < len(header) else None).strip().lstrip("\ufeff").strip()
                 for index in range(column_count)]
    reserved = {name for name in raw_names if name}
    used: set[str] = set()
    names: list[str] = []
    for index, original in enumerate(raw_names):
        base = original or f"Column {index + 1}"
        name = base
        suffix = 2
        while name in used or (not original and name in reserved) or (name != base and name in reserved):
            name = f"{base} ({suffix})"
            suffix += 1
        names.append(name)
        used.add(name)
    return names


def _schema_from_header(header: tuple[Any, ...], column_count: int) -> TableSchema:
    """Make the same header decision for preview, analysis and paging."""
    candidates = _normalize_row(header, column_count)
    if candidates:
        candidates[0] = candidates[0].strip().lstrip("\ufeff").strip()
    has_header = not _headers_look_like_data(candidates)
    names = (_column_names_from_header(header, column_count) if has_header
             else _generic_column_names(column_count))
    return TableSchema(names, has_header)


def _read_csv_schema(path: Path, encoding: str | None = None,
                     delimiter: str | None = None) -> TableSchema:
    """Read the first physical CSV record without library-mangled headers."""
    if encoding is None or delimiter is None:
        encoding, sample = _detect_csv_encoding(path)
        delimiter = _detect_csv_delimiter(sample)
    try:
        with path.open("r", encoding=encoding, newline="") as source:
            header = next((row for row in csv.reader(source, delimiter=delimiter) if row), [])
    except (OSError, UnicodeError, csv.Error) as error:
        raise FileLoadError(f"Could not read CSV header: {error}") from error
    schema = _schema_from_header(tuple(header), len(header))
    return TableSchema(schema.column_names, schema.has_header, encoding, delimiter)


@contextmanager
def _open_excel_rows(path: Path):
    """Yield a schema and lazy rows from the first sheet, closing on every exit."""
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except Exception as error:
            raise FileLoadError(f"Could not open Excel file: {error}") from error
        try:
            if not workbook.worksheets:
                yield TableSchema([], False), iter(()), 0
                return
            sheet = workbook.worksheets[0]
            rows = sheet.iter_rows(values_only=True)
            first = next(rows, None)
            if first is None:
                yield TableSchema([], False), iter(()), 0
                return
            schema = _schema_from_header(first, max(sheet.max_column or 0, len(first)))
            from itertools import chain
            data_rows = rows if schema.has_header else chain([first], rows)
            total = max((sheet.max_row or 0) - int(schema.has_header), 0)
            yield schema, data_rows, total
        finally:
            workbook.close()
    else:
        import xlrd

        try:
            workbook = xlrd.open_workbook(str(path), on_demand=True)
        except Exception as error:
            raise FileLoadError(f"Could not open Excel file: {error}") from error
        try:
            if not workbook.nsheets:
                yield TableSchema([], False), iter(()), 0
                return
            sheet = workbook.sheet_by_index(0)
            def row_values(index):
                return tuple(xlrd.xldate_as_datetime(cell.value, workbook.datemode)
                             if cell.ctype == xlrd.XL_CELL_DATE else cell.value
                             for cell in sheet.row(index))
            first = row_values(0) if sheet.nrows else ()
            schema = _schema_from_header(first, sheet.ncols)
            start = int(schema.has_header) if sheet.nrows else 0
            yield schema, (row_values(index) for index in range(start, sheet.nrows)), sheet.nrows - start
        finally:
            workbook.release_resources()


def _normalize_row(row: tuple[Any, ...], column_count: int) -> list[str]:
    """Return a row padded or truncated to the expected column count."""
    values = list(row[:column_count])
    if len(values) < column_count:
        values.extend([None] * (column_count - len(values)))
    return [_format_cell(value) for value in values]


def _rows_from_iterable(rows: Any) -> list[list[str]]:
    """Convert row tuples from a tabular library to display-safe strings."""
    return [[_format_cell(value) for value in row] for row in rows]


def _format_cell(value: Any) -> str:
    """Convert a cell value to a safe display string."""
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except TypeError:
        pass

    return str(value)
