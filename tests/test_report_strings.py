"""Tests for the bilingual report label table."""

from app.reports.strings import LABELS, SERIES_LABEL_KEYS, label, series_label


def test_russian_and_english_have_identical_keys():
    """A label added to one language must be added to the other."""
    assert set(LABELS["ru"]) == set(LABELS["en"])


def test_label_returns_requested_language():
    assert label("ru", "section_summary") == LABELS["ru"]["section_summary"]
    assert label("en", "section_summary") == LABELS["en"]["section_summary"]


def test_label_falls_back_to_english_for_unknown_language():
    assert label("de", "report_title") == LABELS["en"]["report_title"]


def test_label_returns_key_when_missing_everywhere():
    assert label("ru", "no_such_key") == "no_such_key"


def test_series_labels_are_translated_not_passed_through():
    """A Russian report must not say "spike in Expenses"."""
    assert series_label("ru", "expenses") == "Расходы"
    assert series_label("en", "expenses") == "Expenses"


def test_series_label_falls_back_for_an_unknown_series():
    assert series_label("ru", "mystery", "Mystery") == "Mystery"
    assert series_label("ru", "mystery") == "mystery"


def test_every_series_label_key_exists_in_both_languages():
    for label_key in SERIES_LABEL_KEYS.values():
        assert label_key in LABELS["ru"]
        assert label_key in LABELS["en"]


def test_every_label_is_a_non_empty_string():
    for language, table in LABELS.items():
        for key, value in table.items():
            assert isinstance(value, str), f"{language}.{key} is not a string"
            assert value.strip(), f"{language}.{key} is empty"
