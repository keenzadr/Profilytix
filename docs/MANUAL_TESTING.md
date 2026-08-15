# Manual Testing Checklist

Last updated: 2026-08-16

Everything below is unverified by hand. The automated suite covers the report layer, the
export dialog, and the export worker, and the main window builds under the offscreen Qt
platform. Nobody has driven the real interface.

Expected numbers were produced programmatically on the same code. A mismatch therefore points
at the UI layer, which is exactly the part tests do not reach.

## Setup

```bash
cd "C:/Users/bahil/Desktop/prof/Profilytix"; ./.venv/Scripts/python.exe -m app.main
```

The venv matters. The system Python is 3.11 with no dependencies installed and the
application will not start on it.

If `sample_data/transactions_sample.csv` is missing, regenerate it:

```bash
cd "C:/Users/bahil/Desktop/prof/Profilytix"; ./.venv/Scripts/python.exe scripts/make_sample_data.py
```

## 0. Launch

- [ ] A window titled `Profilytix` appears and stays open.

This one is genuinely open. On 2026-08-15 the process was started in the background, ran, and
exited with code 0 printing nothing at all. That is what closing a window looks like, but it
is also what an immediate exit looks like. Confirm the window really appears.

## 1. Russian CSV, automatic detection

File: `sample_data/transactions_sample.csv`. Load it, then click `Analyze File` without
opening the column dialog.

- [ ] File name, size, row count, encoding and delimiter are shown.
- [ ] The first 100 rows appear in the table.
- [ ] No warning about uncertain columns appears; all four are detected exactly.
- [ ] Revenue reads `16 302 389.00`
- [ ] Expenses read `12 293 093.00`
- [ ] Profit reads `4 009 296.00`
- [ ] Period reads `2026-01-01 - 2026-05-31`
- [ ] `Show Details...` opens and lists top categories by profit.
- [ ] Anomaly summary shows 3 found.

Switch grouping to `Week`. Monthly grouping yields only 5 points, and forecasting declines
below 6 periods by design.

- [ ] Three dashed continuations appear at the right edge, each matching its series colour.
- [ ] Red triangles mark anomalies: pointing down on spikes, up on drops.
- [ ] The legend lists `Forecast` and `Anomaly`.
- [ ] Hovering shows a vertical guide, the date, and exact values.
- [ ] The x-axis stays within 2026. Any sign of 1970 is a regression.
- [ ] `Open Fullscreen` shows the same markers and forecast.
- [ ] Splitters resize the table, metrics, and chart areas.

## 2. English Excel, the case that used to be wrong

File: `sample_data/Product-Sales-Region.xlsx`.

Before analysing, open `Configure Columns...`:

- [ ] Date is `Date`
- [ ] Amount is `TotalPrice`, **not** `UnitPrice`
- [ ] Expenses is `ShippingCost`
- [ ] Category is `Region`
- [ ] A message asks the user to confirm the columns.

Close the dialog without changing anything and click `Analyze File`:

- [ ] Profit reads `4 338 731.49`
- [ ] Revenue reads `4 379 992.43`

Seeing `448 240.42` anywhere means the old detection logic is running.

- [ ] Grouping by `Month` gives 30 points and 2 anomalies.
- [ ] Categories are regions: North, East, West, Central.

## 3. Export

Run from either analysed file.

- [ ] `Export Report...` is hidden before the first analysis and appears after it.
- [ ] The dialog offers PDF, Excel, HTML, PNG, CSV, a brief/detailed choice, and RU/EN.
- [ ] The save dialog pre-fills the right extension and the source file's name.
- [ ] The window stays responsive while the report is written.
- [ ] The status line reports the saved path.
- [ ] `Open Folder` opens the containing folder.

Then open each file:

- [ ] **PDF** renders Cyrillic. Black boxes instead of letters mean the font was not found.
- [ ] **PDF detailed** contains a per-period table that brief does not.
- [ ] **Excel** has separate sheets for metrics, forecast, categories, anomalies, and chart.
- [ ] **Excel** places the chart on its own sheet rather than over data cells.
- [ ] **HTML** opens in a browser with the chart inside it. Disconnect from the network and
      reopen: it must look identical.
- [ ] **PNG** contains only the chart.
- [ ] **CSV** opens in Excel by double-click with readable Cyrillic and no import wizard.
- [ ] Exporting in English produces English labels throughout.

## 4. Refusals and edge cases

- [ ] `sample_data/Financial Distress.csv` loads, warns about uncertain columns, and refuses
      analysis with a readable message rather than crashing.
- [ ] `sample_data/raw_partner_headlines.csv` (382 MB) previews in about a second and refuses
      analysis: it has no money column.
- [ ] With no date column selected, PNG export is greyed out in the format list.
- [ ] Exporting onto a file that is open in Excel reports the problem and leaves the window
      alive.
- [ ] Loading a second file clears the previous metrics, chart, and export button.

## Reporting a failure

Note what was clicked, what appeared, and what was expected. The numbers above are known
good, so any difference is a UI defect rather than an analysis one.
