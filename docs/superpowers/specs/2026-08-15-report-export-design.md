# Report Export Design

Date: 2026-08-15
Status: approved
Branch: `feature/report-export`

## 1. Goal

Let the user export the current analysis as a report in five formats, at two levels of
detail, in Russian or English.

Exporting a report is the last unimplemented item in the MVP scope defined by
`PROJECT_CONTEXT.md`. Once it works, all seven MVP success criteria are met.

## 2. Requirements

Formats: PDF, XLSX, PNG, CSV, HTML.

Depth: brief or detailed, chosen by the user at export time.

Language: Russian or English, chosen by the user at export time. The application UI stays
English in this iteration; only report content is translated.

Content: header, financial metrics, chart, top categories, anomalies, and short rule-based
insight sentences. No LLM is used.

Export must not block the UI and must not crash on a locked or unwritable target file.

## 3. Architecture

A report layer that does not depend on Qt.

```text
app/reports/
  model.py        ReportModel and section dataclasses
  strings.py      LABELS = {"ru": {...}, "en": {...}}
  insights.py     rule-based insight sentences
  builder.py      metrics + time series + anomalies + depth + language -> ReportModel
  chart_image.py  time series -> PNG bytes (Matplotlib, no Qt)
  writers/
    __init__.py   format registry
    csv.py xlsx.py html.py png.py pdf.py
```

`ReportModel` reaches a writer already print-ready: numbers formatted, labels in the target
language, sections dropped according to depth. A writer only lays the model out in its own
format.

Three consequences follow, and they are the reason for this split:

- Language and depth are decided once in `builder.py`, not five times.
- A new format costs one small file and touches nothing else.
- Everything except the dialog is testable without starting a GUI.

### Data flow

```text
AnalysisResult (existing)
  BasicMetrics + TimeSeriesResult + AnomalyDetectionResult
        |
        v
  build_report(..., depth, language, source_info)  ->  ReportModel
        |
        v
  writers[format](model, path)  ->  file on disk
```

`chart_image.render_chart_png()` is called by the builder when a chart exists, and the
resulting bytes travel inside the model. PDF, HTML, and PNG writers reuse those same bytes,
so the exported chart is identical across formats.

## 4. Model

```python
@dataclass(frozen=True)
class ReportSection:
    title: str
    rows: tuple[tuple[str, str], ...]        # label, formatted value

@dataclass(frozen=True)
class ReportTable:
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

@dataclass(frozen=True)
class ReportModel:
    title: str
    generated_at: datetime
    source: ReportSection
    summary: ReportSection
    insights: tuple[str, ...]
    categories: ReportTable | None
    anomalies: ReportTable | None
    periods: ReportTable | None
    chart_png: bytes | None
    language: str                            # "ru" | "en"
    depth: str                               # "brief" | "detailed"
```

Any section may be `None` or empty. Every writer must handle that without special-casing:
an analysis without a date column produces no chart and no period table, and the report is
still valid.

### Depth

| Section | Brief | Detailed |
|---|---|---|
| Header (file, period, rows, grouping) | yes | yes |
| Metrics | see below | all metrics |
| Insights | yes | yes |
| Chart | yes | yes |
| Categories | top 5 | all |
| Anomalies | top 8 | all found |
| Period table | no | yes |

Brief metrics are exactly: transactions, revenue, expenses, profit, and average daily profit.
Detailed metrics add the field counts, averages per transaction, period length, and average
daily revenue and expense. In amount-only analysis the revenue, expense, and profit rows are
replaced by a single amount row, matching what the UI already shows.

## 5. Insights

`insights.py` produces short sentences from formulas only. Each rule returns `None` when its
inputs are missing, so a sparse dataset simply yields fewer sentences.

Rules, in priority order:

1. Profit trend: last period against the previous one, as a percentage.
2. Profit trend over the whole range: first half against second half.
3. Category concentration: share of the largest category, when categories exist.
4. Anomaly summary: how many unusual periods, and the most extreme one.
5. Burn rate and cash gap: average daily expense, and a warning when average daily profit is
   negative, expressed as "at this rate the average day loses X".

Rule 5 is ML Phase 4 from `PROJECT_CONTEXT.md` in its first, formula-based form.

## 6. Fonts

ReportLab's built-in fonts cannot render Cyrillic, and category names in real data are
Cyrillic regardless of the chosen report language.

`DejaVuSans.ttf` ships inside matplotlib (`mpl-data/fonts/ttf/`), which is already a project
dependency. The PDF writer locates it through `matplotlib.get_data_path()` and registers it
with ReportLab. No font file is added to the repository and no network access is needed.

If the font cannot be found, the PDF writer raises a clear error naming the problem rather
than producing a document full of black boxes.

## 7. UI

An `Export Report...` button next to `Show Details...`, enabled only after a successful
analysis.

It opens a dialog with three choices: format, depth, language. Then a `QFileDialog` pre-filled
with the correct extension. The export itself runs in a `QThread` worker, matching the
existing preview and analysis workers, so a large detailed XLSX cannot freeze the window.

On success the status line reports the written path and offers to open the containing folder.

## 8. Error handling

- Target file locked or not writable: the worker reports the OS error, the window stays alive.
- No date column: the model carries no chart and no period table; every writer copes.
- No categories: the category table is absent, not empty-with-headers.
- Missing font: explicit error, no silent garbage output.
- An unexpected writer failure is caught by the worker and surfaced as text, never as a crash.

## 9. Testing

Unit tests, no Qt, run with pytest:

- `builder`: normal analysis, amount-only analysis, analysis without date or category.
- `builder`: brief versus detailed section presence.
- `insights`: each rule fires on crafted input, and each returns nothing on missing input.
- `strings`: Russian and English key sets are identical, guarding against a forgotten label.
- `chart_image`: output starts with the PNG signature; anomaly markers are drawn.
- writers: each produces a non-empty file with the right signature; XLSX opens in openpyxl,
  CSV parses in pandas, HTML contains the section titles, PDF starts with `%PDF`.

Manual verification uses two files:

- a generated synthetic transactional CSV with Russian headers, categories, and planted
  anomalies, which exercises the full path;
- `sample_data/Financial Distress.csv`, an 86-column numeric dataset with no date and no
  money columns, as a robustness case: the app must refuse gracefully, not crash.

## 10. Dependencies

One new dependency: `reportlab`. `PROJECT_CONTEXT.md` already names it as the preferred PDF
tool for the MVP because it packages cleanly into a Windows executable, so this is not a
deviation from project rules.

XLSX uses openpyxl, PNG uses matplotlib, CSV uses pandas, HTML is plain string building. All
are already present.

WeasyPrint and QtWebEngine were considered and rejected: both would bloat the future
PyInstaller build, WeasyPrint through GTK dependencies and QtWebEngine by roughly 130 MB.

## 11. Out of scope

- Translating the application UI.
- Report templates or user-configurable layout.
- Scheduled or batch export.
- Emailing or uploading reports anywhere.

## 12. Related work included here

Two items from the next roadmap phase are folded into this iteration because the export work
already touches the same code:

- Anomaly markers on the chart, drawn in `chart_image.py` and reused by the existing UI chart
  in `main_window.py`. Anomalies are already computed on exactly the points being plotted, so
  this is presentation only. One piece of work, two places it shows up.
- Burn rate and cash gap, as insight rule 5 in section 5 above. Pure formula, no new UI.

## 13. Deferred

Revenue and expense forecasting: moving average and linear trend, drawn as a dashed
continuation of the chart and added as a report section. Attempted only if the work above is
finished and verified; otherwise it moves to a later session untouched.
