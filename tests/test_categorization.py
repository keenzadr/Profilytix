import pandas as pd
import pytest

from app.analytics.metrics import SelectedColumns, prepare_financial_data, calculate_basic_metrics_from_prepared


@pytest.mark.parametrize('text, expected', [
    ('Instagram Ads', 'Marketing'), ('Оплата рекламы', 'Marketing'),
    ('Rent for November', 'Rent'), ('Аренда помещения', 'Rent'),
    ('Salary', 'Payroll'), ('Зарплата сотрудникам', 'Payroll'),
    ('Закупка товара', 'Inventory'), ('Inventory purchase', 'Inventory'),
    ('Kaspi QR', 'Sales'), ('Выручка за день', 'Sales'),
    ('restaurant lunch', 'Other'), (None, 'Other'), ('', 'Other'),
])
def test_description_rules(text, expected):
    from app.ml.categorization import categorize_descriptions
    assert categorize_descriptions(pd.Series([text])).iloc[0] == expected


def test_categories_keep_index_and_handle_empty_input():
    from app.ml.categorization import categorize_descriptions
    source = pd.Series(['Rent', pd.NA], index=[9, 4])
    assert categorize_descriptions(source).to_dict() == {9: 'Rent', 4: 'Other'}
    assert categorize_descriptions(None).empty
    assert categorize_descriptions(pd.Series(dtype=str)).empty


def test_derived_categories_preserve_explicit_breakdown():
    data = pd.DataFrame({'amount': [-100, -50, 300], 'desc': ['Rent', 'Ads', 'Sales'], 'region': ['North'] * 3})
    prepared = prepare_financial_data(data, SelectedColumns(amount='amount', category='region', description='desc'))
    metrics = calculate_basic_metrics_from_prepared(prepared, category_limit=None)
    assert [item.name for item in metrics.top_categories] == ['North']
    assert {item.name for item in metrics.derived_categories} == {'Rent', 'Marketing', 'Sales'}
    assert sum(item.profit for item in metrics.derived_categories) == metrics.total_profit == 150


def test_no_description_does_not_invent_categories():
    metrics = calculate_basic_metrics_from_prepared(prepare_financial_data(pd.DataFrame({'a':[10]}), SelectedColumns(amount='a')))
    assert metrics.derived_categories == ()


def test_detailed_category_breakdown_is_not_capped():
    data = pd.DataFrame({'a': [1] * 40, 'c': [f'Category {i}' for i in range(40)]})
    metrics = calculate_basic_metrics_from_prepared(prepare_financial_data(data, SelectedColumns(amount='a', category='c')), category_limit=None)
    assert len(metrics.top_categories) == 40


def test_empty_file_with_descriptions_produces_no_category_rows():
    prepared = prepare_financial_data(pd.DataFrame(columns=['amount', 'description']), SelectedColumns(amount='amount', description='description'))
    assert calculate_basic_metrics_from_prepared(prepared).derived_categories == ()
