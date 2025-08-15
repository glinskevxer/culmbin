"""The stock pages."""

from __future__ import annotations

import datetime as dt

from culmbin.report.stock import bin_page, laboratory_page, stock_page
from culmbin.sales.desk import allocate
from culmbin.store.book import Book
from tests.sales.conftest import a_lot

ON = dt.date(2025, 11, 20)


def test_an_empty_book_has_no_stock(desk: Book) -> None:
    desk.execute("DELETE FROM malt_lot")
    assert "there is no malt in stock." in stock_page(desk)


def test_a_lot_is_on_the_stock_page(desk: Book) -> None:
    text = stock_page(desk)
    assert "L-CLEAN" in text
    assert "LAUR" in text
    assert "lots           1" in text


def test_an_allocated_lot_has_less_free_than_sealed(desk: Book) -> None:
    """Free is the column the sales desk reads, not sealed."""
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 40.0, ON)
    text = stock_page(desk)
    assert "60.00" in text
    assert "20.00" in text


def test_an_uncertified_lot_is_marked_on_the_stock_page(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    assert "NO" in stock_page(desk)


def test_a_mixed_lot_says_mixed_rather_than_a_variety(desk: Book) -> None:
    a_lot(desk, "L-MIXED", "B05", ("LAUR", "DIAB"), "M-MIXED")
    assert "mixed" in stock_page(desk)


def test_the_bin_page_marks_a_mixed_bin(desk: Book) -> None:
    """A plant with half its bins marked has lost half its contract cover."""
    a_lot(desk, "L-MIXED", "B05", ("LAUR", "DIAB"), "M-MIXED")
    text = bin_page(desk)
    assert "MIXED" in text
    assert "marked mixed  1" in text


def test_a_clean_bin_is_not_marked(desk: Book) -> None:
    text = bin_page(desk)
    assert "MIXED" not in text
    assert "B04" in text


def test_the_bin_page_counts_empty_bins(desk: Book) -> None:
    assert "empty         0" in bin_page(desk)


def test_a_book_with_no_bins_says_so(book: Book) -> None:
    assert "there are no bins." in bin_page(book)


def test_the_laboratory_page_is_empty_when_everything_is_certified(desk: Book) -> None:
    assert "every lot has a certificate." in laboratory_page(desk)


def test_an_uncertified_lot_is_on_the_laboratory_page(desk: Book) -> None:
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    text = laboratory_page(desk)
    assert "L-CLEAN" in text
    assert "lots    1" in text


def test_every_page_ends_in_a_newline_and_has_no_trailing_space(desk: Book) -> None:
    for text in (stock_page(desk), bin_page(desk), laboratory_page(desk)):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
