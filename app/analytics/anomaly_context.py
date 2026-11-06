"""Sparse category contributions to aggregated anomalies; never a dense pivot."""

from dataclasses import replace

import pandas as pd
import numpy as np

from app.analytics.metrics import PreparedFinancialData
from app.analytics.time_series import _group_periods, _normalize_dates
from app.ml.anomaly_detection import AnomalyDetectionResult
from app.services.analysis_loader import AnalysisCancelled


def _implicit_zero_median(values, period_count):
    """Include absent-category zeros without allocating the period/category grid."""
    values = np.asarray(values, dtype=float)
    negative = np.sort(values[values < 0])
    positive = np.sort(values[values > 0])
    zeros = period_count - len(negative) - len(positive)
    def at(index):
        if index < len(negative):
            return negative[index]
        if index < len(negative) + zeros:
            return 0.0
        return positive[index - len(negative) - zeros]
    return at((period_count - 1) // 2) / 2 + at(period_count // 2) / 2


def add_category_context(result: AnomalyDetectionResult, prepared: PreparedFinancialData, grouping: str, week_start: str, *, cancelled=None) -> AnomalyDetectionResult:
    """Describe a contribution, without claiming that a category caused an anomaly."""
    def check():
        if cancelled is not None and cancelled():
            raise AnalysisCancelled()
    check()
    categories = prepared.categories if prepared.categories is not None else prepared.derived_categories
    if not result.has_anomalies or categories is None or prepared.dates is None:
        return result
    dates = _normalize_dates(prepared.dates)
    periods = _group_periods(dates, grouping, week_start)
    frame = pd.DataFrame({'period': periods, 'category': categories})
    for key, values in [('revenue', prepared.revenue), ('expenses', prepared.expenses), ('amount', prepared.amount)]:
        frame[key] = values.fillna(0) if values is not None else 0.0
    frame['profit'] = frame['revenue'] - frame['expenses']
    frame = frame.dropna(subset=['period'])
    if frame.empty:
        return result
    grouped = frame.groupby(['period', 'category'])[['revenue', 'expenses', 'profit', 'amount']].sum()
    period_count = frame['period'].nunique()
    baselines = {}
    for key in {item.series_key for item in result.anomalies}:
        current = {}
        for category, values in grouped[key].groupby(level='category', sort=False):
            check()
            current[category] = _implicit_zero_median(values.to_numpy(), period_count)
        baselines[key] = pd.Series(current, dtype=float)
    contextual = []
    for anomaly in result.anomalies:
        check()
        period = pd.Timestamp(anomaly.period)
        try:
            observed = grouped[anomaly.series_key].xs(period, level='period')
        except KeyError:
            contextual.append(anomaly)
            continue
        delta = observed.subtract(baselines[anomaly.series_key], fill_value=0)
        directional = -delta if anomaly.kind == 'drop' else delta
        if not directional.empty and directional.max() > 0:
            contextual.append(replace(anomaly, category=str(directional.idxmax())))
        else:
            contextual.append(anomaly)
    return replace(result, anomalies=tuple(contextual))
