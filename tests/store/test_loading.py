"""Loading a batch of laboratory results out of a file."""

from __future__ import annotations

from pathlib import Path

import pytest

from culmbin.errors import ConflictError, ValidationError
from culmbin.model.enums import Basis, Material
from culmbin.store.analyses import count_analyses, get_analysis
from culmbin.store.book import Book
from culmbin.store.loading import COLUMNS, gather, load, read

GOOD = """reference,material,taken,code,value
M-1,malt,2025-11-12,malt_moisture,4.2
M-1,malt,2025-11-12,extract_fine,81.4
M-1,malt,2025-11-12,colour,3.4
M-2,malt,2025-11-12,malt_moisture,4.4
M-2,malt,2025-11-12,colour,3.8
"""


def a_file(tmp_path: Path, text: str = GOOD) -> Path:
    path = tmp_path / "lab.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_good_file_reads_every_row(tmp_path: Path) -> None:
    rows = read(a_file(tmp_path))
    assert len(rows) == 5
    assert rows[0].reference == "M-1"
    assert rows[0].result.basis is None


def test_a_result_takes_its_basis_off_the_table(tmp_path: Path) -> None:
    rows = read(a_file(tmp_path))
    extract = next(row for row in rows if row.result.code == "extract_fine")
    assert extract.result.basis is Basis.DRY


def test_the_rows_gather_into_analyses_in_the_order_they_appear(tmp_path: Path) -> None:
    analyses = gather(read(a_file(tmp_path)))
    assert [item.reference for item in analyses] == ["M-1", "M-2"]
    assert len(analyses[0]) == 3


def test_a_whole_file_lands_in_the_book(book: Book, tmp_path: Path) -> None:
    load(book, a_file(tmp_path))
    assert count_analyses(book, Material.MALT) == 2
    assert get_analysis(book, "M-1")["colour"].value == pytest.approx(3.4)


def test_a_file_with_no_header_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="no header row"):
        read(a_file(tmp_path, ""))


def test_a_file_missing_a_column_says_which(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="no value column"):
        read(a_file(tmp_path, "reference,material,taken,code\nM-1,malt,2025-11-12,colour\n"))


def test_a_row_with_a_blank_cell_says_which_line(tmp_path: Path) -> None:
    text = GOOD.replace("M-1,malt,2025-11-12,colour,3.4", "M-1,malt,2025-11-12,colour,")
    with pytest.raises(ValidationError, match="line 4 has no value"):
        read(a_file(tmp_path, text))


def test_a_row_with_a_bad_date_says_which_line(tmp_path: Path) -> None:
    text = GOOD.replace(
        "M-2,malt,2025-11-12,malt_moisture,4.4", "M-2,malt,12/11/2025,malt_moisture,4.4"
    )
    with pytest.raises(ValidationError, match="where a date goes"):
        read(a_file(tmp_path, text))


def test_a_row_with_a_bad_number_says_which_line(tmp_path: Path) -> None:
    text = GOOD.replace("colour,3.4", "colour,dark")
    with pytest.raises(ValidationError, match="where a number goes"):
        read(a_file(tmp_path, text))


def test_a_material_that_is_not_one_is_refused(tmp_path: Path) -> None:
    text = GOOD.replace("M-2,malt,", "M-2,wheat,")
    with pytest.raises(ValidationError, match="the material is 'wheat'"):
        read(a_file(tmp_path, text))


def test_a_barley_determination_in_a_malt_analysis_is_refused(tmp_path: Path) -> None:
    text = GOOD.replace("M-1,malt,2025-11-12,colour,3.4", "M-1,malt,2025-11-12,screenings,1.4")
    with pytest.raises(ValidationError, match="barley determination"):
        read(a_file(tmp_path, text))


def test_two_rows_disagreeing_about_one_analysis_are_refused(tmp_path: Path) -> None:
    text = GOOD.replace("M-1,malt,2025-11-12,colour,3.4", "M-1,malt,2025-11-13,colour,3.4")
    with pytest.raises(ValidationError, match="disagrees with line 2"):
        gather(read(a_file(tmp_path, text)))


def test_the_same_determination_twice_is_refused(tmp_path: Path) -> None:
    text = GOOD + "M-2,malt,2025-11-12,colour,3.9\n"
    with pytest.raises(ValidationError, match="the second colour"):
        gather(read(a_file(tmp_path, text)))


def test_a_bad_line_leaves_the_book_exactly_as_it_was(book: Book, tmp_path: Path) -> None:
    """Eighty percent of a file is the worst possible outcome."""
    text = GOOD.replace("M-2,malt,2025-11-12,colour,3.8", "M-2,malt,2025-11-12,colour,dark")
    with pytest.raises(ValidationError):
        load(book, a_file(tmp_path, text))
    assert count_analyses(book) == 0


def test_loading_the_same_file_twice_is_refused(book: Book, tmp_path: Path) -> None:
    load(book, a_file(tmp_path))
    with pytest.raises(ConflictError, match="this file is a repeat"):
        load(book, a_file(tmp_path))
    assert count_analyses(book) == 2


def test_a_file_that_would_clash_writes_nothing(book: Book, tmp_path: Path) -> None:
    load(book, a_file(tmp_path))
    text = GOOD + "M-3,malt,2025-11-12,malt_moisture,4.5\n"
    with pytest.raises(ConflictError):
        load(book, a_file(tmp_path, text))
    assert count_analyses(book) == 2


def test_the_columns_are_the_five_the_laboratory_sends() -> None:
    """One row per determination, so a new analyte is not a new column."""
    assert COLUMNS == ("reference", "material", "taken", "code", "value")
