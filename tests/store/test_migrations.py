"""The migrations.

These are mostly about the book ending up at the version it says it is at,
because everything else in the package trusts that number.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from culmbin.errors import StateError, ValidationError
from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import (
    MIGRATIONS,
    Migration,
    _check_order,
    current_version,
    latest_version,
    migrate,
    open_book,
    pending,
)

APPLIED = "2025-11-04T09:00:00+00:00"


@pytest.fixture
def book() -> Iterator[Book]:
    with Book.open(MEMORY) as opened:
        yield opened


def test_a_new_book_is_at_version_zero(book: Book) -> None:
    assert current_version(book) == 0


def test_everything_is_pending_on_a_new_book(book: Book) -> None:
    assert pending(book) == MIGRATIONS


def test_migrating_brings_a_book_up_to_date(book: Book) -> None:
    applied = migrate(book, APPLIED)
    assert applied == MIGRATIONS
    assert current_version(book) == latest_version()
    assert pending(book) == ()


def test_migrating_twice_does_nothing_the_second_time(book: Book) -> None:
    migrate(book, APPLIED)
    assert migrate(book, APPLIED) == ()


def test_the_version_table_says_when_and_what(book: Book) -> None:
    migrate(book, APPLIED)
    rows = book.query("SELECT version, name, applied_at FROM schema_version ORDER BY version")
    assert [row["version"] for row in rows] == [item.version for item in MIGRATIONS]
    assert all(row["applied_at"] == APPLIED for row in rows)


def test_the_registers_are_there_after_migrating(book: Book) -> None:
    migrate(book, APPLIED)
    assert {"party", "variety", "vessel"} <= set(book.tables())


def test_the_party_table_holds_what_the_record_holds(book: Book) -> None:
    migrate(book, APPLIED)
    assert book.columns("party") == (
        "code",
        "name",
        "role",
        "opened",
        "closed",
        "holding",
        "note",
    )


def test_a_role_that_is_not_one_is_refused_by_the_book(book: Book) -> None:
    migrate(book, APPLIED)
    with pytest.raises(Exception, match="CHECK"):
        book.execute(
            "INSERT INTO party (code, name, role, opened) VALUES ('X', 'X', 'wizard', '2025-01-01')"
        )


def test_a_holding_on_somebody_who_is_not_a_grower_is_refused(book: Book) -> None:
    migrate(book, APPLIED)
    with pytest.raises(Exception, match="CHECK"):
        book.execute(
            "INSERT INTO party (code, name, role, opened, holding) "
            "VALUES ('X', 'X', 'customer', '2025-01-01', '12/345')"
        )


def test_a_withdrawn_variety_without_a_date_is_refused_by_the_book(book: Book) -> None:
    migrate(book, APPLIED)
    with pytest.raises(Exception, match="CHECK"):
        book.execute(
            "INSERT INTO variety (code, name, habit, approval, listed) "
            "VALUES ('X', 'X', 'spring', 'withdrawn', '2020-01-01')"
        )


def test_a_steep_with_a_bed_depth_is_refused_by_the_book(book: Book) -> None:
    """The record refuses it and so does the book, because both get written to."""
    migrate(book, APPLIED)
    with pytest.raises(Exception, match="CHECK"):
        book.execute(
            "INSERT INTO vessel (code, name, kind, commissioned, charge_limit_t, "
            "floor_area_m2, depth_limit_cm) "
            "VALUES ('S1', 'S1', 'steep', '1998-04-01', 45.0, 120.0, 90.0)"
        )


def test_a_box_without_an_area_is_refused_by_the_book(book: Book) -> None:
    migrate(book, APPLIED)
    with pytest.raises(Exception, match="CHECK"):
        book.execute(
            "INSERT INTO vessel (code, name, kind, commissioned) "
            "VALUES ('G1', 'G1', 'box', '1998-04-01')"
        )


def test_every_migration_has_a_version_a_name_and_a_script() -> None:
    for migration in MIGRATIONS:
        assert migration.version >= 1
        assert migration.name.strip()
        assert migration.script.strip()


def test_the_versions_are_one_two_three_with_no_gaps() -> None:
    assert [item.version for item in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))


def test_no_two_migrations_share_a_name() -> None:
    names = [item.name for item in MIGRATIONS]
    assert len(names) == len(set(names))


def test_a_migration_without_a_script_is_refused() -> None:
    with pytest.raises(ValidationError, match="no script"):
        Migration(1, "empty", "   ")


def test_a_migration_without_a_name_is_refused() -> None:
    with pytest.raises(ValidationError, match="no name"):
        Migration(1, " ", "SELECT 1")


def test_a_migration_numbered_zero_is_refused() -> None:
    with pytest.raises(ValidationError, match="not one"):
        Migration(0, "zero", "SELECT 1")


def test_migrations_out_of_order_are_refused() -> None:
    with pytest.raises(StateError, match="out of order"):
        _check_order([Migration(2, "b", "SELECT 1"), Migration(1, "a", "SELECT 1")])


def test_two_migrations_sharing_a_version_are_refused() -> None:
    with pytest.raises(StateError, match="share a version"):
        _check_order([Migration(1, "a", "SELECT 1"), Migration(1, "b", "SELECT 1")])


def test_open_book_gives_a_book_that_is_up_to_date(tmp_path: Path) -> None:
    with open_book(str(tmp_path / "book.sqlite3"), APPLIED) as opened:
        assert current_version(opened) == latest_version()


def test_open_book_leaves_an_existing_book_alone(tmp_path: Path) -> None:
    path = str(tmp_path / "book.sqlite3")
    with open_book(path, APPLIED) as first:
        first.execute(
            "INSERT INTO party (code, name, role, opened) VALUES ('A', 'A', 'grower', '2025-01-01')"
        )
    with open_book(path, APPLIED) as second:
        assert second.scalar("SELECT count(*) FROM party") == 1
