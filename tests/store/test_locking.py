"""What happens when two people have the same book open.

Everywhere else in these tests a book is one connection in one process, and
that is the case where none of this matters. A malthouse runs the intake
desk and the plant office off one file on a share, so the case that matters
is two connections, and it has its own module because setting it up needs a
real file and a second book.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from culmbin.errors import BusyError, StateError
from culmbin.store.book import WAIT_SECONDS, Book


@pytest.fixture
def shared(tmp_path: Path) -> Path:
    """A book on disk that two connections can both open."""
    path = tmp_path / "shared.sqlite3"
    with Book.open(path) as book:
        book.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    return path


def test_a_book_waits_for_the_length_it_was_told_to(tmp_path: Path) -> None:
    with Book.open(tmp_path / "b.sqlite3", wait_seconds=2.5) as book:
        assert book.wait_seconds == 2.5
        assert book.scalar("PRAGMA busy_timeout") == 2500


def test_the_default_wait_is_the_one_the_module_names(tmp_path: Path) -> None:
    with Book.open(tmp_path / "b.sqlite3") as book:
        assert book.wait_seconds == WAIT_SECONDS
        assert book.scalar("PRAGMA busy_timeout") == int(WAIT_SECONDS * 1000)


def test_a_negative_wait_is_refused_rather_than_quietly_meaning_forever(
    tmp_path: Path,
) -> None:
    with pytest.raises(StateError, match="less than no time"):
        Book.open(tmp_path / "b.sqlite3", wait_seconds=-1.0)


def test_a_reader_sees_what_the_other_connection_has_committed(shared: Path) -> None:
    with Book.open(shared) as writer, Book.open(shared) as reader:
        with writer.writing():
            writer.execute("INSERT INTO note (body) VALUES (?)", ("weighed in",))
        assert reader.row_count("note") == 1


def test_a_reader_does_not_see_a_transaction_that_is_still_open(shared: Path) -> None:
    """WAL is the reason this reads rather than blocks."""
    with Book.open(shared) as writer, Book.open(shared) as reader:
        with writer.writing():
            writer.execute("INSERT INTO note (body) VALUES (?)", ("half done",))
            assert reader.row_count("note") == 0
        assert reader.row_count("note") == 1


def test_a_rolled_back_transaction_leaves_the_other_connection_nothing(
    shared: Path,
) -> None:
    def change_its_mind(book: Book) -> None:
        with book.writing():
            book.execute("INSERT INTO note (body) VALUES (?)", ("never mind",))
            raise ValueError("gave up")

    with Book.open(shared) as writer, Book.open(shared) as reader:
        with pytest.raises(ValueError, match="gave up"):
            change_its_mind(writer)
        assert reader.row_count("note") == 0
        assert not writer.in_transaction


def test_the_second_writer_is_told_the_book_is_busy(shared: Path) -> None:
    """Nought seconds of patience, so the second writer finds out at once."""
    with Book.open(shared) as first, Book.open(shared, wait_seconds=0.0) as second:
        with first.writing():
            first.execute("INSERT INTO note (body) VALUES (?)", ("mine",))
            with pytest.raises(BusyError, match="did not finish in time"), second.writing():
                pass
        with second.writing():
            second.execute("INSERT INTO note (body) VALUES (?)", ("now it is mine",))
        assert first.row_count("note") == 2


def test_a_busy_book_says_which_file_is_busy(shared: Path) -> None:
    def take_it(book: Book) -> None:
        with book.writing():
            pass

    with (
        Book.open(shared) as first,
        Book.open(shared, wait_seconds=0.0) as second,
        first.writing(),
    ):
        first.execute("INSERT INTO note (body) VALUES (?)", ("mine",))
        with pytest.raises(BusyError) as caught:
            take_it(second)
        assert str(shared) in str(caught.value)


def test_a_statement_that_is_wrong_is_still_reported_as_wrong(shared: Path) -> None:
    """Only the two lock messages become a BusyError. The rest are bugs."""
    with Book.open(shared) as book, pytest.raises(sqlite3.OperationalError):
        book.execute("SELECT * FROM a_table_nobody_made")


def test_the_wait_survives_a_close_and_a_reopen(shared: Path) -> None:
    with Book.open(shared, wait_seconds=0.25) as book:
        assert book.scalar("PRAGMA busy_timeout") == 250
    with Book.open(shared) as reopened:
        assert reopened.scalar("PRAGMA busy_timeout") == int(WAIT_SECONDS * 1000)
