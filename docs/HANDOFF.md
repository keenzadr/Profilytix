# Profilytix Handoff

Last updated: 2026-08-16

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
- camelCase headers are split before matching, so `TotalPrice` and `ShippingCost` are understood.
- Category detection covers real-world dimension names (region, product, store, филиал, ...) and can also select a column from its values alone.
- Confirmation is requested whenever a money column was chosen on value shape without header support.
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
- Anomaly markers on the chart, in the embedded view, the fullscreen dialog, and exports.
- Report export in five formats: PDF, XLSX, HTML, PNG, CSV.
- Two report depths: brief and detailed.
- Report language selectable at export time: Russian or English.
- Rule-based insight sentences, including daily burn rate and a cash gap warning.
- Export runs in a background `QThread` worker with success and failure reporting.
- `Open Folder` button after a successful export.
- Forecasting for every visible series: moving average or linear trend, whichever scores better.
- Forecast drawn as a dashed continuation in the embedded chart, the fullscreen dialog, and exports.
- Forecast table and a forecast insight sentence in reports.

Not implemented yet:

- cancellation for long-running analysis;
- true `loaded MB / total MB` progress;
- full-table virtual scrolling/viewing;
- saved reusable column-mapping profiles;
- application UI translation (only reports are bilingual);
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
- `app/reports/model.py` - print-ready report structures.
- `app/reports/strings.py` - Russian and English label tables, plus series name translation.
- `app/reports/insights.py` - five formula-based insight rules.
- `app/reports/builder.py` - turns analysis results into a `ReportModel` at a chosen depth and language.
- `app/reports/chart_image.py` - shared chart drawing, anomaly markers, and PNG rendering.
- `app/reports/writers/` - one module per export format behind a shared registry.
- `app/ui/export_dialog.py` - format, depth, and language selection.
- `scripts/make_sample_data.py` - generates a synthetic transactional CSV with planted anomalies.
- `tests/` - anomaly detection, strings, insights, chart image, builder, writers, and export UI.
- `requirements.txt` - PySide6, pandas, polars, openpyxl, xlrd, scikit-learn, matplotlib, reportlab.
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
- Report generation lives in `app/reports/` and never imports PySide6. `main_window.py` imports the report layer, not the reverse. That is what allows every part of report generation to be unit tested without starting a GUI.
- Chart drawing moved out of `main_window.py` into `app/reports/chart_image.py` and is imported back. The on-screen chart and the exported image therefore come from the same code and cannot drift apart.
- `chart_image.py` uses `FigureCanvasAgg` directly rather than switching the global Matplotlib backend, so the Qt canvas keeps working while reports render off-screen.
- `ReportModel` reaches a writer already print-ready: values are formatted strings in the target language and inapplicable sections are absent. Depth and language are resolved once in `builder.py` instead of five times.
- Adding an export format costs one module plus one registry entry in `app/reports/writers/__init__.py`.
- Writer modules carry a `_writer` suffix because `csv.py` and `html.py` would sit next to code importing the standard library modules of those names.
- PDF uses ReportLab with `DejaVuSans.ttf` taken from `matplotlib.get_data_path()`. Matplotlib is already a dependency, so Cyrillic works with no vendored font and no network access. WeasyPrint and QtWebEngine were rejected: GTK dependencies and roughly 130 MB respectively, both bad for a future PyInstaller build.
- Reports translate series names from `series_key` rather than reusing `FinancialAnomaly.series_label`, which is English for the UI. Without this a Russian report reads "spike in Expenses".
- Analysis requests a wider category breakdown (`ANALYSIS_CATEGORY_LIMIT`) than the panel shows, because a detailed report wants the full list; the panel slices back to five.
- CSV export is a stacked document with blocks of differing width, not a rectangle. It uses `;` and a UTF-8 BOM so Excel on Russian Windows opens it correctly by double-click. Read it with the `csv` module, not `pandas.read_csv`.
- Forecasting scores the moving average and the linear trend over the same periods. Scoring the line over the whole range and the average over its tail would compare two different questions, because the average cannot predict the first few points at all.
- The line is only chosen when it beats the average by `TREND_ADVANTAGE`. A free slope always fits noise slightly better, and telling a small business its revenue is trending steeply when the data does not support that is worse than reporting a flat level.
- `ReportModel.tables()` is what every writer walks, so a table added there reaches all five formats at once. The forecast table was added that way and needed no writer changes.
- Forecasting refuses below `MIN_POINTS_FOR_FORECAST` (six periods). Note that five months of data grouped by month falls under this and correctly produces no forecast; grouping by week gives 22 points and does.

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

The MVP is feature-complete: every success criterion in `PROJECT_CONTEXT.md` is met. The
binding constraint is no longer features. It is that nobody outside this repository has run
the application, and that the interface has never been clicked.

Recommended order:

1. **Work through `docs/MANUAL_TESTING.md` and fix what it finds.** Mandatory before anything
   else. Packaging or extending software that no human has operated compounds unknown defects.
2. **Translate the application UI to Russian.** Reports are already bilingual; the window is
   English only. `PROJECT_CONTEXT.md` targets Russian-speaking small business owners in a
   tenge market, so an English interface blocks the first real user session outright. The
   label-table pattern in `app/reports/strings.py` extends to the UI directly.
3. **Package with PyInstaller, then Inno Setup.** Required for anyone to run this without a
   Python toolchain. Expect friction: PySide6, matplotlib, polars and scikit-learn together
   produce a large bundle with hidden-import problems.
4. **Put it in front of three to five real small business owners and watch.** Everything below
   this line is a guess until that happens.

Deferred, and deliberately so:

- Cancel and real progress for long-running analysis.
- Forecast shown in the main window panel, not only on the chart and in reports.
- Transaction categorisation, ML Phase 2 in `PROJECT_CONTEXT.md`. Rule-based first. Which
  rules matter cannot be known before seeing real customer files.
- Category-aware anomaly summaries.
- Saved reusable column-mapping profiles.

Also open, small and specific: a CSV exported from pandas carries an unnamed index column.
`load_file_preview()` surfaces it as `''`, the column dialog offers it as a blank selectable
entry, and choosing it does nothing because `_normalize_selected_columns()` drops empty names.
Nothing breaks; the list simply contains a decoy. `app/services/file_loader.py` already
generates `Column N` names for headerless files, and that path should cover a single blank
header cell too. Watch the indexed renaming in `analysis_loader.py`, which has misaligned
columns before.

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
4. `docs/MANUAL_TESTING.md` - what has never been checked by hand

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
python -m pytest tests -q
python -m compileall app
python scripts/make_sample_data.py
```

Test data:

- `sample_data/transactions_sample.csv` is generated by `scripts/make_sample_data.py`. It has
  Russian headers, six categories, and three planted anomalies at known dates, so detection
  output can be checked against an expected answer.
- `sample_data/Financial Distress.csv` is the Kaggle financial-distress dataset: 86 columns,
  no real date and no money columns. It is a robustness fixture, not analysis data. The
  detector flags `weak_headers` and `needs_user_confirmation` on it, and picking its integer
  `Time` column as a date correctly yields no dates rather than a chart stretching to 1970.

`sample_data/` is git-ignored, so neither file is in the repository.

Files referenced by earlier handoffs (`C:\Users\user\Desktop\transactions.csv` and similar)
lived on a previous machine and are gone. Do not assume any local path exists; check first.

### PDF Tables Wrapped Headers Mid-Word

Problem:

- The six-column anomaly table gave its first column double width, on the assumption that it
  held a category name. It holds a date. The five remaining columns were squeezed until
  `Показатель` broke into `Показател` / `ь`.

Fix:

- `_column_widths()` in `pdf_writer.py` shares width equally once a table reaches five
  columns, and cells drop to 8pt at six.

### Autodetect Was Confidently Wrong On English Sales Files

Problem:

- On a realistic sales export (`Date, Region, Product, Quantity, UnitPrice, ..., TotalPrice,
  ShippingCost, ...`) the detector chose `UnitPrice` as the money column, found no category,
  and set `needs_user_confirmation` to `False`. A user who clicked Analyze without opening
  `Configure Columns...` saw 448 240.42 where the real revenue was 4 379 992.43, with no
  warning. Wrong by 10x, stated confidently.

Root cause:

- `normalize_text()` split on `_ - / \ | : ; . ,` and brackets but not on camelCase, so
  `TotalPrice` normalized to `totalprice`, in which no keyword list can find `total`. Every
  English camelCase header was invisible to every dictionary in the module.

Four fixes, all in `app/analytics/column_detection.py` unless noted:

- `normalize_text()` splits camelCase and acronym boundaries before folding case.
- `_score_column()` scores the `amount` role before the keyword shortcut. The shortcut
  returned early at a 0.75 keyword score, so a well-named money column ranked *below* an
  unnamed numeric one that reached 0.85 on values alone. Having a meaningful name lowered a
  column's score.
- Revenue and expense roles now reject a keyword hit when the column holds text, capping it
  at `NON_MONEY_KEYWORD_CEILING`. Without this, `PaymentMethod` became an expense because it
  matches `payment`, while containing Card and Cash. The check uses the numeric ratio only,
  not `_score_money_values()`, because the stricter heuristic rejects integer-only columns as
  identifier-like and a revenue column of round thousands looks exactly like that.
- `needs_user_confirmation` is `True` whenever a money role rests on value shape with no
  header support, detected via `KEYWORD_REASON_MARKER`.

Category detection also gained real-world names (region, product, store, branch, manager,
регион, товар, филиал, ...) and graded value evidence: `_score_category_values()` returned a
flat 0.55 while the category threshold is 0.7, so evidence from values alone could never
select anything.

Follow-on bug this exposed, in `app/analytics/time_series.py`:

- `_visible_chart_series()` decided visibility from selected-column counts. A signed amount
  feeds its positive values into revenue, so with `amount` plus a named expense the chart
  showed only shipping costs and hid 4.38 M of revenue. Visibility now follows the values.

### Report CSV Is Not A Rectangle

Problem:

- A test read the exported CSV with `pandas.read_csv` and failed with a tokenizing error.

Fix:

- The report CSV is a stacked document whose blocks have different widths, which is correct
  for something opened in Excel. The test now reads it with the `csv` module.

## Current State

The current app supports:

- fast local file preview;
- column detection and manual mapping;
- basic financial metrics;
- category summary;
- interactive charts with resizing, fullscreen, grouping, readable axis labels, dynamic legend, and snap hover labels;
- simple IQR/Z-score anomaly detection with compact and detailed UI output, and markers on the chart;
- report export to PDF, XLSX, HTML, PNG, and CSV, at brief or detailed depth, in Russian or English;
- rule-based insights including burn rate and a cash gap warning;
- forecasting drawn on the chart and included in reports.

All seven MVP success criteria from `PROJECT_CONTEXT.md` are met.

## Verification Status

Verified on 2026-08-15 with Python 3.12.10 in `.venv`:

- `python -m pytest tests -q` - 132 passed.
- Autodetect on `Product-Sales-Region.xlsx` now produces the same numbers as careful manual
  mapping: revenue 4 379 992.43, expenses 41 260.94, category by Region, 30 monthly points,
  2 anomalies, 3 forecast series.
- `python -m compileall app -q` - no errors.
- All five formats exported from `transactions_sample.csv` at both depths in both languages,
  20 files, all non-empty.
- PDF text extracted and checked: Cyrillic renders correctly, series names are translated,
  no mid-word wrapping.
- Chart images inspected: anomaly markers land on the planted anomalies, and forecast lines
  continue each series in its own colour without disturbing the axis range.
- `Financial Distress.csv` loads, flags uncertainty, and exports without crashing.

### Not Verified

Nobody has driven the real interface. `tests/test_export_ui.py` builds the window under the
offscreen Qt platform and exercises the dialog and the export worker for real, but no human
has clicked anything.

One specific open question: on 2026-08-15 the application was started in the background. The
process ran and exited with code 0, printing nothing — no traceback, no warning. That is what
closing a window looks like, and also what an immediate exit looks like. Whether the window
actually appeared is unconfirmed.

`docs/MANUAL_TESTING.md` holds the checklist, with expected numbers for every step. Those
numbers were produced programmatically on this code, so a mismatch points at the UI layer
rather than at the analysis.
