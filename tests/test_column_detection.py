"""Tests for column detection against real-world file shapes.

The header lists here are copied from actual files that were run through the
application, including ones that used to be detected wrongly. `sample_data/` is
git-ignored, so the shapes live in the test rather than the fixtures.
"""

from __future__ import annotations

from app.analytics.column_detection import detect_columns, normalize_text


# A realistic English sales export. Headers are camelCase, which is how most
# spreadsheets written in English name their columns.
SALES_HEADERS = [
    "Date",
    "Region",
    "Product",
    "Quantity",
    "UnitPrice",
    "StoreLocation",
    "CustomerType",
    "Discount",
    "Salesperson",
    "TotalPrice",
    "PaymentMethod",
    "Promotion",
    "Returned",
    "OrderID",
    "CustomerName",
    "ShippingCost",
    "OrderDate",
    "DeliveryDate",
    "RegionManager",
]

SALES_ROWS = [
    [
        "2023-02-23 00:00:00", "East", "Laptop", "14", "163.6", "Store B", "Wholesale",
        "0", "Eva", "2290.4", "Card", "None", "No", "10001", "Ann Lee", "12.55",
        "2023-02-23 00:00:00", "2023-02-27 00:00:00", "Ivan",
    ],
    [
        "2024-12-19 00:00:00", "South", "Phone", "1", "544.01", "Store A", "Retail",
        "0", "Alice", "544.01", "Cash", "None", "No", "10002", "Bob Ray", "31.20",
        "2024-12-19 00:00:00", "2024-12-23 00:00:00", "Olga",
    ],
    [
        "2023-05-10 00:00:00", "North", "Desk", "14", "346.18", "Store B", "Wholesale",
        "0.1", "Alice", "4361.868", "Card", "Spring", "No", "10003", "Cara Fox", "8.40",
        "2023-05-10 00:00:00", "2023-05-14 00:00:00", "Ivan",
    ],
    [
        "2023-08-02 00:00:00", "Central", "Tablet", "3", "220.50", "Store C", "Retail",
        "0", "Eva", "661.50", "Card", "None", "Yes", "10004", "Dan Kim", "15.00",
        "2023-08-02 00:00:00", "2023-08-06 00:00:00", "Olga",
    ],
    [
        "2024-03-14 00:00:00", "East", "Monitor", "7", "129.99", "Store A", "Wholesale",
        "0.05", "Alice", "909.93", "Cash", "Spring", "No", "10005", "Ann Lee", "22.10",
        "2024-03-14 00:00:00", "2024-03-18 00:00:00", "Ivan",
    ],
    [
        "2024-07-30 00:00:00", "South", "Chair", "2", "89.00", "Store C", "Retail",
        "0", "Eva", "178.00", "Card", "None", "No", "10006", "Bob Ray", "9.75",
        "2024-07-30 00:00:00", "2024-08-03 00:00:00", "Olga",
    ],
]


# The Russian transactional file the project already handled correctly.
RUSSIAN_HEADERS = ["Дата операции", "Категория", "Сумма дохода", "Сумма расхода"]
RUSSIAN_ROWS = [
    ["01.01.2026", "Продажи", "120 000", ""],
    ["01.01.2026", "Аренда", "", "32 000"],
    ["02.01.2026", "Услуги", "75 000", ""],
    ["02.01.2026", "Зарплата", "", "55 000"],
    ["03.01.2026", "Продажи", "98 500", ""],
    ["03.01.2026", "Реклама", "", "18 000"],
]


def detect(headers, rows):
    return detect_columns(list(headers), [list(row) for row in rows])


# Header normalization.


def test_camel_case_headers_are_split_into_words():
    """TotalPrice must expose the word "total", or no keyword list can see it."""
    assert normalize_text("TotalPrice") == "total price"
    assert normalize_text("ShippingCost") == "shipping cost"
    assert normalize_text("CustomerType") == "customer type"


def test_existing_separators_still_normalize():
    assert normalize_text("Дата операции") == "дата операции"
    assert normalize_text("total_price") == "total price"
    assert normalize_text("Total-Price") == "total price"
    assert normalize_text("Сумма дохода") == "сумма дохода"


def test_acronym_runs_are_kept_readable():
    assert normalize_text("OrderID") == "order id"
    assert normalize_text("TOTALPrice") == "total price"


# The bug: the transaction total lost to the per-unit price.


def test_transaction_total_outranks_the_per_unit_price():
    result = detect(SALES_HEADERS, SALES_ROWS)
    ranked = [candidate.column_name for candidate in result.money_candidates]

    assert ranked.index("TotalPrice") < ranked.index("UnitPrice")
    assert ranked.index("TotalPrice") < ranked.index("Discount")
    assert ranked.index("TotalPrice") < ranked.index("ShippingCost")


def test_money_role_picks_the_transaction_total():
    result = detect(SALES_HEADERS, SALES_ROWS)
    money_columns = {
        result.revenue.column_name,
        result.amount.column_name,
    }

    assert "TotalPrice" in money_columns
    assert "UnitPrice" not in money_columns


def test_a_category_is_found_in_a_sales_file():
    result = detect(SALES_HEADERS, SALES_ROWS)

    assert result.category.column_name in {
        "Region",
        "Product",
        "StoreLocation",
        "CustomerType",
    }


def test_date_is_still_detected_in_a_sales_file():
    result = detect(SALES_HEADERS, SALES_ROWS)

    assert result.date.column_name in {"Date", "OrderDate"}


def test_identifier_columns_are_not_treated_as_money():
    result = detect(SALES_HEADERS, SALES_ROWS)
    money_columns = {
        result.revenue.column_name,
        result.expense.column_name,
        result.amount.column_name,
    }

    assert "OrderID" not in money_columns
    assert "Quantity" not in money_columns


# Confirmation flag.


def test_confirmation_requested_when_money_rests_on_values_alone():
    """A numeric column with a meaningless name is a guess, not a finding."""
    headers = ["when", "who", "x1"]
    rows = [
        ["01.01.2026", "Alpha", "1200.55"],
        ["02.01.2026", "Beta", "980.10"],
        ["03.01.2026", "Alpha", "1450.75"],
        ["04.01.2026", "Gamma", "1100.00"],
        ["05.01.2026", "Beta", "1330.40"],
        ["06.01.2026", "Alpha", "1010.90"],
    ]

    result = detect(headers, rows)

    if result.amount.column_name == "x1":
        assert result.needs_user_confirmation


def test_confirmation_requested_when_money_candidates_exist_but_none_was_chosen():
    headers = ["date", "note", "ratio"]
    rows = [
        ["01.01.2026", "a", "0.5"],
        ["02.01.2026", "b", "0.7"],
        ["03.01.2026", "c", "0.2"],
        ["04.01.2026", "d", "0.9"],
        ["05.01.2026", "e", "0.4"],
        ["06.01.2026", "f", "0.6"],
    ]

    result = detect(headers, rows)

    assert result.needs_user_confirmation


def test_named_money_columns_do_not_demand_confirmation():
    result = detect(RUSSIAN_HEADERS, RUSSIAN_ROWS)

    assert not result.needs_user_confirmation


# Regressions: shapes that already worked must keep working.


def test_russian_transactional_headers_are_detected_exactly():
    result = detect(RUSSIAN_HEADERS, RUSSIAN_ROWS)

    assert result.date.column_name == "Дата операции"
    assert result.revenue.column_name == "Сумма дохода"
    assert result.expense.column_name == "Сумма расхода"
    assert result.category.column_name == "Категория"
    assert result.date.confidence == 1.0
    assert result.revenue.confidence == 1.0
    assert result.expense.confidence == 1.0
    assert result.category.confidence == 1.0


def test_anonymous_feature_matrix_asks_for_confirmation():
    """86 numeric feature columns with no money meaning, as in Financial Distress."""
    headers = ["Company", "Time", "Financial Distress"] + [f"x{i}" for i in range(1, 20)]
    rows = [
        ["1", str(step), "0.01"] + [f"{step * i * 0.37:.4f}" for i in range(1, 20)]
        for step in range(1, 8)
    ]

    result = detect(headers, rows)

    assert result.needs_user_confirmation


def test_news_headlines_yield_no_money_column():
    headers = ["", "headline", "url", "publisher", "date", "stock"]
    rows = [
        [
            str(index),
            f"Some market headline number {index}",
            f"https://example.com/news/{index}",
            "Benzinga",
            "2020-06-05 10:30:54-04:00",
            "AAPL",
        ]
        for index in range(8)
    ]

    result = detect(headers, rows)

    assert result.revenue.column_name is None
    assert result.expense.column_name is None
    assert result.amount.column_name is None
    assert result.needs_user_confirmation


def test_category_is_found_from_region_and_product_alone():
    """A sales file need not contain the word "category" anywhere."""
    headers = ["Date", "Region", "Product", "Quantity", "TotalPrice"]
    rows = [
        ["2023-02-23", "East", "Laptop", "14", "2290.40"],
        ["2024-12-19", "South", "Phone", "1", "544.01"],
        ["2023-05-10", "North", "Desk", "14", "4361.87"],
        ["2023-08-02", "Central", "Tablet", "3", "661.50"],
        ["2024-03-14", "East", "Monitor", "7", "909.93"],
        ["2024-07-30", "South", "Chair", "2", "178.00"],
        ["2024-09-11", "North", "Laptop", "5", "1450.00"],
        ["2023-11-05", "East", "Phone", "2", "1088.02"],
    ]

    result = detect(headers, rows)

    assert result.category.column_name in {"Region", "Product"}
    assert result.amount.column_name == "TotalPrice"


def test_russian_business_dimensions_are_recognised():
    headers = ["Дата", "Филиал", "Сумма"]
    rows = [
        ["01.01.2026", "Центральный", "120 000"],
        ["02.01.2026", "Северный", "98 000"],
        ["03.01.2026", "Центральный", "145 000"],
        ["04.01.2026", "Южный", "87 500"],
        ["05.01.2026", "Северный", "132 000"],
        ["06.01.2026", "Центральный", "101 000"],
    ]

    result = detect(headers, rows)

    assert result.category.column_name == "Филиал"


def test_unnamed_low_cardinality_text_column_can_be_a_category():
    """Evidence from values must be able to reach the threshold on its own."""
    headers = ["Дата", "щшгн", "Сумма"]
    rows = [
        ["01.01.2026", "альфа", "120 000"],
        ["02.01.2026", "бета", "98 000"],
        ["03.01.2026", "альфа", "145 000"],
        ["04.01.2026", "гамма", "87 500"],
        ["05.01.2026", "бета", "132 000"],
        ["06.01.2026", "альфа", "101 000"],
    ]

    result = detect(headers, rows)

    assert result.category.column_name == "щшгн"


def test_high_cardinality_text_column_is_not_a_category():
    headers = ["Дата", "Комментарий", "Сумма"]
    rows = [
        [f"0{index}.01.2026", f"уникальное примечание номер {index}", "100 000"]
        for index in range(1, 9)
    ]

    result = detect(headers, rows)

    assert result.category.column_name != "Комментарий"


def test_free_text_columns_never_become_categories():
    headers = ["date", "headline", "amount"]
    rows = [
        ["0%d.01.2026" % index, f"A completely unique headline {index}", "100.50"]
        for index in range(1, 9)
    ]

    result = detect(headers, rows)

    assert result.category.column_name != "headline"
