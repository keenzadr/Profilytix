# Complete the original desktop roadmap

User authorization: implement as much of the previously reviewed old plan as possible.
Sources: PROJECT_CONTEXT.md, AGENTS.md, 2026-08-16-next-sessions.md.

## Constraints and decisions

- Python 3.12+, PySide6 desktop, pandas processing, scikit-learn ML; no web, database, cloud, auth, payments or LLM API.
- Preserve the existing preview, metrics, charts and all five report formats.
- Work on a feature branch in the current checkout; preserve the pre-existing MANUAL_TESTING.md edits.
- Russian is the default UI; English remains selectable and the preference is local QSettings.
- Explicit description selection enables keyword categorisation. Existing categories remain independently available.
- Cash runway requires an explicit user-supplied current cash balance; never infer it from net profit.
- Add an optional Isolation Forest method alongside the existing rule method, deterministic and guarded for short/constant inputs.
- Use bounded pages to view all table rows without building millions of Qt cells.
- Cancellation is cooperative; never terminate a running QThread. CSV progress is measured from bytes read, Excel progress from processed rows where available.
- Packaging: one-folder PyInstaller build, per-user Inno Setup installer, offline sample included. Build and smoke-test if tools are available; record exact blockers otherwise.
- Real customer interviews and trained categorisation require people/labelled data and remain explicitly outstanding.

## Tasks and verification

- [x] 1. Baseline: 132 tests passed with repository-local pytest temporary directory.
- [x] 2. Localisation: label tables, RU default, runtime language switch, dialogs and dynamic summaries translated. Tests: widget text, retained state, persistence, label parity.
- [x] 3. Financial analysis: RU/EN keyword categories from selected descriptions, preserved explicit category breakdown, cash runway from explicit balance, optional Isolation Forest, category context for anomalies. Tests: noisy/missing/short data, numeric results and report integration.
- [x] 4. File handling: normalized unique blank headers and consistent selected-column loading, chunked cancellable loading with progress, bounded table pages. Tests: mixed/duplicate/headerless/CP1251 files, real cancellation and page contents.
- [x] 5. UI integration: description selection, saved reusable mappings, cash balance input, anomaly method, forecast summary, cancellation/progress and full table browser. Test complete workflows offscreen, invalid profile/schema inputs and cancellation cleanup.
- [x] 6. Packaging sources: reproducible build requirements/spec/script and Inno Setup, source checks for fonts/Agg/sample resources. Actual frozen build blocked by unavailable build tools/package index; see packaging/BUILD_STATUS.md.
- [x] 7. Review: independent code review, 220 tests and 25 subtests passed, compile/whitespace checks passed; native desktop startup inspected; README/HANDOFF/manual checks updated with evidence and remaining work.

## Review focus

- Switching language must preserve loaded data/results and not translate user-provided cell values.
- Generated header names must never select the wrong physical column.
- Cancelled workers must not publish stale partial results or be destroyed while running.
- Missing balance/date/money inputs must not produce invented runway or profit.
- Packaged app must export Cyrillic PDF and charts without network access.

## Execution record

Initial checkout: main at 02e8c12; pre-existing change in docs/MANUAL_TESTING.md.
Initial pytest: 103 passed, 29 setup errors because the sandbox default temporary directory is unwritable; rerun with explicit basetemp.
Environment: .git is read-only (branch creation failed); changes remain in the current checkout, no commits or merges will be attempted. Use repository-local .pytest-tmp-* for tests (C:/workspace does not exist).
Review: fixed sparse category context (no quadratic dense pivot, cancellation checkpoints) and suppressed cash estimates when nonzero money transactions lack valid dates. Global totals are preserved. Native startup/Russian controls visually confirmed; complete interactive file/export checklist remains open.
Final: reproduced and fixed native QThread cleanup/deletion deadlock for paged browsing and all three main-window worker types. Slow native-finished callbacks regressions run in bounded child processes. Final command: .venv/Scripts/python.exe -m pytest tests -q --basetemp .pytest-tmp-release-check --tb=short -> 220 passed, 25 subtests passed in 23.90s. compileall app packaging and git diff --check succeeded.
