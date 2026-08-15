"""Generate a synthetic transactional CSV for manual and automated verification.

The file mimics what a small business actually keeps in a spreadsheet: Russian
headers, a category column, separate revenue and expense columns, and money
written with spaces as thousands separators.

Three anomalies are planted at known dates so anomaly detection can be checked
against an expected answer instead of a guess.

Run:

    .venv/Scripts/python.exe scripts/make_sample_data.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "transactions_sample.csv"

HEADERS = ["Дата операции", "Категория", "Сумма дохода", "Сумма расхода"]

START_DATE = date(2026, 1, 1)
DAY_COUNT = 151
RANDOM_SEED = 20260815

# Category name, typical revenue per transaction, typical expense per transaction.
CATEGORIES = [
    ("Продажи", 120_000, 0),
    ("Услуги", 75_000, 0),
    ("Аренда", 0, 32_000),
    ("Зарплата", 0, 55_000),
    ("Реклама", 0, 18_000),
    ("Закуп товара", 0, 40_000),
]

# Planted anomalies: day offset from START_DATE, multiplier, affected side.
REVENUE_SPIKE_DAY = 47
REVENUE_SPIKE_MULTIPLIER = 8
EXPENSE_SPIKE_DAY = 89
EXPENSE_SPIKE_MULTIPLIER = 6
PROFIT_COLLAPSE_DAY = 122


def format_money(value: int) -> str:
    """Format money the way a spreadsheet exported by a small business looks."""
    if value <= 0:
        return ""
    return f"{value:,}".replace(",", " ")


def build_rows(rng: random.Random) -> list[list[str]]:
    """Build transaction rows with three planted anomalies."""
    rows: list[list[str]] = []

    for day_offset in range(DAY_COUNT):
        current_date = START_DATE + timedelta(days=day_offset)
        weekday_factor = 0.6 if current_date.weekday() >= 5 else 1.0

        for name, base_revenue, base_expense in CATEGORIES:
            if rng.random() > 0.55:
                continue

            revenue = 0
            expense = 0
            if base_revenue:
                revenue = int(base_revenue * weekday_factor * rng.uniform(0.7, 1.3))
            if base_expense:
                expense = int(base_expense * rng.uniform(0.8, 1.2))

            if day_offset == REVENUE_SPIKE_DAY and revenue:
                revenue *= REVENUE_SPIKE_MULTIPLIER
            if day_offset == EXPENSE_SPIKE_DAY and expense:
                expense *= EXPENSE_SPIKE_MULTIPLIER
            if day_offset == PROFIT_COLLAPSE_DAY:
                revenue = int(revenue * 0.1)

            if not revenue and not expense:
                continue

            rows.append(
                [
                    current_date.strftime("%d.%m.%Y"),
                    name,
                    format_money(revenue),
                    format_money(expense),
                ]
            )

    return rows


def main() -> None:
    """Write the sample file and report what was planted."""
    rng = random.Random(RANDOM_SEED)
    rows = build_rows(rng)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(HEADERS)
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print("Planted anomalies:")
    print(f"  revenue spike  {START_DATE + timedelta(days=REVENUE_SPIKE_DAY):%d.%m.%Y}")
    print(f"  expense spike  {START_DATE + timedelta(days=EXPENSE_SPIKE_DAY):%d.%m.%Y}")
    print(f"  profit drop    {START_DATE + timedelta(days=PROFIT_COLLAPSE_DAY):%d.%m.%Y}")


if __name__ == "__main__":
    main()
