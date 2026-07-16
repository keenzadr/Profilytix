# PROJECT_CONTEXT.md

# Project Name

Profilytix

The name combines "Profit" and "Analytics".

---

# Product Vision

Profilytix is a Windows desktop application for small businesses that turns Excel/CSV financial files into clear business analytics, anomaly detection, forecasts, and PDF reports.

The product should feel like a local AI/ML financial analyst for small business owners.

Primary workflow:

Excel/CSV file → automatic analysis → metrics → anomalies → insights → PDF report.

---

# Core Positioning

Profilytix is not accounting software.

Profilytix is an analytics layer for business owners who already keep their financial data in spreadsheets.

The first product version must work locally on the user's computer.

No website.
No Telegram bot.
No cloud infrastructure.
No authentication.
No database in MVP unless absolutely necessary.
No LLM API in the first version.

---

# Founder Context

Solo founder.

Background:
- Data Analyst
- SQL
- PostgreSQL
- Airflow
- ETL
- BI / Analytics
- Experience with business metrics and reporting

Development style:
- AI-assisted coding
- Codex is the primary development tool
- Keep the project simple
- Prefer working features over perfect architecture
- Avoid overengineering

---

# Main Hypothesis

Small businesses often store sales, expenses, and profit data in Excel files.

They usually struggle to quickly understand:
- how much they earned
- how much they spent
- whether profit is growing or falling
- which days or categories look suspicious
- whether a cash gap may happen soon
- what the next month may look like

Profilytix should make those answers understandable without requiring BI, accounting knowledge, or SQL.

---

# Target Users

Initial target users:
- small business owners
- beauty salons
- small stores
- local service businesses
- cafes
- marketplace sellers
- accountants who work with Excel files

Primary platform:
- Windows desktop

---

# MVP Scope

The MVP must allow the user to:

1. Open the desktop application.
2. Upload an Excel or CSV file.
3. Preview the loaded table.
4. Automatically detect important columns:
   - date
   - revenue
   - expenses
   - category
5. Calculate core financial metrics.
6. Detect simple anomalies.
7. Display charts.
8. Export a PDF report.

---

# Version 1 Features

## 1. Desktop Application

Technology:
- Python 3.12+
- PySide6

The interface should be simple:

- file upload button
- table preview
- detected column section
- metrics section
- charts section
- anomaly section
- PDF export button

Design is not a priority in the first version.

Stability and understandable results are more important.

---

## 2. File Import

Supported formats:
- .xlsx
- .xls
- .csv

Libraries:
- pandas
- openpyxl

CSV should support common encodings:
- utf-8
- utf-8-sig
- cp1251

For Excel files:
- first version may read only the first sheet
- sheet selection can be added later

---

## 3. Table Preview

After loading a file, show:
- file name
- number of rows
- number of columns
- column names
- first 100 rows

The application must not crash on:
- empty files
- unsupported files
- broken files
- wrong encodings
- missing columns

---

# Column Detection

Create a simple keyword-based column detector.

The detector should support Russian and English column names.

## Date column keywords

Examples:
- date
- дата
- дата операции
- день
- created_at
- operation_date

## Revenue column keywords

Examples:
- revenue
- income
- sales
- выручка
- доход
- продажи
- поступление
- приход

## Expense column keywords

Examples:
- expense
- cost
- spend
- расходы
- расход
- затраты
- списание
- уход
- оплата

## Category column keywords

Examples:
- category
- категория
- тип
- статья
- группа
- назначение

---

# Column Detection Output

Expected output example:

```python
{
    "date_column": "Дата операции",
    "revenue_column": "Сумма дохода",
    "expense_column": "Сумма расхода",
    "category_column": "Категория",
    "confidence": {
        "date_column": 0.9,
        "revenue_column": 0.8,
        "expense_column": 0.8,
        "category_column": 0.7
    }
}
```

Confidence logic can be simple:
- exact match: 1.0
- partial match: 0.7
- not found: 0.0

---

# Data Cleaning

## Numeric Cleaning

Create a function:

```python
clean_numeric_column()
```

It should handle values like:

- 100000
- 100 000
- 100 000 ₸
- 100,000
- 100.000
- "100 000 KZT"

For MVP, the function should be practical rather than perfect.

---

## Date Cleaning

Create a function:

```python
clean_date_column()
```

It should handle common formats:

- 2026-06-01
- 01.06.2026
- 01/06/2026

Use:

```python
pd.to_datetime(..., errors="coerce", dayfirst=True)
```

---

# Basic Metrics

Calculate:

- total revenue
- total expenses
- total profit
- transaction count
- average revenue
- average expense

If a date column is detected, also calculate:

- date_min
- date_max
- period_days
- average_daily_revenue
- average_daily_expense
- average_daily_profit

Example UI output:

```text
Выручка: 310 000 ₸
Расходы: 210 000 ₸
Прибыль: 100 000 ₸
Период: 01.06.2026 — 03.06.2026
Средняя дневная прибыль: 33 333 ₸
```

---

# Charts

Display basic charts:

- revenue over time
- expenses over time
- profit over time

Preferred:
- Plotly

Alternative:
- Matplotlib

For MVP, Matplotlib may be simpler inside PySide6.

---

# Classical ML Roadmap

The project should focus on classical ML, not custom LLM training.

No custom GPT-like model.
No foundation model development.
No GPU-heavy training in MVP.

---

## ML Phase 1: Anomaly Detection

Goal:

Detect unusual financial activity.

Examples:
- abnormal expenses
- abnormal revenue spikes
- abnormal profit drops
- days where profit is unusually low

Start with:
- IQR rules
- Z-score rules

Then add:
- IsolationForest from scikit-learn

Library:
- scikit-learn

---

## ML Phase 2: Transaction Categorization

Input examples:
- Instagram Ads
- Kaspi QR
- Rent
- Salary
- Закуп товара
- Аренда
- Реклама

Output categories:
- Marketing
- Sales
- Rent
- Payroll
- Inventory
- Other

First implementation:
- rule-based categorization

Future:
- supervised classification
- CatBoost
- LightGBM

---

## ML Phase 3: Forecasting

Goals:
- revenue forecast
- expense forecast
- profit forecast

Potential tools:
- simple moving average
- linear regression
- CatBoost
- XGBoost
- Prophet

Do not start with complex forecasting.

---

## ML Phase 4: Cash Flow Risk

Examples:
- "At the current burn rate, money will last for 19 days."
- "There is a risk of a cash gap next month."

First implementation:
- formulas and rules

Future:
- ML-based risk estimation

---

# Non Goals

Do NOT build:

- accounting software
- ERP
- CRM
- inventory management
- payroll system
- tax reporting system
- payment processing
- online dashboards
- multi-user accounts

Profilytix is a local analytics and reporting tool.

---

# Tech Stack

## Language

Python 3.12+

## Desktop UI

PySide6

## Data Processing

pandas
numpy
openpyxl

## ML

scikit-learn

Future:
- CatBoost
- Prophet
- XGBoost

## Charts

Matplotlib or Plotly

## PDF

Evaluate:
- ReportLab
- WeasyPrint

For MVP, ReportLab may be easier to package into a Windows desktop app.

## Packaging

Future:
- PyInstaller
- Inno Setup

Packaging is not required in the first 3 days.

---

# Suggested Folder Structure

```text
profilytix/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── main_window.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── file_loader.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── column_detection.py
│   │   └── metrics.py
│   ├── ml/
│   │   ├── __init__.py
│   │   └── anomaly_detection.py
│   ├── reports/
│   │   ├── __init__.py
│   │   └── pdf_report.py
│   └── utils/
│       ├── __init__.py
│       └── formatting.py
├── sample_data/
├── tests/
├── docs/
├── PROJECT_CONTEXT.md
├── requirements.txt
├── README.md
└── .gitignore
```

---

# First 3 Days Plan

## Day 1: Project Skeleton

Goal:
- create repo
- create folder structure
- create virtual environment
- create minimal PySide6 app
- app opens a main window
- main window has a "Load Excel/CSV" button
- no real file loading yet

Expected result:
- `python -m app.main` opens the desktop application

Commit:
- `Initial desktop app skeleton`

---

## Day 2: File Loading and Table Preview

Goal:
- implement Excel/CSV loading
- display first 100 rows
- display file info
- handle loading errors

Requirements:
- .xlsx
- .xls
- .csv
- UTF-8 / UTF-8-SIG / CP1251 for CSV

Expected result:
- user can load a file and see its table preview

Commit:
- `Add Excel and CSV file loading`

---

## Day 3: Column Detection and Metrics

Goal:
- detect date/revenue/expense/category columns
- clean numeric columns
- clean date columns
- calculate basic metrics
- display detected columns and metrics in UI

Expected result:
- user loads Excel/CSV and sees:
  - detected columns
  - revenue
  - expenses
  - profit
  - date range
  - average daily profit

Commit:
- `Add column detection and basic metrics`

---

# Week 1 Goal

By the end of Week 1, the app should support:

- file loading
- table preview
- column detection
- basic financial metrics
- simple charts
- simple anomaly detection
- PDF export

No additional features.

---

# Success Criteria For MVP Prototype

User can:

1. Launch Profilytix.
2. Upload Excel or CSV.
3. See table preview.
4. See detected columns.
5. See financial summary.
6. See simple anomaly report.
7. Export PDF.

This is a successful first prototype.

---

# Development Principles

1. Keep code readable.
2. Keep modules small.
3. Avoid unnecessary abstractions.
4. Avoid premature database usage.
5. Prefer local processing.
6. Prefer simple rules before complex ML.
7. Do not add web features.
8. Do not add authentication.
9. Do not add payments.
10. Do not add cloud infrastructure.

---

# First Prompt For Codex

Use this prompt after placing this file in the repository root:

```text
Read PROJECT_CONTEXT.md completely and use it as the source of truth.

Create the initial project skeleton for a Python 3.12+ Windows desktop application called Profilytix.

Requirements:
- Use PySide6.
- Create the folder structure described in PROJECT_CONTEXT.md.
- Create a minimal runnable desktop app.
- The app should open a main window with:
  - title: Profilytix
  - button: Load Excel/CSV
  - empty area for future table preview
  - empty area for future metrics
- Do not implement file loading yet.
- Add clear docstrings and TODO comments.
- Add requirements.txt if missing.
- Add README.md with setup and run instructions.
- Add .gitignore for Python, venv, IDE files, cache files and local data.

After implementation, provide:
1. File tree.
2. How to run the app.
3. What was implemented.
4. What should be done next.
```

---

# Important Notes For Codex

Do not create a web application.

Do not add FastAPI, Flask, Django, React, Next.js, or any web stack.

Do not add authentication.

Do not add a database unless the user explicitly asks.

Do not use LLM API in the first version.

Do not overengineer architecture.

Focus on building a working local Windows desktop app.
