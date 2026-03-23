"""An append-only journal of what was done, by whom, and to what."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ValidationError
from culmbin.store.book import Book
from culmbin.store.journal import (
    UNKNOWN,
    Entry,
    about,
    actors,
    check_append_only,
    entries,
    record,
    unattributed,
)

TODAY = dt.date(2025, 11, 4)


def test_an_entry_reads_back_the_way_it_went_in(book: Book) -> None:
    written = record(book, TODAY, "jhollis", "graded", "W-1", "accepted on deduction")
    assert entries(book) == (written,)
    assert written.actor == "jhollis"


def test_an_entry_prints_as_a_line(book: Book) -> None:
    written = record(book, TODAY, "jhollis", "graded", "W-1", "accepted")
    assert str(written) == "2025-11-04  jhollis   graded W-1: accepted"


def test_an_entry_with_no_detail_prints_without_a_colon(book: Book) -> None:
    written = record(book, TODAY, "jhollis", "graded", "W-1")
    assert str(written).endswith("graded W-1")


def test_an_entry_nobody_signed_is_still_an_entry(book: Book) -> None:
    """Pretending the work did not happen is worse than admitting nobody asked."""
    written = record(book, TODAY, "  ", "graded", "W-1")
    assert written.actor == UNKNOWN
    assert unattributed(book) == 1


def test_an_entry_needs_an_action_and_a_subject(book: Book) -> None:
    with pytest.raises(ValidationError, match="needs action"):
        record(book, TODAY, "jhollis", "  ", "W-1")
    with pytest.raises(ValidationError, match="needs subject"):
        record(book, TODAY, "jhollis", "graded", " ")


def test_the_entries_come_back_oldest_first(book: Book) -> None:
    record(book, TODAY, "jhollis", "graded", "W-1")
    record(book, TODAY, "jhollis", "settled", "W-1")
    assert [item.action for item in entries(book)] == ["graded", "settled"]


def test_everything_about_one_thing_comes_back(book: Book) -> None:
    record(book, TODAY, "jhollis", "graded", "W-1")
    record(book, TODAY, "jhollis", "graded", "W-2")
    assert [item.subject for item in about(book, "W-1")] == ["W-1"]


def test_the_entries_narrow_by_who_and_by_day(book: Book) -> None:
    record(book, TODAY, "jhollis", "graded", "W-1")
    record(book, dt.date(2025, 11, 8), "dkehoe", "cast", "2025-118")
    assert [item.actor for item in entries(book, actor="dkehoe")] == ["dkehoe"]
    later = entries(book, since=dt.date(2025, 11, 6))
    assert [item.subject for item in later] == ["2025-118"]


def test_everybody_who_has_done_anything_is_listed(book: Book) -> None:
    record(book, TODAY, "jhollis", "graded", "W-1")
    record(book, TODAY, "dkehoe", "cast", "2025-118")
    record(book, TODAY, "jhollis", "settled", "W-1")
    assert actors(book) == ("dkehoe", "jhollis")


def test_an_entry_cannot_be_edited(book: Book) -> None:
    """A record that can be tidied up is one nobody has reason to believe."""
    record(book, TODAY, "jhollis", "graded", "W-1", "accepted")
    with pytest.raises(Exception, match="append only"):
        book.execute("UPDATE entry SET detail = 'tidied' WHERE seq = 1")


def test_an_entry_cannot_be_deleted(book: Book) -> None:
    record(book, TODAY, "jhollis", "graded", "W-1")
    with pytest.raises(Exception, match="append only"):
        book.execute("DELETE FROM entry WHERE seq = 1")


def test_the_positive_control_proves_the_trigger_fires(book: Book) -> None:
    """A trigger nobody has fired is a trigger somebody believes in."""
    record(book, TODAY, "jhollis", "graded", "W-1")
    check_append_only(book)


def test_an_empty_journal_has_nobody_in_it(book: Book) -> None:
    assert entries(book) == ()
    assert actors(book) == ()
    assert unattributed(book) == 0


def test_a_sequence_number_goes_up(book: Book) -> None:
    first = record(book, TODAY, "jhollis", "graded", "W-1")
    second = record(book, TODAY, "jhollis", "graded", "W-2")
    assert second.seq > first.seq


def test_an_entry_can_be_built_directly() -> None:
    entry = Entry(1, TODAY, "jhollis", "graded", "W-1")
    assert entry.detail == ""
