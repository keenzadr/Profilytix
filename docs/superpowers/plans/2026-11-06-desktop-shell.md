# Desktop shell implementation plan

> Implement inline with superpowers:executing-plans; preserve existing working features.

**Goal:** Apply the approved five-page Qt design, a bottom-left theme switch and an icon-only collapsible sidebar to the working desktop app.

**Architecture:** A small reusable Sidebar and theme helpers in `app/ui/shell.py`;
the existing MainWindow remains the owner of file, analysis and export state.
Existing controls move into QStackedWidget pages; navigation does not rebuild them.

**Tech Stack:** Existing Python 3.12+, PySide6, pandas, Matplotlib, scikit-learn only.

**Spec:** `prototypes/UI_DESIGN.md`, `docs/NEXT_STEPS.md`, and the user's approved corrections.

## Constraints and decisions

- Native Windows desktop, standard frame, no new dependency or web/database/cloud layer.
- Original PyOneDark compatibility is still unverified. Use our existing Qt widgets,
  retaining the approved visual direction rather than importing untested template code.
- Work in the current checkout: `.git` is read-only in this environment; preserve prior prototype/docs changes.
- Theme/collapse preferences use existing local QSettings. No financial state is rebuilt on navigation/theme/collapse.
- Reports keep their own chart styling; only desktop Matplotlib colors follow the theme.
- No commit, push, or production packaging in this task.

## Review focus

State after file replacement/profile changes; cancellation from another page; missing dates
or monetary roles; native child dialogs in dark mode; narrow windows and RU/EN labels.

## Tasks

- [x] Add failing regression tests for five-page navigation, compact sidebar, preferences,
  global progress/cancel, language, categories and stale-result invalidation.
- [x] Implement Sidebar and theme helpers; apply user corrections to the disposable preview.
- [x] Move existing working controls into five pages, add real KPI/category views and concise
  mode help; preserve worker, selection, report and mapping behavior.
- [x] Run targeted and full pytest, render real working pages in both themes and compact mode,
  visually inspect, then obtain one independent code review and address important findings.
- [x] Update plan/status/manual checks and report the result and remaining native DPI limits.

## Execution record

Baseline suite started before implementation. Prior prototype renders and changes are preserved.

Baseline: 220 tests +25 subtests passed. First six shell tests failed on missing navigation,
preferences and dashboard; targeted checks then passed. Review fixes were reproduced by
failing tests: dark all-row QTableView and unlocked profiles during export. Both fixed.
Category tables bounded at100 rows with full results retained; regression verifies150 entries.
Final suite: 230 tests +25 subtests passed (27.98s). Compileall and diff checks passed.
Both theme renders and compact 1000×700/DPR1.5 checked; no horizontal page scrolling.
Native window, theme and collapse inspected; complete interactive import/export and real
cross-monitor DPI remain manual checks. No further code-review findings were deferred.
