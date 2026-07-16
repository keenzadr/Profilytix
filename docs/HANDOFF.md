# Profilytix Handoff

Last updated: 2026-06-30

## 1. What Is Implemented

Profilytix is currently a local Windows desktop application built with Python 3.12+ and PySide6.

Implemented:

- Launch command: `python -m app.main`.
- Main desktop window titled `Profilytix`.
- File loading for `.csv`, `.xlsx`, and `.xls`.
- Last used file directory is remembered with `QSettings`.
- Fast preview of the first 100 rows.
- File metadata display: file name, file size, row count status, column count, preview rows, column names, CSV encoding/delimiter/reader when available.
- Background preview loading through `QThread`, so the UI stays responsive.
- CSV preview prefers Polars and falls back to pandas.
- Excel preview uses `openpyxl` read-only mode for `.xlsx` and pandas for `.xls`.
- CSV encoding detection supports `utf-8`, `utf-8-sig`, and `cp1251`.
- Automatic column detection for `Date`, `Revenue`, `Expenses`, `Amount`, and `Category`.
- Generic header support through `Column 1`, `Column 2`, etc.
- Weak/generic header warning.
- Money/direction/category candidate hints with reasons.
- Improved money detection that prefers decimal/currency/signed values and avoids obvious ID-like integer columns.
- Manual column mapping in a separate `Configure Columns...` dialog.
- Multiple selected fields per role using `+` and `-`.
- Optional roles: user can analyze amount-only, revenue-only, expense-only, or mixed selections.
- Signed amount support:
  - positive `Amount` values become revenue internally;
  - negative `Amount` values become expenses internally;
  - amount-only charts display `Amount`, not misleading `Revenue`/`Expenses`.
- Full-file analysis reads only selected columns.
- Basic financial metrics:
  - transactions;
  - revenue;
  - expenses;
  - profit;
  - averages;
  - date range;
  - period days;
  - average daily revenue/expense/profit.
- Category summary:
  - selected category columns are used for `Top categories by profit`;
  - `None`, `nan`, and `null` category values are normalized to `Uncategorized`.
- Compact metrics panel after analysis.
- Full metrics dialog via `Show Details...`.
- Detected-column controls are hidden after successful analysis to keep the result view clean.
- Resizable layout using splitters for table/metrics/chart areas.
- Matplotlib charts embedded in PySide6.
- Chart grouping by hour, day, week, month, and year.
- Weekly grouping supports user-selected week start: Monday through Sunday.
- Week-start selector is shown only for weekly grouping.
- Chart y-axis uses readable suffixes such as `1k`, `120k`, `1m`, `1.2m`.
- Dynamic chart legend: only relevant non-empty series are shown.
- `Open Fullscreen` chart dialog.
- Interactive chart hover:
  - hover snaps to the nearest vertical date/time position;
  - vertical guide line appears;
  - active points are highlighted with diamond markers;
  - value labels and date labels appear directly on the chart.
- Simple anomaly detection on aggregated chart data:
  - IQR rules;
  - Z-score rules;
  - revenue/amount spikes;
  - expense spikes;
  - profit/amount drops.
- Compact anomaly section in the main UI.
- Detailed anomaly rows in the `Show Details...` analysis dialog.

Not implemented yet:

- anomaly markers on charts;
- forecasting;
- PDF export;
- cancellation for long-running analysis;
- true `loaded MB / total MB` progress;
- full-table virtual scrolling/viewing;
- saved reusable column-mapping profiles;
- packaging/installer.

## 2. Created Or Changed Files

Important files:

- `app/main.py` - application entry point.
- `app/ui/main_window.py` - main UI, dialogs, workers, chart rendering, hover interactions.
- `app/services/file_loader.py` - fast Excel/CSV preview and file metadata.
- `app/services/analysis_loader.py` - selected-column loading for full analysis.
- `app/analytics/column_detection.py` - keyword/value-based column detector.
- `app/analytics/metrics.py` - numeric/date cleaning, prepared series, metrics, category summaries.
- `app/analytics/time_series.py` - time grouping and chart series selection.
- `app/ml/anomaly_detection.py` - simple IQR/Z-score anomaly detection over aggregated chart series.
- `tests/test_anomaly_detection.py` - focused anomaly detection tests.
- `requirements.txt` - PySide6, pandas, polars, openpyxl, xlrd, scikit-learn, matplotlib.
- `README.md` - setup, run, and current scope.
- `AGENTS.md` - project rules and instruction-change rule.
- `docs/HANDOFF.md` - this handoff document.

Current key structure:

```text
app/
  main.py
  ui/
    main_window.py
  services/
    file_loader.py
    analysis_loader.py
  analytics/
    column_detection.py
    metrics.py
    time_series.py
  ml/
    anomaly_detection.py
  reports/
  utils/
docs/
  HANDOFF.md
sample_data/
PROJECT_CONTEXT.md
AGENTS.md
README.md
requirements.txt
```

## 3. Architecture Decisions

- The product remains a local desktop app, not a web app.
- PySide6 is used for UI.
- File preview and analysis run in `QThread` workers to avoid freezing the UI.
- Preview is intentionally limited to the first 100 rows.
- CSV preview uses Polars where useful, with pandas fallback.
- Full metric analysis currently uses pandas after selected-column loading because the tested Polars full-aggregation path was slower on the real `transactions.csv`.
- Only selected columns are loaded for full analysis.
- `SelectedColumns` supports tuples for date, revenue, expense, amount, and category.
- `prepare_financial_data()` cleans and prepares series once, then metrics and charts reuse the prepared result.
- `Amount` is treated as signed net movement internally, but amount-only charts show `Amount` to avoid misleading UI.
- Time-series aggregation is isolated in `app/analytics/time_series.py`.
- Simple anomaly detection runs after time-series aggregation, so anomaly periods match the chart grouping.
- Charts are Matplotlib inside PySide6, not Plotly/WebView.
- Chart hover is implemented with Matplotlib artists, not Qt tooltips, so it can snap to the nearest vertical date position and show labels directly on the plot.
- The UI is intentionally still simple: no database, no auth, no cloud, no LLM API.

## 4. Project Constraints To Remember

From `PROJECT_CONTEXT.md` and `AGENTS.md`:

- Use Python 3.12+.
- Use PySide6 for desktop UI.
- Use pandas for Excel/CSV processing.
- Use scikit-learn for classical ML.
- Do not create a web application.
- Do not use FastAPI, Flask, Django, React, Next.js, or any web stack.
- Do not add authentication.
- Do not add payments.
- Do not add cloud infrastructure.
- Do not add a database in MVP unless explicitly requested.
- Do not use an LLM API in the first version.
- Keep architecture simple.
- Prefer readable code over clever abstractions.
- Preserve existing working functionality on every task.
- Profilytix is an analytics layer, not accounting software, ERP, CRM, inventory, payroll, or tax reporting software.

Important process rule:

- If a future task appears to require violating, bypassing, or changing instructions from `PROJECT_CONTEXT.md` or `AGENTS.md`, tell the user first and discuss the tradeoff before implementing it. This especially applies to stack changes, database/cloud/auth/payment/LLM usage, or changing from desktop to web.

## 5. Suggested Next Tasks

Recommended next small task:

1. Add anomaly markers on the chart.

After that:

2. Add category-aware anomaly summaries.
3. Add PDF export after metrics/charts/anomalies stabilize.
4. Add cancel/progress for long-running analysis.
5. Add packaging later through PyInstaller/Inno Setup.

## 6. Problems Already Seen And Fixes

### Polars Installed In A Different Python

Problem:

- Polars was not initially available in the Python environment used by the app/tests.

Fix:

- The user installed Polars into global Python 3.12.
- Checks used:

```powershell
python -c "import polars as pl; print(pl.__version__); print(hasattr(pl, 'read_csv'))"
```

### Full Polars Aggregation Was Slower

Problem:

- A full Polars aggregation experiment on `transactions.csv` took about `12.22s`, while the optimized pandas path was around `4.10s`, later about `3.13s` for amount-only.

Fix:

- Kept Polars for fast CSV preview/selected loading where useful.
- Kept optimized pandas cleaning/metrics as the active analysis path.

### Generic `Column N` Reading Could Misalign Columns

Problem:

- With generated columns, pandas `usecols` could return physically ordered columns and confuse selected names.

Fix:

- Added indexed renaming/order restoration in `analysis_loader.py`.

### Polars `to_pandas()` Could Require PyArrow

Problem:

- Polars -> pandas conversion via `to_pandas()` can require extra dependencies.

Fix:

- Use `pd.DataFrame(frame.to_dict(as_series=False))`.

### Date Parsing With Timezones

Problem:

- Real dates like `2026-02-01 00:00:20.000000 +00:00` needed stable parsing.

Fix:

- Added explicit fast date parse format `%Y-%m-%d %H:%M:%S.%f %z`.
- Time-series normalization uses UTC parsing then converts to timezone-naive values for grouping.

### ISO Dates Could Be Misread With `dayfirst=True`

Problem:

- `pd.to_datetime(..., dayfirst=True)` can misread ISO-like dates.

Fix:

- `clean_date_column()` handles ISO-like dates with `yearfirst=True` first, then falls back to `dayfirst=True`.

### Money Candidates Included ID Columns

Problem:

- Integer ID columns looked like money because they were numeric.

Fix:

- Money scoring now prefers decimal, signed, or currency-like values.
- Long integer-only, small integer-code, all-zero, and JSON/text-with-number columns are downgraded or ignored.

### Right Panel Became Too Crowded

Problem:

- Inline column selectors made the right panel unusable in smaller windows.

Fix:

- Moved manual column selection into `Configure Columns...`.
- Right panel now shows compact results after analysis.
- Full metrics are available through `Show Details...`.

### Chart Showed Revenue/Expenses When Only Amount Was Selected

Problem:

- Internally signed amount splits into positive revenue and negative expenses, but showing those labels in amount-only mode was confusing.

Fix:

- `TimeSeriesResult.visible_series` controls visible chart series.
- Amount-only analysis now shows `Amount`.

### Category Selection Initially Had No Visible Effect

Problem:

- Selecting category did not change the output.

Fix:

- Added `Top categories by profit` in metrics.

### Matplotlib Axis Displayed `1e6`

Problem:

- Scientific notation on the y-axis was hard to read.

Fix:

- Added compact y-axis formatting: `k`, `m`, `b`.

### Hover Layer Stretched Chart To 1970

Problem:

- The hover guide line was initially created at `x=0`.
- Matplotlib interpreted that as a date around 1970, expanding the x-axis to include 1970.

Fix:

- Hover guide line is initialized at the first real chart x-value.
- `xlim` and `ylim` are saved before creating hover artists and restored immediately after.
- Verified on `transactions.csv`: points start at `2026-02-01`, end at `2026-06-22`, and chart axis stays around 2026.

## 7. What A New Chat Must Read First

Must read fully before continuing:

1. `PROJECT_CONTEXT.md`
2. `AGENTS.md`
3. `docs/HANDOFF.md`

Then read the relevant implementation files:

4. `README.md`
5. `app/ui/main_window.py`
6. `app/services/file_loader.py`
7. `app/services/analysis_loader.py`
8. `app/analytics/column_detection.py`
9. `app/analytics/metrics.py`
10. `app/analytics/time_series.py`
11. `app/ml/anomaly_detection.py`

Useful commands:

```bash
pip install -r requirements.txt
python -m app.main
python -m compileall app
```

Real local files used during manual testing, if they still exist:

- `C:\Users\user\Desktop\transactions.csv`
- `C:\Users\user\Desktop\eubs_email.csv`
- `C:\Users\user\Desktop\emails_notify.xlsx`

Do not assume these files always exist. Check before using them.

## Current State

The current app supports:

- fast local file preview;
- column detection and manual mapping;
- basic financial metrics;
- category summary;
- interactive charts with resizing, fullscreen, grouping, readable axis labels, dynamic legend, and snap hover labels.
- simple IQR/Z-score anomaly detection with compact and detailed UI output.

The next meaningful MVP feature is anomaly markers on charts or PDF export.
