# Next Sessions Plan

Date: 2026-08-16
Status: agreed
Branch: `main` is current; create a feature branch per session.

## Why this order

Every MVP success criterion in `PROJECT_CONTEXT.md` is met, so features are no longer the
binding constraint. Two things are:

- Nobody has clicked the running interface.
- The interface is English while the target user is a Russian-speaking small business owner.

The agreed direction combines shipping readiness with one more analytics feature: rule-based
transaction categorisation, ML Phase 2 in `PROJECT_CONTEXT.md`.

Categorisation earns its place here rather than being a guess, because it fills a real gap:
when a file has no category column at all, the report currently has no category breakdown.
Deriving categories from a description column removes that dead end.

Packaging comes last. It is the least uncertain work, and in-person user testing needs only a
Russian interface and a laptop, not an installer.

## Session A: usable by a stranger, roughly 3.5 hours

### A0. Manual pass — the founder, not the agent, about 25 minutes

Work through `docs/MANUAL_TESTING.md` and record what fails. Best done before the session
starts, so the session opens with fixes rather than waiting.

An agent cannot click a desktop window. This step cannot be delegated.

The first line of that checklist is still open: whether the window appears at all. On
2026-08-15 the process ran and exited with code 0 printing nothing, which is what a closed
window looks like and also what an immediate exit looks like.

### A1. Fix what the pass found, about 60 minutes

Unknown until A0 runs. Budgeted generously because UI defects in never-exercised code tend to
arrive in clusters. If A0 comes back clean, this time moves to A3.

### A2. Russian interface, about 75 minutes

**Files:** create `app/ui/strings.py`; modify `app/ui/main_window.py`,
`app/ui/export_dialog.py`; test `tests/test_ui_strings.py`.

Mirror the pattern already proven in `app/reports/strings.py`: one table per language, a
`label(language, key)` lookup with English fallback, and a test asserting both tables carry
identical keys. That test is what stops a half-translated build.

Russian is the default. The language lives in `QSettings` beside the existing last-directory
setting, with a switch in the window.

Scope note: this translates the interface only. Log messages, code, and documentation stay
English, matching the existing convention.

Watch for: `main_window.py` builds several strings by concatenation and f-string, for example
in `_format_metrics()` and `_format_anomaly_short()`. Those need parameterised templates, not
glued fragments, or Russian grammar will come out wrong.

### A3. Rule-based transaction categorisation, about 75 minutes

**Files:** create `app/ml/categorization.py`, `tests/test_categorization.py`; modify
`app/analytics/metrics.py`, `app/ui/main_window.py`, `app/reports/builder.py`.

Canonical categories from `PROJECT_CONTEXT.md`: Marketing, Sales, Rent, Payroll, Inventory,
Other.

```python
CATEGORY_RULES: dict[str, tuple[str, ...]]   # canonical category -> keywords, RU and EN
def categorize_descriptions(values: pd.Series) -> pd.Series
```

Matching reuses `normalize_text()` from `app/analytics/column_detection.py`, which already
handles camelCase, separators and `ё`. Anything unmatched becomes Other rather than being
dropped.

Wiring: add an optional `description` role to `SelectedColumns` and to the column dialog.
Explicit beats magic here — deriving categories silently from a high-cardinality category
column would surprise the user. When a description column is selected, the derived breakdown
appears alongside the existing category summary in metrics and in reports.

Tests: each rule fires on its keywords; unmatched text lands in Other; an empty or absent
column returns an empty result rather than raising; Russian and English descriptions both
match.

### A4. Documentation and commits, about 20 minutes

Update `README.md`, `docs/HANDOFF.md`, and `docs/MANUAL_TESTING.md` with steps for the new
language switch and the categorisation role.

## Session B: shippable, roughly 2 hours

### B1. PyInstaller

One-folder build first; one-file only if startup time is acceptable. Expect hidden-import
problems from PySide6, matplotlib, polars and scikit-learn together, and a bundle in the
hundreds of megabytes.

Two project-specific traps:

- The PDF writer reads `DejaVuSans.ttf` through `matplotlib.get_data_path()`. That path
  differs inside a bundle and must be verified, or PDF export breaks only in the packaged
  build.
- `app/reports/chart_image.py` imports `FigureCanvasAgg` directly. Confirm the Agg backend is
  collected.

Smoke test the built executable against `docs/MANUAL_TESTING.md`, not just against launching.

### B2. Installer and first-run experience

Inno Setup script. Consider shipping `transactions_sample.csv` inside the installer so a new
user has something to open immediately, rather than facing an empty window.

### B3. Put it in front of three to five real small business owners

Watch, do not explain. Where they hesitate is the backlog.

## Deferred, deliberately

- Cancel and real progress for long-running analysis.
- Forecast shown in the main window panel, not only on the chart and in reports.
- Category-aware anomaly summaries.
- Saved reusable column-mapping profiles.
- Supervised categorisation with CatBoost or LightGBM, once rule-based output can be compared
  against real labelled files.
- Blank header cells surfacing as an unselectable `''` entry in the column dialog. Cosmetic;
  details in `docs/HANDOFF.md`.
