"""Every foreign key has an index on the column that points."""

from __future__ import annotations

from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import migrate
from culmbin.tools import check_indexes


def test_the_check_passes_on_the_schema_that_ships() -> None:
    assert check_indexes.problems() == []


def test_the_book_has_a_good_number_of_foreign_keys() -> None:
    with Book.open(MEMORY) as book:
        migrate(book, check_indexes.STAMP)
        assert len(check_indexes.keys(book)) > 30


def test_a_key_prints_as_an_arrow() -> None:
    key = check_indexes.Key("delivery", "party", "party")
    assert str(key) == "delivery.party -> party"


def test_a_primary_key_counts_as_indexed() -> None:
    """SQLite indexes those for free, so a second index would be a duplicate."""
    with Book.open(MEMORY) as book:
        migrate(book, check_indexes.STAMP)
        assert "ticket" in check_indexes.leading_columns(book, "grading")


def test_a_composite_index_covers_its_leading_column() -> None:
    """Half the indexes here are composite for the sake of the order things come back."""
    with Book.open(MEMORY) as book:
        migrate(book, check_indexes.STAMP)
        assert "party" in check_indexes.leading_columns(book, "delivery")


def test_a_column_nothing_indexes_is_not_leading() -> None:
    with Book.open(MEMORY) as book:
        migrate(book, check_indexes.STAMP)
        assert "note" not in check_indexes.leading_columns(book, "movement")


def test_every_exemption_is_a_key_that_exists() -> None:
    """An exemption for a key that has gone is an exemption that hides the next one."""
    with Book.open(MEMORY) as book:
        migrate(book, check_indexes.STAMP)
        present = {(key.table, key.column) for key in check_indexes.keys(book)}
    assert present >= check_indexes.EXEMPT
