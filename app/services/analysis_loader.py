"""Full-file loading for metric analysis with cooperative cancellation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from app.analytics.metrics import BasicMetrics, SelectedColumns, calculate_basic_metrics
from app.services.file_loader import (
    SUPPORTED_EXTENSIONS,
    FileLoadError,
    TableSchema,
    _open_excel_rows,
    _polars_encoding,
    _read_csv_schema,
)


ProgressCallback = Callable[[int, int, str], None]
CancellationCallback = Callable[[], bool]
CSV_CHUNK_ROWS = 5000
EXCEL_PROGRESS_ROWS = 500


class AnalysisCancelled(Exception):
    """Raised when loading is cancelled; no partial data is published."""


def calculate_file_metrics(file_path: str | Path, selected_columns: SelectedColumns) -> BasicMetrics:
    """Load selected columns and calculate metrics."""
    data = load_selected_columns(file_path, selected_columns)
    return calculate_basic_metrics(data, selected_columns)


def load_selected_columns(
    file_path: str | Path,
    selected_columns: SelectedColumns,
    *,
    progress: ProgressCallback | None = None,
    cancelled: CancellationCallback | None = None,
) -> pd.DataFrame:
    """Load physical columns with measured I/O progress and cancellation.

    CSV progress counts bytes consumed by the parser (which can read ahead).
    Excel progress counts processed data rows. Cancellation is checked before
    work, between chunks/rows, and before returning the completed frame.
    """
    _check_cancelled(cancelled)
    path = Path(file_path)
    if not path.is_file():
        raise FileLoadError("Selected path is not a readable file.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise FileLoadError(f"Unsupported file type. Please choose one of: {supported}.")
    columns = _selected_column_names(selected_columns)
    if not columns:
        raise FileLoadError("Select at least a revenue, expenses, or amount column before analysis.")
    try:
        if path.suffix.lower() == ".csv":
            data = _load_csv_selected_columns(path, columns, progress, cancelled)
        else:
            data = _load_excel_selected_columns(path, columns, progress, cancelled)
    except (AnalysisCancelled, FileLoadError):
        raise
    except Exception as error:
        raise FileLoadError(f"Could not read selected columns: {error}") from error
    _check_cancelled(cancelled)
    return data


def _selected_column_names(selected_columns: SelectedColumns) -> list[str]:
    """Return selected names without duplicates, in selection order."""
    names = [*selected_columns.date, *selected_columns.revenue, *selected_columns.expense,
             *selected_columns.amount, *selected_columns.category,
             *getattr(selected_columns, "description", ())]
    return list(dict.fromkeys(names))


def _column_indexes(schema: TableSchema, columns: list[str]) -> list[int]:
    """Resolve display names against the schema, never their spelling."""
    missing = [name for name in columns if name not in schema.column_names]
    if missing:
        raise FileLoadError(f"Selected columns are missing from the file: {', '.join(missing)}")
    return [schema.column_names.index(name) for name in columns]


def _load_csv_selected_columns(path, columns, progress=None, cancelled=None) -> pd.DataFrame:
    schema = _read_csv_schema(path)
    indexes = sorted(_column_indexes(schema, columns))
    physical_names = {index: schema.column_names[index] for index in indexes}
    if progress is None and cancelled is None:
        try:
            import polars as pl

            frame = pl.read_csv(
                str(path), separator=schema.delimiter, encoding=_polars_encoding(schema.encoding),
                columns=indexes, has_header=schema.has_header, infer_schema=False,
                try_parse_dates=False, truncate_ragged_lines=True, rechunk=False,
            )
            frame.columns = [physical_names[index] for index in indexes]
            return pd.DataFrame(frame.to_dict(as_series=False)).loc[:, columns]
        except Exception:
            # pandas supports encodings unsupported by some Polars versions.
            pass
    read_options = dict(
        sep=schema.delimiter, encoding=schema.encoding, usecols=indexes,
        header=0 if schema.has_header else None, dtype=str, keep_default_na=False,
        engine="c", on_bad_lines="skip",
    )
    if progress is None and cancelled is None:
        frame = pd.read_csv(path, **read_options)
        frame.columns = [physical_names[index] for index in indexes]
        return frame.loc[:, columns]
    total = path.stat().st_size
    _report_progress(progress, 0, total, "bytes", cancelled)
    chunks = []
    # The parser may read ahead; the offset is actual bytes read, never an
    # assumed percentage or estimated bytes per row.
    with path.open("rb") as source:
        with pd.read_csv(source, chunksize=CSV_CHUNK_ROWS, **read_options) as reader:
            for chunk in reader:
                _check_cancelled(cancelled)
                chunk.columns = [physical_names[index] for index in indexes]
                chunks.append(chunk)
                _report_progress(progress, source.tell(), total, "bytes", cancelled)
    frame = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=physical_names.values())
    _report_progress(progress, total, total, "bytes", cancelled)
    return frame.loc[:, columns]


def _load_excel_selected_columns(path, columns, progress=None, cancelled=None) -> pd.DataFrame:
    with _open_excel_rows(path) as (schema, rows, total):
        indexes = _column_indexes(schema, columns)
        _report_progress(progress, 0, total, "rows", cancelled)
        values = []
        done = 0
        for done, row in enumerate(rows, start=1):
            _check_cancelled(cancelled)
            values.append([row[index] if index < len(row) else None for index in indexes])
            if done % EXCEL_PROGRESS_ROWS == 0:
                _report_progress(progress, done, total, "rows", cancelled)
        _report_progress(progress, done, max(total, done), "rows", cancelled)
        return pd.DataFrame(values, columns=columns)


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise AnalysisCancelled("Analysis was cancelled.")


def _report_progress(progress, done, total, unit, cancelled):
    _check_cancelled(cancelled)
    if progress is not None:
        progress(done, total, unit)
    _check_cancelled(cancelled)
