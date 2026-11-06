"""Conservative, explainable RU/EN keyword categorisation; no training or API."""

from __future__ import annotations

import re
import pandas as pd

from app.analytics.column_detection import normalize_text


# Specific expense rules precede broad sales rules. Cyrillic stems cover inflection;
# English keywords match whole words so 'rent' cannot match 'restaurant'.
CATEGORY_RULES: dict[str, tuple[str, ...]] = {
    'Marketing': ('ads', 'advertising', 'marketing', 'реклам', 'таргет', 'маркетинг'),
    'Rent': ('rent', 'lease', 'аренд'),
    'Payroll': ('salary', 'payroll', 'wages', 'зарплат', 'заработн'),
    'Inventory': ('inventory', 'stock', 'purchase', 'закуп', 'поставщик'),
    'Sales': ('sales', 'sale', 'kaspi qr', 'выруч', 'продаж'),
}
CATEGORIES = (*CATEGORY_RULES, 'Other')
_PATTERNS = {
    category: tuple(re.compile(r'(?<!\w)' + re.escape(word) + (r'\w*' if re.search('[а-я]', word) else r'(?!\w)')) for word in words)
    for category, words in CATEGORY_RULES.items()
}


def categorize_descriptions(values: pd.Series | None) -> pd.Series:
    """Preserve the source index; missing/unmatched descriptions become Other."""
    if values is None:
        return pd.Series(dtype=str)

    def categorize(value: object) -> str:
        if pd.isna(value):
            return 'Other'
        text = normalize_text(str(value))
        for category, patterns in _PATTERNS.items():
            if any(pattern.search(text) for pattern in patterns):
                return category
        return 'Other'

    return values.map(categorize).astype(str)
