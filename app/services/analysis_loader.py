"""Full-file loading for metric analysis."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from app.analytics.metrics import (
    BasicMetrics,
    SelectedColumns,
    calculate_basic_metrics,
)
from app.services.file_loader import (
    FileLoadError,
    _detect_csv_delimiter,
    _detect_csv_encoding,
    _polars_encoding,
)


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def calculate_file_metrics(file_path: str | Path, selected_columns: SelectedColumns) -> BasicMetrics:
    """Load selected columns and calculate metrics."""
    data = load_selected_columns(file_path, selected_columns)
    return calculate_basic_metrics(data, selected_columns)


def load_selected_columns(file_path: str | Path, selected_columns: SelectedColumns) -> pd.DataFrame:
    """Load only selected columns needed for analysis."""
    path = Path(file_path)
    extension = path.suffix.lower()

    if not path.is_file():
        raise FileLoadError("Selected path is not a readable file.")
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise FileLoadError(f"Unsupported file type. Please choose one of: {supported}.")

    columns = _selected_column_names(selected_columns)
    if not columns:
        raise FileLoadError("Select at least a revenue, expenses, or amount column before analysis.")

    if extension == ".csv":
        return _load_csv_selected_columns(path, columns)
    if extension == ".xlsx":
        return _load_excel_selected_columns(path, columns)
    return _load_excel_selected_columns(path, columns)


def _selected_column_names(selected_columns: SelectedColumns) -> list[str]:
    """Return selected column names without duplicates."""
    names = [
        *selected_columns.date,
        *selected_columns.revenue,
        *selected_columns.expense,
        *selected_columns.amount,
        *selected_columns.category,
    ]
    return list(dict.fromkeys(names))


def _load_csv_selected_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    """Load selected CSV columns, preferring Polars for speed."""
    encoding, sample_text = _detect_csv_encoding(path)
    delimiter = _detect_csv_delimiter(sample_text)
    has_generic_columns = all(_is_generic_column_name(column) for column in columns)

    try:
        import polars as pl

        if hasattr(pl, "read_csv"):
            frame = pl.read_csv(
                str(path),
                separator=delimiter,
                encoding=_polars_encoding(encoding),
                columns=None if has_generic_columns else columns,
                has_header=not has_generic_columns,
                infer_schema=False,
                try_parse_dates=False,
                truncate_ragged_lines=True,
                rechunk=False,
            )
            if has_generic_columns:
                all_column_names = _generic_column_names(frame.width)
                frame.columns = all_column_names
                frame = frame.select(columns)
            return _pandas_from_polars(frame)
    except Exception:
        pass

    if has_generic_columns:
        frame = pd.read_csv(
            path,
            sep=delimiter,
            encoding=encoding,
            usecols=_column_indexes(columns),
            header=None,
            dtype=str,
            keep_default_na=False,
            engine="c",
            on_bad_lines="skip",
        )
        return _rename_indexed_columns(frame, columns)

    return pd.read_csv(
        path,
        sep=delimiter,
        encoding=encoding,
        usecols=columns,
        dtype=str,
        keep_default_na=False,
        engine="c",
        on_bad_lines="skip",
    )


def _load_excel_selected_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    """Load selected Excel columns, handling generated Column N names."""
    has_generic_columns = all(_is_generic_column_name(column) for column in columns)
    if has_generic_columns:
        frame = pd.read_excel(path, sheet_name=0, usecols=_column_indexes(columns), header=None)
        return _rename_indexed_columns(frame, columns)
    return pd.read_excel(path, sheet_name=0, usecols=columns)


def _pandas_from_polars(frame: object) -> pd.DataFrame:
    """Convert a selected Polars frame to pandas without requiring pyarrow."""
    return pd.DataFrame(frame.to_dict(as_series=False))


def _is_generic_column_name(column_name: str) -> bool:
    """Return whether a column name follows the generated Column N pattern."""
    return bool(re.fullmatch(r"Column \d+", column_name))


def _generic_column_names(column_count: int) -> list[str]:
    """Create generic Column N names."""
    return [f"Column {index + 1}" for index in range(column_count)]


def _column_indexes(columns: list[str]) -> list[int]:
    """Convert generated Column N names to zero-based indexes."""
    return [int(column_name.split()[-1]) - 1 for column_name in columns]


def _rename_indexed_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Rename index-selected generic columns and keep the user's selected order."""
    index_to_name = dict(zip(_column_indexes(columns), columns))
    renamed = frame.rename(columns=index_to_name)
    return renamed.loc[:, columns]
