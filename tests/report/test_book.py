"""The page about the book itself."""

from __future__ import annotations

from culmbin.report.book import book_page
from culmbin.store.book import Book
from culmbin.store.migrations import latest_version


def test_a_fresh_book_says_nothing_is_wrong(book: Book) -> None:
    text = book_page(book)
    assert "nothing is wrong with this book." in text
    assert f"of {latest_version()}" in text


def test_a_fresh_book_lists_every_table_as_empty(book: Book) -> None:
    text = book_page(book)
    assert "holding nothing" in text
    assert "party" in text


def test_a_stocked_book_says_what_is_in_it(desk: Book) -> None:
    text = book_page(desk)
    assert "what is in it" in text
    assert "contract" in text


def test_a_fault_is_on_the_page(desk: Book) -> None:
    desk.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-1', 'C-2025-031', 'L-CLEAN', 28.0, 4.2, '2025-11-20', 'despatched')"
    )
    desk.execute("UPDATE malt_lot SET analysis = NULL WHERE code = 'L-CLEAN'")
    text = book_page(desk)
    assert "wrong" in text
    assert "nothing is wrong with this book." not in text


def test_something_odd_is_kept_apart_from_something_wrong(desk: Book) -> None:
    text = book_page(desk)
    assert "worth a look" in text
    assert "nothing is wrong with this book." in text


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(desk: Book) -> None:
    text = book_page(desk)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
