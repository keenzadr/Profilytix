"""Generate a small, deterministic offline example without shipping private data."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


def generate_demo(target: Path) -> Path:
    """Write two transactions per day with a visible exceptional expense."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Дата", "Доход", "Расход", "Категория", "Описание"])
        for offset in range(90):
            day = date(2026, 1, 1) + timedelta(days=offset)
            revenue = 25000 + (offset % 7) * 1700
            expenses = 9000 + (offset % 5) * 450
            if offset == 65:
                expenses = 88000
            writer.writerow([day.isoformat(), revenue, 0, "Продажи", "Kaspi QR"])
            writer.writerow([day.isoformat(), 0, expenses, "Закупки", "Закуп товара"])
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    print(generate_demo(parser.parse_args().target))
