"""Physical-column mapping, bounded browsing and cancellable file reads."""

from pathlib import Path
import struct
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.analytics.metrics import SelectedColumns
from app.services.analysis_loader import load_selected_columns
from app.services.file_loader import load_file_preview


def make_xlsx(path: Path, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    workbook.save(path)
    workbook.close()
    return path


def make_xls(path: Path, rows: list[list[object]], *, typed_numbers: bool = False) -> Path:
    """Small real BIFF8 fixture, avoiding a runtime Excel-writing dependency."""
    def record(kind, data=b""):
        return struct.pack("<HH", kind, len(data)) + data
    def bof(kind):
        return record(0x0809, struct.pack("<HHHHII", 0x0600, kind, 0x0DBB, 0x07CC, 0, 6))
    def boundsheet(offset):
        return record(0x0085, struct.pack("<IBBBB", offset, 0, 0, 5, 0) + b"Sheet")
    globals_before = bof(0x0005) + record(0x0042, struct.pack("<H", 1200))
    offset = len(globals_before) + len(boundsheet(0)) + 4
    data = globals_before + boundsheet(offset) + record(0x000A) + bof(0x0010)
    data += record(0x0200, struct.pack("<IIHHH", 0, len(rows), 0, max(map(len, rows), default=0), 0))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if typed_numbers and isinstance(value, (int, float)):
                data += record(0x0203, struct.pack("<HHHd", row_index, column_index, 0, value))
                continue
            text = "" if value is None else str(value)
            data += record(0x0204, struct.pack("<HHHHB", row_index, column_index, 0, len(text), 1)
                           + text.encode("utf-16-le"))
    path.write_bytes(data + record(0x000A))
    return path


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls"])
def test_blank_duplicate_and_generated_headers_select_physical_columns(tmp_path, extension):
    rows = [["", "Column 1", " revenue ", "revenue", "revenue (2)"],
            [10, 20, 30, 40, 50], [11, 21, 31, 41, 51]]
    path = tmp_path / f"mixed.{extension}"
    if extension == "csv":
        path.write_text(",Column 1, revenue ,revenue,revenue (2)\n10,20,30,40,50\n11,21,31,41,51\n", encoding="utf-8")
    elif extension == "xlsx":
        make_xlsx(path, rows)
    else:
        make_xls(path, rows)
    preview = load_file_preview(path)
    assert preview.column_names == ["Column 1 (2)", "Column 1", "revenue", "revenue (3)", "revenue (2)"]
    frame = load_selected_columns(path, SelectedColumns(revenue=("revenue (3)", "Column 1 (2)", "Column 1")))
    assert frame.columns.tolist() == ["revenue (3)", "Column 1 (2)", "Column 1"]
    assert frame.astype(str).values.tolist() == [["40", "10", "20"], ["41", "11", "21"]]


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls"])
def test_headerless_files_keep_first_row_and_generated_columns(tmp_path, extension):
    path = tmp_path / f"headerless.{extension}"
    if extension == "csv":
        path.write_text("2026-01-01,100\n2026-01-02,200\n", encoding="utf-8")
    elif extension == "xlsx":
        make_xlsx(path, [["2026-01-01", 100], ["2026-01-02", 200]])
    else:
        make_xls(path, [["2026-01-01", 100], ["2026-01-02", 200]])
    preview = load_file_preview(path)
    assert preview.column_names == ["Column 1", "Column 2"]
    frame = load_selected_columns(path, SelectedColumns(revenue="Column 2"))
    assert frame.astype(str).values.tolist() == [["100"], ["200"]]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1251"])
def test_non_ascii_csv_schema_and_values_survive_full_load(tmp_path, encoding):
    path = tmp_path / "russian.csv"
    path.write_text("Доход;Описание\n100;Кофе\n200;Аренда\n", encoding=encoding)
    preview = load_file_preview(path)
    assert preview.column_names == ["Доход", "Описание"]
    frame = load_selected_columns(path, SelectedColumns(revenue="Доход", category="Описание"))
    assert frame.values.tolist() == [["100", "Кофе"], ["200", "Аренда"]]
    chunked = load_selected_columns(path, SelectedColumns(revenue="Доход", category="Описание"), progress=lambda *_: None)
    assert chunked.values.tolist() == [["100", "Кофе"], ["200", "Аренда"]]


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls"])
def test_pages_include_exact_next_rows_without_loading_all_cells(tmp_path, extension):
    from app.services.table_pages import load_table_page

    path = tmp_path / f"paged.{extension}"
    if extension == "csv":
        path.write_text("revenue,\n" + "".join(f"{i},value {i}\n" for i in range(205)), encoding="utf-8")
    elif extension == "xlsx":
        make_xlsx(path, [["revenue", ""], *[[i, f"value {i}"] for i in range(205)]])
    else:
        make_xls(path, [["revenue", ""], *[[i, f"value {i}"] for i in range(205)]])
    assert load_file_preview(path).preview_row_count == 100
    first = load_table_page(path, page=0, page_size=100)
    assert first.column_names == ["revenue", "Column 2"]
    assert first.rows[0] == ["0", "value 0"]
    assert len(first.rows) == 100 and first.has_next
    last = load_table_page(path, page=2, page_size=100)
    assert last.page == 2 and not last.has_next
    assert last.rows == [[str(i), f"value {i}"] for i in range(200, 205)]
    assert load_table_page(path, page=3, page_size=100).rows == []
    with pytest.raises(ValueError):
        load_table_page(path, page=-1)
    with pytest.raises(ValueError):
        load_table_page(path, page_size=0)


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls"])
def test_measured_progress_and_cancellation_discard_partial_results(tmp_path, extension):
    from app.services.analysis_loader import AnalysisCancelled

    path = tmp_path / f"cancel.{extension}"
    count = 20000 if extension == "csv" else 2500
    if extension == "csv":
        path.write_text("revenue,description\n" + "".join(f"{i},Кофе {i}\n" for i in range(count)), encoding="utf-8")
    elif extension == "xlsx":
        make_xlsx(path, [["revenue", "description"], *[[i, f"Кофе {i}"] for i in range(count)]])
    else:
        make_xls(path, [["revenue", "description"], *[[i, f"Кофе {i}"] for i in range(count)]])
    events = []
    def progress(done, total, unit):
        events.append((done, total, unit))

    with pytest.raises(AnalysisCancelled):
        load_selected_columns(path, SelectedColumns(revenue="revenue"), progress=progress,
                              cancelled=lambda: any(done > 0 for done, _, _ in events))
    assert events and events[0][0] == 0
    assert events[-1][0] < events[-1][1]
    events.clear()
    frame = load_selected_columns(path, SelectedColumns(revenue="revenue"), progress=progress)
    expected_total = path.stat().st_size if extension == "csv" else count
    expected_unit = "bytes" if extension == "csv" else "rows"
    assert len(frame) == count
    assert events[-1] == (expected_total, expected_total, expected_unit)
    assert all(0 <= a <= b for a, b, _ in events)
    assert [e[0] for e in events] == sorted(e[0] for e in events)


def test_cancelled_before_loading_reads_no_data(tmp_path):
    from app.services.analysis_loader import AnalysisCancelled

    path = tmp_path / "data.csv"
    path.write_text("revenue\n10\n", encoding="utf-8")
    with pytest.raises(AnalysisCancelled):
        load_selected_columns(path, SelectedColumns(revenue="revenue"), cancelled=lambda: True)


def test_single_headerless_bom_column_keeps_first_value(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text("100\n200\n", encoding="utf-8-sig")
    preview = load_file_preview(path)
    assert preview.column_names == ["Column 1"]
    assert preview.preview_rows == [["100"], ["200"]]
    frame = load_selected_columns(path, SelectedColumns(revenue="Column 1"))
    assert frame.values.tolist() == [["100"], ["200"]]


def test_description_columns_and_quoted_multiline_pages(tmp_path):
    from app.services.table_pages import load_table_page

    path = tmp_path / "multiline.csv"
    path.write_text('revenue,memo\n100,"Кофе\nи чай"\n200,Аренда\n', encoding="utf-8-sig", newline="")
    selected = SimpleNamespace(date=(), revenue=("revenue",), expense=(), amount=(), category=(), description=("memo",))
    frame = load_selected_columns(path, selected, progress=lambda *_: None)
    assert frame.values.tolist() == [["100", "Кофе\nи чай"], ["200", "Аренда"]]
    page = load_table_page(path, page=1, page_size=1)
    assert page.rows == [["200", "Аренда"]] and not page.has_next


def test_page_consumes_only_requested_rows_and_one_lookahead(tmp_path, monkeypatch):
    import app.services.table_pages as pages

    path = tmp_path / "bounded.csv"
    path.write_text("revenue\n" + "".join(f"{i}\n" for i in range(10000)), encoding="utf-8")
    original_reader = pages.csv.reader
    observed = []
    def observed_reader(*args, **kwargs):
        for row in original_reader(*args, **kwargs):
            observed.append(row)
            yield row
    monkeypatch.setattr(pages.csv, "reader", observed_reader)
    page = pages.load_table_page(path, page=2, page_size=10)
    assert page.rows == [[str(i)] for i in range(20, 30)]
    assert page.has_next
    # One schema header, one page header, 20 skipped, 10 page and 1 lookahead.
    assert len(observed) == 33


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls"])
def test_empty_files_have_empty_preview_and_page(tmp_path, extension):
    from app.services.table_pages import load_table_page
    from app.services.file_loader import FileLoadError

    path = tmp_path / f"empty.{extension}"
    if extension == "csv":
        path.write_bytes(b"")
    elif extension == "xlsx":
        make_xlsx(path, [])
    else:
        make_xls(path, [])
    preview = load_file_preview(path)
    page = load_table_page(path)
    assert preview.column_names == [] and preview.preview_rows == []
    assert page.column_names == [] and page.rows == [] and not page.has_next
    with pytest.raises(FileLoadError):
        load_selected_columns(path, SelectedColumns(revenue="missing"))


def test_utf8_sample_ending_inside_character_is_not_misdetected(tmp_path):
    path = tmp_path / "split.csv"
    # The 23 ASCII bytes put the sample in the middle of a Cyrillic code point.
    path.write_text("revenue,description\n10," + "я" * 40000 + "\n", encoding="utf-8", newline="")
    preview = load_file_preview(path)
    assert preview.preview_rows == [["10", "я" * 40000]]
    frame = load_selected_columns(path, SelectedColumns(revenue="revenue", category="description"))
    assert frame.iloc[0, 1] == "я" * 40000


def test_typed_xls_numbers_have_same_display_on_preview_and_pages(tmp_path):
    from app.services.table_pages import load_table_page

    path = make_xls(tmp_path / "numeric.xls", [["revenue", "expense"], [10, 4], [20, 5]], typed_numbers=True)
    preview = load_file_preview(path)
    page = load_table_page(path)
    assert preview.preview_rows == page.rows


def test_xlsx_header_detection_ignores_leading_bom(tmp_path):
    path = make_xlsx(tmp_path / "bom.xlsx", [["\ufeff100"], [200]])
    preview = load_file_preview(path)
    assert preview.column_names == ["Column 1"]
    frame = load_selected_columns(path, SelectedColumns(revenue="Column 1"))
    assert len(frame) == 2


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_bom_and_header_whitespace_are_both_removed(tmp_path, extension):
    path = tmp_path / f"spaced.{extension}"
    if extension == "csv":
        path.write_text(" revenue ,memo\n100,coffee\n", encoding="utf-8-sig")
    else:
        make_xlsx(path, [["\ufeff revenue ", "memo"], [100, "coffee"]])
    assert load_file_preview(path).column_names == ["revenue", "memo"]
    frame = load_selected_columns(path, SelectedColumns(revenue="revenue"))
    assert frame.astype(str).values.tolist() == [["100"]]
