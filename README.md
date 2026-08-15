# Profilytix

Profilytix is a local Windows desktop application for small business financial analytics.

This repository currently contains a Python + PySide6 desktop application with fast Excel/CSV preview, column mapping, basic financial metrics, interactive charts, simple anomaly detection, and report export to PDF, Excel, HTML, PNG, and CSV.

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
    export_dialog.py
  services/
  analytics/
  ml/
  reports/
    model.py
    strings.py
    insights.py
    builder.py
    chart_image.py
    writers/
  utils/
docs/
sample_data/
scripts/
tests/
```

Nothing under `app/reports/` imports PySide6. The window imports the report layer, never the
other way round, which is what lets every part of report generation be tested without a GUI.

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
- Understands camelCase headers such as `TotalPrice` and `ShippingCost`, and recognises real-world category names such as `Region`, `Product`, and `Филиал`.
- Asks for confirmation whenever a money column was picked from its values rather than its name.
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
- Marks detected anomalies on the chart: spikes with a downward triangle, drops with an upward one.
- Exports a report through `Export Report...` in five formats: PDF, Excel, HTML, PNG, and CSV.
- Offers two levels of detail: brief and detailed.
- Writes the report in Russian or English, chosen at export time.
- Adds short rule-based insights, including a daily burn rate and a cash gap warning.
- Runs the export in a background worker, so a large detailed workbook does not freeze the window.
- Forecasts each visible series a few periods ahead and draws it as a dashed continuation.
- Chooses between a moving average and a linear trend per series, and declines to forecast from fewer than six periods.
- Keeps service, analytics, ML, report, and utility packages ready for the next small steps.

## Report Contents

| Section | Brief | Detailed |
|---|---|---|
| File, period, transactions, grouping | yes | yes |
| Metrics | key figures | all figures |
| Insights | yes | yes |
| Chart | yes | yes |
| Forecast | yes | yes |
| Categories | top 5 | all |
| Anomalies | top 8 | all found |
| Per-period table | no | yes |

PDF export renders Cyrillic through the DejaVuSans font that ships inside matplotlib, so no
font file is bundled and no download is needed.

## Sample Data

`sample_data/` is ignored by git. To generate a synthetic transactional file with Russian
headers and three planted anomalies:

```bash
python scripts/make_sample_data.py
```

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
11. Confirm that detected anomalies carry red triangle markers on the chart.
12. Click `Export Report...`, choose a format, detail level, and language, and save the file.
13. Open the saved file and confirm the numbers match the panel.

## Tests

```bash
python -m pytest tests -q
```

## Next Step

Add cancel and real progress reporting for long-running analysis, then packaging through
PyInstaller and Inno Setup.
