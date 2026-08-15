"""Report labels in Russian and English.

The application UI stays English; only report content is translated. Both
tables must carry the same keys, which `tests/test_report_strings.py` enforces
so a label added to one language cannot silently miss the other.
"""

from __future__ import annotations


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("ru", "en")

LABELS: dict[str, dict[str, str]] = {
    "ru": {
        # Document
        "report_title": "Финансовый отчёт",
        "generated_at": "Отчёт создан",
        # Section titles
        "section_source": "Источник",
        "section_summary": "Показатели",
        "section_insights": "Выводы",
        "section_categories": "Категории",
        "section_anomalies": "Аномалии",
        "section_periods": "Динамика по периодам",
        "section_chart": "График",
        # Source rows
        "source_file": "Файл",
        "source_period": "Период",
        "source_transactions": "Операций",
        "source_grouping": "Группировка",
        # Metric rows
        "metric_transactions": "Операций",
        "metric_revenue": "Выручка",
        "metric_expenses": "Расходы",
        "metric_profit": "Прибыль",
        "metric_amount": "Сумма",
        "metric_average_revenue": "Средняя выручка на операцию",
        "metric_average_expense": "Средний расход на операцию",
        "metric_period_days": "Дней в периоде",
        "metric_average_daily_revenue": "Средняя дневная выручка",
        "metric_average_daily_expense": "Средний дневной расход",
        "metric_average_daily_profit": "Средняя дневная прибыль",
        "metric_revenue_fields": "Колонок выручки",
        "metric_expense_fields": "Колонок расходов",
        "metric_amount_fields": "Колонок суммы",
        "metric_category_fields": "Колонок категорий",
        # Table headers
        "header_category": "Категория",
        "header_transactions": "Операций",
        "header_revenue": "Выручка",
        "header_expenses": "Расходы",
        "header_profit": "Прибыль",
        "header_period": "Период",
        "header_amount": "Сумма",
        "header_indicator": "Показатель",
        "header_value": "Значение",
        "header_kind": "Тип",
        "header_severity": "Значимость",
        "header_baseline": "Норма",
        "header_rule": "Правило",
        # Anomaly vocabulary
        "anomaly_spike": "всплеск",
        "anomaly_drop": "провал",
        "severity_high": "высокая",
        "severity_medium": "средняя",
        # Grouping names
        "grouping_hour": "по часам",
        "grouping_day": "по дням",
        "grouping_week": "по неделям",
        "grouping_month": "по месяцам",
        "grouping_year": "по годам",
        # Insight sentences
        "insight_profit_change_up": "Прибыль за последний период выросла на {percent}% относительно предыдущего.",
        "insight_profit_change_down": "Прибыль за последний период упала на {percent}% относительно предыдущего.",
        "insight_half_trend_up": "Во второй половине периода прибыль выше, чем в первой, на {percent}%.",
        "insight_half_trend_down": "Во второй половине периода прибыль ниже, чем в первой, на {percent}%.",
        "insight_category_share": "На категорию «{name}» приходится {percent}% оборота.",
        "insight_anomalies": "Найдено необычных периодов: {count}. Самый заметный — {kind} по показателю «{series}» {date}.",
        "insight_burn_rate": "Средний расход составляет {value} в день.",
        "insight_cash_gap": "Средний день закрывается в минус на {value}. При таком темпе есть риск кассового разрыва.",
        # Fallbacks
        "not_available": "нет данных",
        "no_insights": "Недостаточно данных для выводов.",
        "uncategorized": "Без категории",
    },
    "en": {
        # Document
        "report_title": "Financial report",
        "generated_at": "Generated at",
        # Section titles
        "section_source": "Source",
        "section_summary": "Metrics",
        "section_insights": "Insights",
        "section_categories": "Categories",
        "section_anomalies": "Anomalies",
        "section_periods": "Periods",
        "section_chart": "Chart",
        # Source rows
        "source_file": "File",
        "source_period": "Period",
        "source_transactions": "Transactions",
        "source_grouping": "Grouping",
        # Metric rows
        "metric_transactions": "Transactions",
        "metric_revenue": "Revenue",
        "metric_expenses": "Expenses",
        "metric_profit": "Profit",
        "metric_amount": "Amount",
        "metric_average_revenue": "Average revenue per transaction",
        "metric_average_expense": "Average expense per transaction",
        "metric_period_days": "Days in period",
        "metric_average_daily_revenue": "Average daily revenue",
        "metric_average_daily_expense": "Average daily expense",
        "metric_average_daily_profit": "Average daily profit",
        "metric_revenue_fields": "Revenue fields",
        "metric_expense_fields": "Expense fields",
        "metric_amount_fields": "Amount fields",
        "metric_category_fields": "Category fields",
        # Table headers
        "header_category": "Category",
        "header_transactions": "Transactions",
        "header_revenue": "Revenue",
        "header_expenses": "Expenses",
        "header_profit": "Profit",
        "header_period": "Period",
        "header_amount": "Amount",
        "header_indicator": "Indicator",
        "header_value": "Value",
        "header_kind": "Kind",
        "header_severity": "Severity",
        "header_baseline": "Baseline",
        "header_rule": "Rule",
        # Anomaly vocabulary
        "anomaly_spike": "spike",
        "anomaly_drop": "drop",
        "severity_high": "high",
        "severity_medium": "medium",
        # Grouping names
        "grouping_hour": "by hour",
        "grouping_day": "by day",
        "grouping_week": "by week",
        "grouping_month": "by month",
        "grouping_year": "by year",
        # Insight sentences
        "insight_profit_change_up": "Profit in the last period rose {percent}% against the one before it.",
        "insight_profit_change_down": "Profit in the last period fell {percent}% against the one before it.",
        "insight_half_trend_up": "Profit in the second half of the range is {percent}% higher than in the first.",
        "insight_half_trend_down": "Profit in the second half of the range is {percent}% lower than in the first.",
        "insight_category_share": "Category \"{name}\" accounts for {percent}% of turnover.",
        "insight_anomalies": "Unusual periods found: {count}. The most notable is a {kind} in {series} on {date}.",
        "insight_burn_rate": "Average expense runs at {value} per day.",
        "insight_cash_gap": "The average day closes {value} short. At this rate there is a cash gap risk.",
        # Fallbacks
        "not_available": "not available",
        "no_insights": "Not enough data for insights.",
        "uncategorized": "Uncategorized",
    },
}


# Anomaly detection labels its series in English for the UI. Reports translate
# them from the series key instead, so a Russian report does not say
# "spike in Expenses".
SERIES_LABEL_KEYS = {
    "revenue": "header_revenue",
    "expenses": "header_expenses",
    "profit": "header_profit",
    "amount": "header_amount",
}


def label(language: str, key: str) -> str:
    """Return one label, falling back to English and then to the key itself."""
    table = LABELS.get(language)
    if table is not None and key in table:
        return table[key]

    fallback = LABELS[DEFAULT_LANGUAGE]
    return fallback.get(key, key)


def series_label(language: str, series_key: str, fallback: str = "") -> str:
    """Return a localised name for one financial series."""
    label_key = SERIES_LABEL_KEYS.get(series_key)
    if label_key is None:
        return fallback or series_key
    return label(language, label_key)
