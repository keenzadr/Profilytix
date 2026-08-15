# Report Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export the current analysis as a report in PDF, XLSX, PNG, CSV, or HTML, at brief or detailed depth, in Russian or English.

**Architecture:** A Qt-independent report layer. A builder turns the existing `BasicMetrics`, `TimeSeriesResult`, and `AnomalyDetectionResult` into a print-ready `ReportModel`; five small writers lay that model out per format. Language and depth are resolved once, in the builder.

**Tech Stack:** Python 3.12, PySide6, pandas, matplotlib, openpyxl, reportlab.

**Spec:** `docs/superpowers/specs/2026-08-15-report-export-design.md`

## Global Constraints

- Python 3.12+; PySide6 for UI; pandas for tabular work; scikit-learn for classical ML.
- No web stack, no auth, no payments, no cloud, no database, no LLM API.
- Every task must preserve existing working functionality.
- Modules stay small and readable; no clever abstractions.
- Nothing under `app/reports/` may import PySide6. The UI imports the report layer, never the reverse.
- Report text is Russian or English, selected at export time. The application UI stays English.
- Money values carry no currency symbol, matching `format_money()` in `app/analytics/metrics.py:447`.
- Exactly one new dependency: `reportlab`. Add it to `requirements.txt`.
- Commit after every task on branch `feature/report-export`. Do not push.

---

### Task 0: Environment and verification data

**Files:**
- Create: `.venv/` (not committed)
- Create: `scripts/make_sample_data.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: a working Python 3.12 venv with all dependencies; `sample_data/transactions_sample.csv` with known planted anomalies for manual verification.

- [ ] **Step 1: Confirm Python 3.12 is installed**

Run: `py -0p`
Expected: a `-V:3.12` line pointing at `Python312\python.exe`.

- [ ] **Step 2: Create the venv and install dependencies**

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt pytest
```

- [ ] **Step 3: Add reportlab to requirements.txt**

Append `reportlab>=4.0` to `requirements.txt`, then install it:

```bash
.venv/Scripts/python.exe -m pip install "reportlab>=4.0"
```

- [ ] **Step 4: Verify the existing app imports and the existing test passes**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: 3 passed (the existing anomaly detection tests).

Run: `.venv/Scripts/python.exe -m compileall app -q`
Expected: no errors.

- [ ] **Step 5: Write the sample data generator**

`scripts/make_sample_data.py` writes `sample_data/transactions_sample.csv` with Russian
headers `Дата операции,Категория,Сумма дохода,Сумма расхода`, roughly 400 daily rows across
about 5 months, six categories, and three planted anomalies: one revenue spike at 8x the
median, one expense spike at 6x, and one profit collapse. Values are written with a space as
the thousands separator to exercise `_clean_numeric_value()`. Use a fixed seed so runs are
reproducible.

- [ ] **Step 6: Generate the data and confirm it loads**

```bash
.venv/Scripts/python.exe scripts/make_sample_data.py
```

Expected: the file exists and pandas reads it with four columns and the planted rows present.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt scripts/make_sample_data.py
git commit -m "Add report export dependencies and sample data generator"
```

---

### Task 1: Report model and strings

**Files:**
- Create: `app/reports/model.py`
- Create: `app/reports/strings.py`
- Test: `tests/test_report_strings.py`

**Interfaces:**
- Produces: `ReportSection`, `ReportTable`, `ReportModel` dataclasses exactly as written in spec section 4; `LABELS: dict[str, dict[str, str]]` keyed `"ru"` and `"en"`; `label(language: str, key: str) -> str` which falls back to English then to the key itself.

- [ ] **Step 1: Write the failing test**

```python
from app.reports.strings import LABELS, label


def test_russian_and_english_have_identical_keys():
    assert set(LABELS["ru"]) == set(LABELS["en"])


def test_label_falls_back_to_english_for_unknown_language():
    assert label("de", "report_title") == LABELS["en"]["report_title"]


def test_label_returns_key_when_missing_everywhere():
    assert label("ru", "no_such_key") == "no_such_key"
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_strings.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.reports.strings'`.

- [ ] **Step 3: Write `model.py`**

The three frozen dataclasses from spec section 4. No logic, no imports beyond `dataclasses` and `datetime`.

- [ ] **Step 4: Write `strings.py`**

`LABELS` covers every label the builder emits: report title, section titles (source, summary, insights, categories, anomalies, periods), every metric row label, table headers, anomaly kinds (`spike`, `drop`), severities, grouping names, and the "not available" placeholder. Both dictionaries carry the same keys.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_strings.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/reports/model.py app/reports/strings.py tests/test_report_strings.py
git commit -m "Add report model and bilingual label table"
```

---

### Task 2: Insights

**Files:**
- Create: `app/reports/insights.py`
- Test: `tests/test_report_insights.py`

**Interfaces:**
- Consumes: `BasicMetrics` from `app.analytics.metrics`, `TimeSeriesResult` from `app.analytics.time_series`, `AnomalyDetectionResult` from `app.ml.anomaly_detection`, `label()` from `app.reports.strings`.
- Produces: `generate_insights(metrics, time_series, anomalies, language) -> tuple[str, ...]`.

Each private rule returns `str | None`. `generate_insights` collects the non-`None` results in
the priority order from spec section 5 and returns at most five sentences.

- [ ] **Step 1: Write the failing tests**

Cover: last-period profit change fires with a readable percentage; the same rule returns
nothing with fewer than two periods; category concentration fires when one category dominates
and stays quiet when categories are absent; the anomaly rule reports the count; the burn-rate
rule fires only when `average_daily_profit` is negative; and `generate_insights` returns an
empty tuple when metrics are empty rather than raising.

Build inputs with small hand-made `TimeSeriesPoint` lists so expected numbers are exact.

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_insights.py -v`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement the five rules**

Guard every division by zero and every empty sequence. A rule with missing inputs returns
`None`; it never raises and never emits a sentence containing `nan` or `inf`.

- [ ] **Step 4: Run the tests**

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/reports/insights.py tests/test_report_insights.py
git commit -m "Add rule-based report insights including burn rate"
```

---

### Task 3: Chart image with anomaly markers

**Files:**
- Create: `app/reports/chart_image.py`
- Modify: `app/ui/main_window.py` (`_draw_time_series_chart`, `_update_chart`)
- Test: `tests/test_chart_image.py`

**Interfaces:**
- Produces: `render_chart_png(time_series, anomalies, width_in=10.0, height_in=4.5, dpi=150) -> bytes | None`, returning `None` when there are no points; and `draw_anomaly_markers(axes, time_series, anomalies) -> None`, which the UI chart reuses.

`chart_image.py` uses the `Agg` backend explicitly and must not import PySide6. Marker drawing
is factored so `main_window.py` calls the same function, keeping the on-screen chart and the
exported image identical.

- [ ] **Step 1: Write the failing test**

```python
def test_render_returns_png_bytes():
    result = render_chart_png(time_series, anomalies)
    assert result is not None
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_returns_none_without_points():
    empty = TimeSeriesResult(points=[], grouping="day", week_start="monday")
    assert render_chart_png(empty, None) is None


def test_markers_are_drawn_for_each_anomaly():
    figure = Figure()
    axes = figure.add_subplot(111)
    before = len(axes.lines)
    draw_anomaly_markers(axes, time_series, anomalies_with_two_items)
    assert len(axes.lines) > before
```

- [ ] **Step 2: Run and confirm failure**

- [ ] **Step 3: Implement `chart_image.py`**

Reuse the axis formatting already in `main_window.py` (`_format_chart_axis_value`) by moving it
to a shared place rather than duplicating it: put the formatting helpers used by both in
`app/reports/chart_image.py` and import them from `main_window.py`. Markers are drawn as red
downward triangles above spikes and red upward triangles below drops, with the y-axis limits
captured before and restored after, which is the same defence `main_window.py` already uses
against Matplotlib rescaling.

- [ ] **Step 4: Run the test**

Expected: pass.

- [ ] **Step 5: Wire markers into the live UI chart**

In `_update_chart`, after `_draw_time_series_chart`, call `draw_anomaly_markers` with the
anomaly result already held by the window. Store the latest `AnomalyDetectionResult` on the
window when analysis completes so the chart can reach it. `ChartDialog` receives the anomalies
too, so fullscreen matches.

- [ ] **Step 6: Verify the app still runs and markers appear**

Run the app, load `sample_data/transactions_sample.csv`, analyze, and confirm the three planted
anomalies carry markers and the x-axis still spans the real date range with no 1970 artifact.

- [ ] **Step 7: Commit**

```bash
git add app/reports/chart_image.py app/ui/main_window.py tests/test_chart_image.py
git commit -m "Add chart image rendering and anomaly markers on charts"
```

---

### Task 4: Report builder

**Files:**
- Create: `app/reports/builder.py`
- Test: `tests/test_report_builder.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ReportRequest:
    file_name: str
    depth: str        # "brief" | "detailed"
    language: str     # "ru" | "en"
    grouping: str
    include_chart: bool = True

def build_report(
    metrics: BasicMetrics,
    time_series: TimeSeriesResult,
    anomalies: AnomalyDetectionResult,
    request: ReportRequest,
) -> ReportModel: ...
```

- [ ] **Step 1: Write the failing tests**

Cover: brief omits the period table while detailed includes it; brief caps categories at five
and anomalies at eight while detailed includes everything; Russian output has a Russian section
title and English output an English one; an amount-only analysis produces an amount row instead
of revenue/expense/profit rows; a metrics object with no dates yields `chart_png is None` and
`periods is None` without raising; every value in every section is a `str`.

- [ ] **Step 2: Run and confirm failure**

- [ ] **Step 3: Implement the builder**

Depth and language are applied here and nowhere else. Numbers pass through `format_money` and
`format_number` from `app.analytics.metrics` so the report agrees with the UI. The chart is
rendered by calling `render_chart_png` when `include_chart` is set and points exist.

- [ ] **Step 4: Run the tests**

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/reports/builder.py tests/test_report_builder.py
git commit -m "Add report builder with depth and language handling"
```

---

### Task 5: Writers

**Files:**
- Create: `app/reports/writers/__init__.py`, `csv_writer.py`, `xlsx_writer.py`, `html_writer.py`, `png_writer.py`, `pdf_writer.py`

Modules carry the `_writer` suffix deliberately. Naming them `csv.py` and `html.py` would sit
directly next to code that does `import csv` and `import html` for the standard library.
Absolute imports mean it would actually work, but it is a trap for the next reader, and the
suffix costs nothing.
- Test: `tests/test_report_writers.py`

**Interfaces:**
- Produces: each module exposes `write(model: ReportModel, path: Path) -> None`. `__init__.py` exposes

```python
WRITERS: dict[str, ReportFormat]   # keyed "pdf" | "xlsx" | "png" | "csv" | "html"

@dataclass(frozen=True)
class ReportFormat:
    key: str
    label: str          # e.g. "PDF document"
    extension: str      # e.g. ".pdf"
    write: Callable[[ReportModel, Path], None]
```

Build them in ascending order of difficulty: csv, xlsx, html, png, pdf. Each is one small file.

- `csv_writer.py`: sections stacked as `label,value` blocks, tables with their headers, UTF-8 with BOM so Excel opens Cyrillic correctly.
- `xlsx_writer.py`: openpyxl, one sheet per section that exists, bold headers, frozen header row, column widths sized to content; the chart PNG is anchored on its own sheet when present.
- `html_writer.py`: a single self-contained file, inline CSS, chart embedded as a base64 `data:` URI, every value escaped with `html.escape`.
- `png_writer.py`: writes `model.chart_png` straight to disk; raises `ReportExportError` with a clear message when the model has no chart.
- `pdf_writer.py`: ReportLab platypus. Registers DejaVuSans from `matplotlib.get_data_path()/fonts/ttf/DejaVuSans.ttf` plus its bold sibling; raises `ReportExportError` naming the font when it is missing. Title, source and summary as two-column tables, insights as bullets, chart scaled to page width, category and anomaly tables with repeating headers across pages.

`ReportExportError` lives in `app/reports/writers/__init__.py` and is what the UI catches.

- [ ] **Step 1: Write the failing tests**

One parametrised test over all five writers asserting a non-empty file is produced from a full
model; signature checks (`%PDF-` prefix, PNG magic bytes, XLSX opens in openpyxl, CSV parses in
pandas with the expected row count, HTML contains each section title); a test that every writer
except `png` succeeds on a model with `chart_png=None`; and a test that `png` raises
`ReportExportError` on that same model.

- [ ] **Step 2: Run and confirm failure**

- [ ] **Step 3: Implement the writers, running the tests after each one**

- [ ] **Step 4: Run the full writer test suite**

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/reports/writers tests/test_report_writers.py
git commit -m "Add CSV, XLSX, HTML, PNG, and PDF report writers"
```

---

### Task 6: Export dialog and worker

**Files:**
- Modify: `app/ui/main_window.py`
- Create: `app/ui/export_dialog.py`

**Interfaces:**
- Consumes: `WRITERS`, `ReportExportError`, `build_report`, `ReportRequest`.
- Produces: `ExportOptions(format_key, depth, language)` and `ExportDialog.options()`.

`main_window.py` is already 1541 lines. The dialog goes in its own module rather than growing
it further; the window keeps only the button, the worker, and the result handling.

- [ ] **Step 1: Write `export_dialog.py`**

A `QDialog` with a format combo built from `WRITERS`, a depth radio pair, a language radio pair,
and OK/Cancel. Defaults: PDF, brief, Russian.

- [ ] **Step 2: Add the Export Report button**

Next to `Show Details...` in `_create_analysis_area`. Disabled until an analysis succeeds,
enabled in `_handle_analysis_completed`, disabled again in `_handle_analysis_failed` and when a
new file is loaded.

- [ ] **Step 3: Add `ExportWorker`**

Mirrors the existing `AnalysisWorker` shape: a `QObject` with `completed(str)` and `failed(str)`
signals moved onto a `QThread`. It calls `build_report` then the chosen writer. It catches
`ReportExportError` and `OSError` and emits `failed` with the message; it never lets an
exception escape the thread.

- [ ] **Step 4: Wire the flow**

Button opens `ExportDialog`; on accept, a `QFileDialog.getSaveFileName` pre-filled with the
format's extension and the source file's stem; then the worker starts and the button shows a
busy state. On success the status line shows the path and an `Open Folder` button that calls
`QDesktopServices.openUrl`.

- [ ] **Step 5: Verify by hand**

Load `sample_data/transactions_sample.csv`, analyze, and export all five formats in both depths
and both languages. Open each file and confirm Cyrillic renders in the PDF, the chart appears in
PDF, HTML, and PNG, and the XLSX sheets are populated.

Then load `sample_data/Financial Distress.csv`, which has no date and no money columns, and
confirm the app reports the problem instead of crashing.

- [ ] **Step 6: Commit**

```bash
git add app/ui/export_dialog.py app/ui/main_window.py
git commit -m "Add report export dialog and background export worker"
```

---

### Task 7: Documentation

**Files:**
- Modify: `README.md`, `docs/HANDOFF.md`

- [ ] **Step 1: Update README**

Add export to the current scope list, add `reportlab` to the dependency note, and extend the
manual check with the export steps. Remove "PDF export is intentionally not implemented yet"
and rewrite the "Next Step" section.

- [ ] **Step 2: Update HANDOFF**

Move PDF export and chart anomaly markers from "not implemented" to "implemented". Record the
new report layer in the file map and architecture decisions, including the DejaVuSans-from-
matplotlib choice and the reason WeasyPrint and QtWebEngine were rejected. Note that
`Financial Distress.csv` is a no-date robustness fixture, not analysis data.

- [ ] **Step 3: Run the full test suite and compile check**

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m compileall app -q
```

Expected: all tests pass, no compile errors.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/HANDOFF.md
git commit -m "Document report export and chart anomaly markers"
```

---

### Task 8 (deferred): Forecasting

Attempt only if Tasks 0 through 7 are finished and verified.

**Files:**
- Create: `app/ml/forecasting.py`, `tests/test_forecasting.py`
- Modify: `app/reports/chart_image.py`, `app/reports/builder.py`, `app/ui/main_window.py`

**Interfaces:**
- Produces: `forecast_series(time_series, periods_ahead=3) -> ForecastResult`, holding projected points per visible series plus the method used.

Moving average and least-squares linear trend, whichever has the lower in-sample error, refusing
to forecast with fewer than six points. Drawn as a dashed continuation of each series and added
to the report as a section. If this task is not reached, it stays in `docs/HANDOFF.md` as the
next task.

---

## Verification Gate

The work is done when, on branch `feature/report-export`:

- `.venv/Scripts/python.exe -m pytest tests -q` passes with no failures.
- `.venv/Scripts/python.exe -m compileall app -q` reports no errors.
- All five formats have been exported by hand and opened.
- The PDF shows Cyrillic text correctly.
- `Financial Distress.csv` loads without crashing the application.

No success is claimed for any of these without the command output or the opened file in hand.
