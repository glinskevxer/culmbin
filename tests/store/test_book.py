"""The book.

The tests that matter are the transaction ones, because that is what this
class exists for. The rest is a thin wrapper and is tested as one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.store.book import MEMORY, Book, split_statements


@pytest.fixture
def book() -> Iterator[Book]:
    with Book.open(MEMORY) as opened:
        opened.executescript(
            "CREATE TABLE thing (code TEXT PRIMARY KEY, weight REAL NOT NULL);"
            "CREATE TABLE part ("
            "  id INTEGER PRIMARY KEY, thing TEXT NOT NULL REFERENCES thing (code)"
            ");"
        )
        yield opened


def test_a_book_opens_and_closes(tmp_path: Path) -> None:
    opened = Book.open(tmp_path / "book.sqlite3")
    assert not opened.closed
    opened.close()
    assert opened.closed


def test_closing_a_closed_book_is_not_an_error(tmp_path: Path) -> None:
    opened = Book.open(tmp_path / "book.sqlite3")
    opened.close()
    opened.close()


def test_using_a_closed_book_says_so(tmp_path: Path) -> None:
    opened = Book.open(tmp_path / "book.sqlite3")
    opened.close()
    with pytest.raises(StateError, match="is closed"):
        opened.query("SELECT 1")


def test_foreign_keys_are_on(book: Book) -> None:
    """SQLite has them off by default, per connection, every single time."""
    with pytest.raises(ConflictError, match="does not hold"):
        book.execute("INSERT INTO part (id, thing) VALUES (1, 'nothing')")


def test_a_duplicate_key_is_a_conflict(book: Book) -> None:
    book.execute("INSERT INTO thing VALUES ('A', 1.0)")
    with pytest.raises(ConflictError, match="already holds"):
        book.execute("INSERT INTO thing VALUES ('A', 2.0)")


def test_a_write_outside_a_block_is_committed(tmp_path: Path) -> None:
    """The one that a test reading through the writing connection cannot see."""
    path = tmp_path / "book.sqlite3"
    with Book.open(path) as first:
        first.executescript("CREATE TABLE thing (code TEXT PRIMARY KEY)")
        first.execute("INSERT INTO thing VALUES ('A')")
    with Book.open(path) as second:
        assert second.scalar("SELECT count(*) FROM thing") == 1


def test_a_block_that_finishes_is_committed(tmp_path: Path) -> None:
    path = tmp_path / "book.sqlite3"
    with Book.open(path) as first:
        first.executescript("CREATE TABLE thing (code TEXT PRIMARY KEY)")
        with first.writing() as writing:
            writing.execute("INSERT INTO thing VALUES ('A')")
            writing.execute("INSERT INTO thing VALUES ('B')")
    with Book.open(path) as second:
        assert second.scalar("SELECT count(*) FROM thing") == 2


def test_a_block_that_raises_leaves_nothing_behind(book: Book) -> None:
    def write_then_go_home() -> None:
        with book.writing() as writing:
            writing.execute("INSERT INTO thing VALUES ('A', 1.0)")
            raise RuntimeError("the operator went home")

    with pytest.raises(RuntimeError):
        write_then_go_home()
    assert book.scalar("SELECT count(*) FROM thing") == 0


def test_a_nested_block_commits_once_at_the_outside(book: Book) -> None:
    depth = []
    with book.writing() as outer:
        outer.execute("INSERT INTO thing VALUES ('A', 1.0)")
        with outer.writing() as inner:
            inner.execute("INSERT INTO thing VALUES ('B', 2.0)")
            depth.append(book.in_transaction)
        depth.append(book.in_transaction)
    depth.append(book.in_transaction)
    assert depth == [True, True, False]
    assert book.scalar("SELECT count(*) FROM thing") == 2


def test_a_nested_block_that_raises_rolls_the_whole_thing_back(book: Book) -> None:
    def write_twice_then_trip() -> None:
        with book.writing() as outer:
            outer.execute("INSERT INTO thing VALUES ('A', 1.0)")
            with outer.writing() as inner:
                inner.execute("INSERT INTO thing VALUES ('B', 2.0)")
                raise RuntimeError("the pump tripped")

    with pytest.raises(RuntimeError):
        write_twice_then_trip()
    assert book.scalar("SELECT count(*) FROM thing") == 0


def test_the_book_is_not_in_a_transaction_to_start_with(book: Book) -> None:
    assert not book.in_transaction


def test_query_gives_every_row(book: Book) -> None:
    book.executemany("INSERT INTO thing VALUES (?, ?)", [("A", 1.0), ("B", 2.0)])
    rows = book.query("SELECT code FROM thing ORDER BY code")
    assert [row["code"] for row in rows] == ["A", "B"]


def test_first_gives_nothing_when_there_is_nothing(book: Book) -> None:
    assert book.first("SELECT * FROM thing") is None


def test_one_says_what_was_being_looked_for(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no delivery matches"):
        book.one("SELECT * FROM thing WHERE code = ?", ("A",), what="delivery")


def test_one_gives_the_row_when_there_is_one(book: Book) -> None:
    book.execute("INSERT INTO thing VALUES ('A', 1.0)")
    assert book.one("SELECT * FROM thing WHERE code = ?", ("A",))["weight"] == 1.0


def test_scalar_gives_the_first_column(book: Book) -> None:
    assert book.scalar("SELECT count(*) FROM thing") == 0


def test_scalar_of_nothing_is_nothing(book: Book) -> None:
    assert book.scalar("SELECT code FROM thing") is None


def test_the_tables_are_listed_in_name_order(book: Book) -> None:
    assert book.tables() == ("part", "thing")


def test_the_columns_are_listed_as_declared(book: Book) -> None:
    assert book.columns("thing") == ("code", "weight")


def test_asking_for_a_table_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no table called"):
        book.columns("nothing")


def test_a_table_name_that_is_not_one_is_refused(book: Book) -> None:
    """Table names cannot be parameters, so the few that interpolate are gated."""
    with pytest.raises(NotFoundError, match="not a table name"):
        book.columns("thing; DROP TABLE thing")


def test_a_backup_is_the_same_book(book: Book, tmp_path: Path) -> None:
    book.execute("INSERT INTO thing VALUES ('A', 1.0)")
    book.backup_to(tmp_path / "copy.sqlite3")
    with Book.open(tmp_path / "copy.sqlite3") as copy:
        assert copy.scalar("SELECT count(*) FROM thing") == 1


def test_the_connection_is_reachable_for_the_few_that_need_it(book: Book) -> None:
    assert isinstance(book.connection, sqlite3.Connection)


def test_a_script_splits_into_its_statements() -> None:
    statements = split_statements("CREATE TABLE a (x TEXT);\nCREATE TABLE b (y TEXT);\n")
    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE a")


def test_a_semicolon_inside_a_string_does_not_split() -> None:
    statements = split_statements("INSERT INTO a VALUES ('one; two');\n")
    assert len(statements) == 1


def test_a_trigger_body_does_not_split() -> None:
    """A split on semicolons gets this wrong and `complete_statement` does not."""
    script = (
        "CREATE TRIGGER t AFTER INSERT ON a BEGIN\n"
        "  UPDATE a SET x = 'seen';\n"
        "  UPDATE a SET x = 'twice';\n"
        "END;\n"
    )
    assert len(split_statements(script)) == 1


def test_a_last_statement_with_no_semicolon_is_still_a_statement() -> None:
    assert split_statements("CREATE TABLE a (x TEXT)") == ("CREATE TABLE a (x TEXT)",)


def test_two_statements_on_one_line_are_two_statements() -> None:
    statements = split_statements("CREATE TABLE a (x TEXT); CREATE TABLE b (y TEXT);")
    assert len(statements) == 2


def test_a_script_that_stops_inside_a_string_is_refused() -> None:
    with pytest.raises(StateError, match="middle of a statement"):
        split_statements("INSERT INTO a VALUES ('unclosed")


def test_an_empty_script_has_no_statements() -> None:
    assert split_statements("   \n") == ()


def test_ddl_in_a_block_that_raises_is_rolled_back(book: Book) -> None:
    """This is what `Connection.executescript` would have quietly committed."""

    def make_a_table_then_fail() -> None:
        with book.writing() as writing:
            writing.executescript("CREATE TABLE later (x TEXT);")
            raise RuntimeError("the migration was wrong")

    with pytest.raises(RuntimeError):
        make_a_table_then_fail()
    assert "later" not in book.tables()
