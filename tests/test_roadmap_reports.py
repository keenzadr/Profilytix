from datetime import datetime

import pandas as pd

from app.analytics.metrics import SelectedColumns, prepare_financial_data, calculate_basic_metrics_from_prepared
from app.analytics.time_series import calculate_time_series
from app.ml.anomaly_detection import detect_financial_anomalies
from app.reports.builder import ReportRequest, build_report


def source():
    data = pd.DataFrame({'date':pd.date_range('2026-01-01', periods=10), 'a':[-10] * 10, 'desc':['Rent'] * 10, 'region':['North'] * 10})
    prepared = prepare_financial_data(data, SelectedColumns(date='date', amount='a', description='desc', category='region'))
    metrics = calculate_basic_metrics_from_prepared(prepared)
    series = calculate_time_series(prepared, 'day', 'monday')
    return metrics, series, detect_financial_anomalies(series)


def test_derived_categories_and_cash_reach_all_table_writers():
    metrics, series, anomalies = source()
    report = build_report(metrics, series, anomalies, ReportRequest('test.csv', include_chart=False), cash_balance=200)
    assert report.categories.rows[0][0] == 'North'
    assert report.derived_categories.rows[0][0] == 'Аренда'
    assert report.derived_categories in report.tables()
    assert any('20' in value for key, value in report.summary.rows if key == 'Запас денег, дней')
    assert any('текущего остатка' in line for line in report.insights)


def test_missing_cash_does_not_create_runway():
    metrics, series, anomalies = source()
    report = build_report(metrics, series, anomalies, ReportRequest('test.csv', language='en', include_chart=False))
    assert not any(key == 'Cash runway, days' for key, _ in report.summary.rows)


def test_category_anomaly_context_names_largest_directional_change():
    from app.analytics.anomaly_context import add_category_context
    data = pd.DataFrame({'date':list(pd.date_range('2026-01-01', periods=10)) * 2,
        'expenses':[10] * 9 + [1000] + [20] * 10, 'category':['Rent'] * 10 + ['Other'] * 10})
    prepared = prepare_financial_data(data, SelectedColumns(date='date', expense='expenses', category='category'))
    series = calculate_time_series(prepared, 'day', 'monday')
    anomalies = add_category_context(detect_financial_anomalies(series), prepared, 'day', 'monday')
    assert anomalies.anomalies[0].category == 'Rent'
    report = build_report(calculate_basic_metrics_from_prepared(prepared), series, anomalies, ReportRequest('x', include_chart=False))
    assert 'Rent' in report.anomalies.rows[0]


def test_undated_money_cannot_produce_cash_runway():
    from app.analytics.cash_flow import calculate_cash_flow
    data = pd.DataFrame({'date':['2026-01-01','2026-01-10','bad'], 'revenue':[100,100,0], 'expenses':[0,0,10000]})
    prepared = prepare_financial_data(data, SelectedColumns(date='date', revenue='revenue', expense='expenses'))
    metrics = calculate_basic_metrics_from_prepared(prepared)
    cash = calculate_cash_flow(metrics, 1000)
    assert metrics.total_profit == -9800
    assert cash.runway_days is None
    assert cash.projected_balance_30_days is None
    series = calculate_time_series(prepared, 'day', 'monday')
    report = build_report(metrics, series, detect_financial_anomalies(series), ReportRequest('bad.csv', include_chart=False, language='en'), cash_balance=1000)
    assert not any(key == 'Cash runway, days' for key, value in report.summary.rows)
    assert any('undated' in text for text in report.insights)


def test_category_context_avoids_dense_pivots_and_can_cancel(monkeypatch):
    from dataclasses import replace
    from app.analytics.anomaly_context import add_category_context
    from app.ml.anomaly_detection import AnomalyDetectionResult, FinancialAnomaly
    from app.services.analysis_loader import AnalysisCancelled
    import pytest
    data = pd.DataFrame({'date':pd.date_range('2026-01-01', periods=1000, freq='h'), 'amount':[1]*999+[1000], 'category':[f'C{i}' for i in range(1000)]})
    prepared = prepare_financial_data(data, SelectedColumns(date='date', amount='amount', category='category'))
    anomaly = FinancialAnomaly(data.date.iloc[-1].to_pydatetime(), 'amount','Amount','spike',1000,1,3,'IQR','High')
    result = AnomalyDetectionResult((anomaly,), 1)
    def no_pivot(*args, **kwargs): raise AssertionError('Dense pivot would be quadratic')
    monkeypatch.setattr(pd.Series, 'unstack', no_pivot)
    assert add_category_context(result, prepared, 'hour', 'monday').anomalies[0].category == 'C999'
    with pytest.raises(AnalysisCancelled):
        add_category_context(result, prepared, 'hour', 'monday', cancelled=lambda: True)
