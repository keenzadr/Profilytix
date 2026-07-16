"""Basic financial metric calculation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SelectedColumns:
    """User-selected columns for analysis."""

    date: object = ()
    revenue: object = ()
    expense: object = ()
    amount: object = ()
    category: object = ()

    def __post_init__(self) -> None:
        """Normalize single-value and multi-value selections."""
        object.__setattr__(self, "date", _normalize_selected_columns(self.date))
        object.__setattr__(self, "revenue", _normalize_selected_columns(self.revenue))
        object.__setattr__(self, "expense", _normalize_selected_columns(self.expense))
        object.__setattr__(self, "amount", _normalize_selected_columns(self.amount))
        object.__setattr__(self, "category", _normalize_selected_columns(self.category))

    @property
    def has_money_column(self) -> bool:
        """Return whether at least one money column is selected."""
        return bool(self.revenue or self.expense or self.amount)


@dataclass(frozen=True)
class CategoryMetric:
    """Aggregated metric for one category."""

    name: str
    transaction_count: int
    revenue: float | None
    expenses: float | None
    profit: float | None


@dataclass(frozen=True)
class BasicMetrics:
    """Calculated financial metrics."""

    total_revenue: float | None
    total_expenses: float | None
    total_profit: float | None
    transaction_count: int
    average_revenue: float | None
    average_expense: float | None
    revenue_column_count: int = 0
    expense_column_count: int = 0
    amount_column_count: int = 0
    category_column_count: int = 0
    date_min: datetime | None = None
    date_max: datetime | None = None
    period_days: int | None = None
    average_daily_revenue: float | None = None
    average_daily_expense: float | None = None
    average_daily_profit: float | None = None
    top_categories: tuple[CategoryMetric, ...] = ()


@dataclass(frozen=True)
class PreparedFinancialData:
    """Cleaned series needed for metrics and time-series analysis."""

    transaction_count: int
    revenue: pd.Series | None
    expenses: pd.Series | None
    amount: pd.Series | None
    dates: pd.Series | None
    categories: pd.Series | None
    revenue_column_count: int
    expense_column_count: int
    amount_column_count: int
    category_column_count: int


def calculate_basic_metrics(data: pd.DataFrame, selected_columns: SelectedColumns) -> BasicMetrics:
    """Calculate basic metrics from selected optional columns."""
    return calculate_basic_metrics_from_prepared(
        prepare_financial_data(data, selected_columns)
    )


def prepare_financial_data(
    data: pd.DataFrame,
    selected_columns: SelectedColumns,
) -> PreparedFinancialData:
    """Prepare cleaned date and money series for analysis."""
    revenue_columns = _existing_columns(data, selected_columns.revenue)
    expense_columns = _existing_columns(data, selected_columns.expense)
    amount_columns = _existing_columns(data, selected_columns.amount)
    category_columns = _existing_columns(data, selected_columns.category)
    revenue = _sum_numeric_columns(data, revenue_columns)
    expenses = _sum_numeric_columns(data, expense_columns)
    amount, amount_revenue, amount_expenses = _prepare_amount_columns(data, amount_columns)
    revenue = _add_optional_series(revenue, amount_revenue)
    expenses = _add_optional_series(expenses, amount_expenses)
    dates = _first_valid_date_column(data, selected_columns.date)
    categories = _combined_category_columns(data, category_columns)

    return PreparedFinancialData(
        transaction_count=len(data),
        revenue=revenue,
        expenses=expenses,
        amount=amount,
        dates=dates,
        categories=categories,
        revenue_column_count=len(revenue_columns),
        expense_column_count=len(expense_columns),
        amount_column_count=len(amount_columns),
        category_column_count=len(category_columns),
    )


def calculate_basic_metrics_from_prepared(
    prepared: PreparedFinancialData,
) -> BasicMetrics:
    """Calculate basic metrics from already cleaned financial data."""
    total_revenue = float(prepared.revenue.sum()) if prepared.revenue is not None else None
    total_expenses = (
        float(prepared.expenses.sum()) if prepared.expenses is not None else None
    )

    date_min = None
    date_max = None

    if prepared.dates is not None:
        valid_dates = prepared.dates.dropna()
        if not valid_dates.empty:
            date_min = _to_python_datetime(valid_dates.min())
            date_max = _to_python_datetime(valid_dates.max())

    return build_basic_metrics(
        transaction_count=prepared.transaction_count,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        revenue_column_count=prepared.revenue_column_count,
        expense_column_count=prepared.expense_column_count,
        amount_column_count=prepared.amount_column_count,
        category_column_count=prepared.category_column_count,
        date_min=date_min,
        date_max=date_max,
        top_categories=_calculate_top_categories(prepared),
    )


def build_basic_metrics(
    *,
    transaction_count: int,
    total_revenue: float | None,
    total_expenses: float | None,
    revenue_column_count: int = 0,
    expense_column_count: int = 0,
    amount_column_count: int = 0,
    category_column_count: int = 0,
    date_min: datetime | None = None,
    date_max: datetime | None = None,
    top_categories: tuple[CategoryMetric, ...] = (),
) -> BasicMetrics:
    """Build derived metrics from pre-aggregated totals."""
    total_profit = _subtract_optional(total_revenue, total_expenses)
    average_revenue = (
        total_revenue / transaction_count
        if total_revenue is not None and transaction_count
        else None
    )
    average_expense = (
        total_expenses / transaction_count
        if total_expenses is not None and transaction_count
        else None
    )
    period_days = None
    average_daily_revenue = None
    average_daily_expense = None
    average_daily_profit = None

    if date_min is not None and date_max is not None:
        period_days = max((date_max.date() - date_min.date()).days + 1, 1)
        if total_revenue is not None:
            average_daily_revenue = total_revenue / period_days
        if total_expenses is not None:
            average_daily_expense = total_expenses / period_days
        if total_profit is not None:
            average_daily_profit = total_profit / period_days

    return BasicMetrics(
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        total_profit=total_profit,
        transaction_count=transaction_count,
        average_revenue=average_revenue,
        average_expense=average_expense,
        revenue_column_count=revenue_column_count,
        expense_column_count=expense_column_count,
        amount_column_count=amount_column_count,
        category_column_count=category_column_count,
        date_min=date_min,
        date_max=date_max,
        period_days=period_days,
        average_daily_revenue=average_daily_revenue,
        average_daily_expense=average_daily_expense,
        average_daily_profit=average_daily_profit,
        top_categories=top_categories,
    )


def clean_numeric_column(series: pd.Series) -> pd.Series:
    """Convert common money-like values to numeric values."""
    direct = pd.to_numeric(series, errors="coerce")
    missing_mask = direct.isna()
    if not missing_mask.any():
        return direct

    missing_values = series[missing_mask]
    if missing_values.empty or missing_values.isna().all():
        return direct.fillna(0)

    missing_text = missing_values.astype(str).str.strip()
    if missing_text.eq("").all():
        return direct.fillna(0)

    cleaned = series.astype(str).map(_clean_numeric_value)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def clean_date_column(series: pd.Series) -> pd.Series:
    """Convert common date-like values to datetimes."""
    values = series.astype(str).str.strip()
    fast_result = _try_fast_date_parse(values)
    if fast_result is not None:
        return fast_result

    iso_mask = values.str.match(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}")

    result = pd.to_datetime(values.where(iso_mask), errors="coerce", yearfirst=True)
    fallback_mask = result.isna()
    if fallback_mask.any():
        result.loc[fallback_mask] = pd.to_datetime(
            values.loc[fallback_mask],
            errors="coerce",
            dayfirst=True,
        )

    return result


def _try_fast_date_parse(values: pd.Series) -> pd.Series | None:
    """Parse uniform common date formats with explicit pandas formats."""
    sample = values[values.ne("")].head(20)
    if sample.empty:
        return None

    format_checks = (
        (
            r"^\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{2}:\d{2}\.\d+ [+-]\d{2}:\d{2}$",
            {"format": "%Y-%m-%d %H:%M:%S.%f %z"},
        ),
        (r"^\d{4}-\d{1,2}-\d{1,2}$", {"format": "%Y-%m-%d"}),
        (r"^\d{1,2}\.\d{1,2}\.\d{4}$", {"format": "%d.%m.%Y"}),
        (r"^\d{1,2}/\d{1,2}/\d{4}$", {"dayfirst": True}),
    )

    for pattern, options in format_checks:
        if not sample.str.match(pattern).all():
            continue
        result = pd.to_datetime(values, errors="coerce", **options)
        if result.notna().any():
            return result

    return None


def _normalize_selected_columns(value: object) -> tuple[str, ...]:
    """Return a deduplicated tuple of selected column names."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()

    try:
        iterator = iter(value)  # type: ignore[arg-type]
    except TypeError:
        return ()

    selected: list[str] = []
    seen: set[str] = set()
    for column_name in iterator:
        if not isinstance(column_name, str) or not column_name or column_name in seen:
            continue
        selected.append(column_name)
        seen.add(column_name)
    return tuple(selected)


def _existing_columns(data: pd.DataFrame, columns: tuple[str, ...]) -> tuple[str, ...]:
    """Return selected columns that exist in the loaded data."""
    return tuple(column for column in columns if column in data.columns)


def _sum_numeric_columns(data: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series | None:
    """Clean and sum multiple money-like columns row by row."""
    if not columns:
        return None

    total = pd.Series(0.0, index=data.index)
    for column in columns:
        total = total.add(clean_numeric_column(data[column]), fill_value=0)
    return total


def _prepare_amount_columns(
    data: pd.DataFrame,
    columns: tuple[str, ...],
) -> tuple[pd.Series | None, pd.Series | None, pd.Series | None]:
    """Prepare net, positive, and negative amount series."""
    if not columns:
        return None, None, None

    amount = pd.Series(0.0, index=data.index)
    revenue = pd.Series(0.0, index=data.index)
    expenses = pd.Series(0.0, index=data.index)
    for column in columns:
        values = clean_numeric_column(data[column])
        amount = amount.add(values, fill_value=0)
        revenue = revenue.add(values.clip(lower=0), fill_value=0)
        expenses = expenses.add(values.clip(upper=0).abs(), fill_value=0)
    return amount, revenue, expenses


def _add_optional_series(
    left: pd.Series | None,
    right: pd.Series | None,
) -> pd.Series | None:
    """Add two optional numeric series."""
    if left is None:
        return right
    if right is None:
        return left
    return left.add(right, fill_value=0)


def _to_python_datetime(value: Any) -> datetime:
    """Convert pandas timestamps to Python datetimes."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _first_valid_date_column(data: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series | None:
    """Use the first selected date column that contains valid dates."""
    for column in columns:
        if column not in data.columns:
            continue
        dates = clean_date_column(data[column])
        if dates.notna().any():
            return dates
    return None


def _combined_category_columns(
    data: pd.DataFrame,
    columns: tuple[str, ...],
) -> pd.Series | None:
    """Combine selected category columns into one display category."""
    if not columns:
        return None

    if len(columns) == 1:
        return data[columns[0]].astype(str).map(_clean_category_value)

    selected = data.loc[:, list(columns)].astype(str)
    return selected.apply(
        lambda row: " / ".join(
            value
            for value in (_clean_category_value(item) for item in row)
            if value
        )
        or "Uncategorized",
        axis=1,
    )


def _clean_category_value(value: object) -> str:
    """Normalize a category cell for display and grouping."""
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none", "null"} else "Uncategorized"


def _calculate_top_categories(
    prepared: PreparedFinancialData,
    limit: int = 5,
) -> tuple[CategoryMetric, ...]:
    """Calculate a compact category breakdown."""
    if prepared.categories is None:
        return ()

    frame = pd.DataFrame({"category": prepared.categories})
    if prepared.revenue is not None:
        frame["revenue"] = prepared.revenue.fillna(0).astype(float)
    if prepared.expenses is not None:
        frame["expenses"] = prepared.expenses.fillna(0).astype(float)

    if "revenue" not in frame and "expenses" not in frame:
        return ()

    if "revenue" not in frame:
        frame["revenue"] = 0.0
    if "expenses" not in frame:
        frame["expenses"] = 0.0

    frame["profit"] = frame["revenue"] - frame["expenses"]
    grouped = (
        frame.groupby("category", dropna=False)
        .agg(
            transaction_count=("category", "size"),
            revenue=("revenue", "sum"),
            expenses=("expenses", "sum"),
            profit=("profit", "sum"),
        )
        .reset_index()
    )
    grouped["sort_value"] = grouped["profit"].abs()
    grouped = grouped.sort_values("sort_value", ascending=False).head(limit)

    return tuple(
        CategoryMetric(
            name=str(row.category),
            transaction_count=int(row.transaction_count),
            revenue=float(row.revenue),
            expenses=float(row.expenses),
            profit=float(row.profit),
        )
        for row in grouped.itertuples(index=False)
    )


def format_money(value: float | None) -> str:
    """Format optional money values for display."""
    if value is None:
        return "not available"
    return f"{value:,.2f}".replace(",", " ")


def format_number(value: float | int | None) -> str:
    """Format optional numeric values for display."""
    if value is None:
        return "not available"
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ")


def _clean_numeric_value(value: Any) -> str:
    """Normalize one numeric cell value."""
    text = str(value).strip()
    if not text:
        return ""

    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[^\d,.\-+]", "", text)

    if text.count(",") and text.count("."):
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1 and text.count(".") == 0:
        left, right = text.split(",")
        text = left.replace(" ", "") + ("." + right if len(right) <= 2 else right)
    elif text.count(".") == 1 and text.count(",") == 0:
        left, right = text.split(".")
        text = left.replace(" ", "") + ("." + right if len(right) <= 2 else right)

    text = text.replace(" ", "")
    if negative and not text.startswith("-"):
        text = f"-{text}"
    return text


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    """Subtract optional values only when both are available."""
    if left is None or right is None:
        return None
    return left - right
