"""One search across every register."""

from __future__ import annotations

import pytest

from culmbin.store.book import Book
from culmbin.store.search import counts, search, searchable


def test_a_code_that_is_a_party_is_found(stocked: Book) -> None:
    found = search(stocked, "HOLB")
    assert [item.kind for item in found] == ["party"]
    assert "Holbeach Grange" in found[0].detail


def test_a_code_that_is_a_purchase_is_found(stocked: Book) -> None:
    found = search(stocked, "P-2025-014")
    assert [item.kind for item in found] == ["purchase"]


def test_a_code_that_is_nothing_finds_nothing(stocked: Book) -> None:
    assert search(stocked, "NOTHING") == ()


def test_a_code_in_two_registers_is_found_twice(stocked: Book) -> None:
    """Codes are not unique across registers and the search does not pretend."""
    stocked.execute(
        "INSERT INTO malt_bin (code, capacity_tonnes, state) VALUES ('LAUR', 100.0, 'empty')"
    )
    found = search(stocked, "LAUR")
    assert {item.kind for item in found} == {"variety", "bin"}


def test_the_search_is_exact(stocked: Book) -> None:
    """A code off a piece of paper is exact, and a partial match is a list."""
    assert search(stocked, "HOL") == ()
    assert search(stocked, "holb") == ()


def test_a_found_row_prints_as_a_line(stocked: Book) -> None:
    line = str(search(stocked, "HOLB")[0])
    assert line.startswith("party")
    assert "HOLB" in line


def test_every_register_is_counted(stocked: Book) -> None:
    counted = dict(counts(stocked))
    assert counted["party"] == 4
    assert counted["variety"] == 2
    assert counted["shipment"] == 0


def test_the_counts_cover_exactly_what_the_search_looks_in(stocked: Book) -> None:
    assert tuple(kind for kind, _ in counts(stocked)) == searchable()


@pytest.mark.parametrize("kind", searchable())
def test_every_searchable_register_is_a_table_in_the_book(book: Book, kind: str) -> None:
    """A register in the table and not in the book is a search that raises."""
    assert dict(counts(book))[kind] == 0
