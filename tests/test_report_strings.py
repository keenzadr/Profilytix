"""Tests for the bilingual report label table."""

from app.reports.strings import LABELS, label


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


def test_every_label_is_a_non_empty_string():
    for language, table in LABELS.items():
        for key, value in table.items():
            assert isinstance(value, str), f"{language}.{key} is not a string"
            assert value.strip(), f"{language}.{key} is empty"
