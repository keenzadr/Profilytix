import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_cash_input_distinguishes_missing_zero_and_invalid(app):
    from app.ui.analysis_options import AnalysisOptionsWidget
    options = AnalysisOptionsWidget(language='en')
    assert options.cash_balance() is None
    options.balance_edit.setText('0')
    assert options.cash_balance() == 0
    options.balance_edit.setText('10 000,50')
    assert options.cash_balance() == 10000.5
    for value in ['-1', 'NaN', 'inf', 'abc']:
        options.balance_edit.setText(value)
        with pytest.raises(ValueError): options.cash_balance()


def test_method_and_profiles_keep_stable_keys(app):
    from app.ui.analysis_options import AnalysisOptionsWidget
    options = AnalysisOptionsWidget(language='ru')
    options.method_combo.setCurrentIndex(options.method_combo.findData('isolation_forest'))
    options.set_profiles(['Bank', 'Sales'])
    options.profile_combo.setCurrentText('Bank')
    options.set_language('en')
    assert options.anomaly_method() == 'isolation_forest'
    assert options.profile_combo.currentText() == 'Bank'
