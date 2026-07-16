# Profilytix

Profilytix is a local Windows desktop application for small business financial analytics.

This repository currently contains a Python + PySide6 desktop application with fast Excel/CSV preview, column mapping, basic financial metrics, interactive charts, and simple anomaly detection.

## Requirements

- Python 3.12+
- Windows desktop environment

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m app.main
```

## Project Structure

```text
app/
  main.py
  ui/
    main_window.py
  services/
  analytics/
  ml/
  reports/
  utils/
docs/
sample_data/
tests/
```

## Current Scope

- Opens a desktop window titled `Profilytix`.
- Shows a `Load Excel/CSV` button.
- Loads `.csv`, `.xlsx`, and `.xls` files.
- Remembers the last directory used for loading files.
- Reads only the first 100 rows for fast preview instead of loading the whole file.
- Loads file previews in a background worker so the UI stays responsive.
- Uses Polars for fast CSV preview, with a pandas preview fallback when Polars is unavailable.
- Uses a fast numeric/date parsing path for clean columns, with a practical fallback for currency-like values.
- Tries common CSV encodings: `utf-8`, `utf-8-sig`, `cp1251`.
- Shows file name, file size, row count status, column count, column names, and CSV encoding/delimiter when applicable.
- Shows a loading status and busy progress indicator while preview is being read.
- Shows the first 100 rows in a table preview.
- Detects likely date, revenue, expense, amount, and category columns from headers and preview values.
- Handles files without a clear header row by assigning generic `Column 1`, `Column 2`, etc.
- Marks generic headers like `col1`, `Column 1`, `Unnamed: 0`, or numeric headers as uncertain.
- Shows money and direction candidates when revenue/expense cannot be detected safely.
- Provides a `Configure Columns...` dialog for confirming date, revenue, expense, amount, and category columns.
- Supports adding multiple fields per type with `+` and removing extra fields with `-` inside the column configuration dialog.
- Calculates basic metrics from selected optional revenue, expense, and/or signed amount columns.
- Splits signed amount columns by sign: positive values become revenue, negative values become expenses.
- Allows expense-only, revenue-only, or amount-only analysis; date and category are optional.
- Shows compact metrics after analysis, with full details available via `Show Details...`.
- Uses selected category columns for a `Top categories by profit` summary.
- Shows interactive charts when a date column is selected.
- Shows only the chart series that make sense for the selected fields, for example `Amount` for amount-only analysis.
- Supports chart grouping by hour, day, week, month, and year.
- Allows choosing the first day of the week for weekly grouping.
- Hides the week-start selector unless weekly grouping is selected.
- Allows resizing the table/metrics/chart areas with splitters.
- Allows opening the chart in a maximized `Open Fullscreen` dialog.
- Shows chart hover markers by nearest vertical date position, with a vertical guide line, highlighted point, date label, and exact value label.
- Detects simple anomalies on aggregated chart data with IQR and Z-score rules.
- Shows a compact anomaly summary in the main window and detailed anomaly rows in `Show Details...`.
- Keeps service, analytics, ML, report, and utility packages ready for the next small steps.

Forecasting and PDF export are intentionally not implemented yet.

## Manual Check

1. Install dependencies with `pip install -r requirements.txt`.
2. Run `python -m app.main`.
3. Confirm that a window titled `Profilytix` opens.
4. Click `Load Excel/CSV` and choose a `.csv`, `.xlsx`, or `.xls` file.
5. Confirm that file information, file size, and the first 100 rows are visible.
6. Confirm or change columns through `Configure Columns...`.
7. Click `Analyze File`.
8. Confirm that compact metrics and a chart appear.
9. Confirm that anomaly status appears in the right panel.
10. Hover over the chart to see the nearest-period marker and value label.

## Next Step

Add anomaly markers on the chart or start PDF export after metrics/charts/anomalies stabilize.
