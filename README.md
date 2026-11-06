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

The suite covers analysis, reports, file schema/paging, cash estimates, categorisation,
localisation, background workers and packaging source checks. Native startup and Russian
controls were visually inspected on 2026-11-06; the full interactive workflow remains open.
`docs/MANUAL_TESTING.md` lists what to click and the numbers to expect.

## Next Step

The original roadmap implementation was expanded on 2026-11-06:

- Russian is the default desktop language; switching to English preserves the open file and results.
- Select `Description (categorisation)` in the column dialog to derive Marketing, Sales, Rent,
  Payroll, Inventory and Other categories using local RU/EN rules. Existing category columns remain separate.
- Save, apply and delete reusable column mappings in local application settings. A mapping is
  rejected if the current file lacks any saved columns.
- Choose IQR/Z-score or deterministic Isolation Forest (at least eight finite periods).
- Enter an optional current cash balance to estimate runway and the balance after 30 days.
  These estimates use historical average net profit; undated money transactions suppress them.
- The right panel includes the next-period forecast and cash summary. Reports include derived
  categories and cash estimates too.
- Cancel full-file analysis cooperatively; loading progress reports bytes for CSV and rows for Excel.
- `View all rows...` opens a background-loaded, paged table model. Pages retain at most 1,000 rows;
  moving to later pages scans earlier records again. The normal preview stays limited to 100 rows.
- Blank/duplicate headers are normalized consistently across preview, analysis and browsing.

The startup window has been inspected on Windows. Continue the full interactive checks in
`docs/MANUAL_TESTING.md` before release. The current status is recorded in `docs/ROADMAP_STATUS.md`.

## Windows Build

```powershell
pwsh -File scripts/build_windows.ps1 -InstallDependencies -Installer
```

This prepares a one-folder PyInstaller app and, with Inno Setup 6 installed, a per-user
installer. The bundled synthetic demo and frozen smoke test exercise all five report formats.
See `packaging/README.md` for prerequisites and `packaging/BUILD_STATUS.md` for actual verification.
No EXE or installer has been produced on this machine: PyInstaller is missing, its download
was blocked by unavailable PyPI DNS, and Inno Setup is absent.

On a restricted Windows environment, run tests with an explicit writable temporary directory:

```powershell
./.venv/Scripts/python.exe -m pytest tests -q --basetemp .pytest-tmp-check
```
