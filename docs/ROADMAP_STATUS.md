# Profilytix roadmap status — 2026-11-06

The current forward plan and Russian feature summary are in `docs/NEXT_STEPS.md`.
In-app mode help is the first planned task and is not implemented yet.
Approved UI direction: evaluate PyOneDark on Python 3.12+/current PySide6, agree a mockup,
then migrate the existing features into five sections using Actual Budget as a visual
reference. Qt-Material is the fallback. This is planning only; no UI template was installed.

## Implemented

| Original task | Current result |
|---|---|
| Local Windows MVP | Excel/CSV, preview, mappings, metrics, charts, rules, five exports preserved |
| Russian UI | RU default, EN switch, persistent choice, source data preserved |
| Transaction categorisation | Explicit description selection, local RU/EN rules, six categories, separate from supplied dimensions |
| Isolation Forest | Optional deterministic method, eight-period/constant/nonfinite guards |
| Simple forecasting | Existing moving average/trend plus numeric next-period summary in the panel |
| Cash risk | Explicit current balance, daily net burn, runway, 30-day estimate; no estimates for undated money rows |
| Category context | Sparse largest directional category movement for each anomaly, shown in details/reports |
| Mapping profiles | Save/apply/delete via existing local QSettings; validate all columns before applying |
| Long analysis | Cooperative cancellation, measured CSV bytes/Excel rows, safe close; no forced thread termination |
| All-row viewing | Bounded 1,000-row pages loaded in a background worker, same schema as analysis |
| Header regression | Blank/duplicate/generated names consistently map to physical indexes for CSV/XLSX/XLS |
| Packaging sources | One-folder PyInstaller spec, per-user Inno Setup, offline demo, logging, dependency locks, smoke checks |

All processing remains local Python/PySide6/pandas/scikit-learn. No database, cloud, auth,
payments or LLM API was introduced.

## Remaining

- Actual `.exe`/installer build and frozen validation: blocked here by missing PyInstaller,
  unavailable PyPI DNS and missing Inno Setup. See `packaging/BUILD_STATUS.md`.
- Complete interactive import/analysis/export checks in `docs/MANUAL_TESTING.md`; native
  launch and Russian controls have been visually inspected, the full click-through has not.
- ML model comparison and integration planning are now a priority; candidate models and
  evaluation steps are recorded in docs/NEXT_STEPS.md. No new model/dependency has been installed.

## Practical limits

- Cancellation is checked between loading chunks and analysis stages, not inside every
  pandas/scikit-learn call. Closing waits for background work to end safely.
- Paging retains bounded display rows but rescans preceding records for later pages. XLS
  decoding uses xlrd, which loads its worksheet internally.
- The default Python CSV cell-size limit can reject exceptionally large text fields in the
  page browser; this minor review observation is deferred.
- A forecast/runway is an estimate from past data; the entered balance is not inferred from profit.

## Verification

Initial unchanged suite: 132 passed using a repository-local pytest temporary directory.
New behavior has regression tests for RU/EN matching and UI persistence, profiles/schema
validation, CSV/XLSX/XLS headers/pages/cancellation, optional ML, cash edge cases and report
tables. Independent review found two Important issues (dense category pivot and undated cash
baseline); both received failing regression tests before fixes. Final suite evidence is
recorded below.

Final verification (2026-11-06):

- `.venv/Scripts/python.exe -m pytest tests -q --basetemp .pytest-tmp-release-check --tb=short`:
  **220 passed, 25 subtests passed in 23.90 seconds**.
- `.venv/Scripts/python.exe -m compileall app packaging -q`: passed.
- `git diff --check`: passed (only repository CRLF conversion notices).
- A native thread deletion race was reproduced with slow native-finished callbacks. Browsing,
  preview, analysis and export now join native cleanup before deleting their QThreads.
  Regression tests use child-process timeouts to avoid hanging the whole suite.

The existing MANUAL_TESTING.md path/environment edits were preserved. Git metadata was
read-only, so this session made no commits, branch changes, merges or pushes.
