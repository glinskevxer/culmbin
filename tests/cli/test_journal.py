"""The journal commands, and what the other commands write into it."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.cli.conftest import Invoke

GOOD = (
    "--result",
    "moisture=12.5",
    "--result",
    "screenings=1.4",
    "--result",
    "germ_capacity=99.0",
    "--result",
    "germ_energy=98.0",
    "--result",
    "admixture=0.4",
    "--result",
    "nitrogen=1.62",
)


def intake(invoke: Invoke) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved", on="2018-12-01")
    invoke("standard", "add", "malting 2025")
    invoke(
        "purchase",
        "add",
        "P-1",
        "HOLB",
        "LAUR",
        "--tonnes",
        "480",
        "--price",
        "232.50",
        "--standard",
        "malting 2025",
        "--crop",
        "2025",
        "--from",
        "2025-09-01",
        "--to",
        "2025-11-30",
        on="2025-03-12",
    )


def test_an_empty_journal_says_nothing_was_done(invoke: Invoke) -> None:
    invoke("init")
    assert "nothing was done." in invoke("journal", "list").output


def test_a_lorry_taken_in_is_written_down(invoke: Invoke) -> None:
    intake(invoke)
    invoke(
        "--by",
        "jhollis",
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        "--harvested",
        "2025-08-14",
        on="2025-09-18",
    )
    text = invoke("journal", "show", "W-1").output
    assert "weighed in W-1" in text
    assert "jhollis" in text


def test_a_grading_is_written_down_with_its_outcome(invoke: Invoke) -> None:
    intake(invoke)
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        "--harvested",
        "2025-08-14",
        on="2025-09-18",
    )
    invoke("delivery", "sample", "W-1", "B-1", *GOOD, on="2025-09-19")
    invoke("--by", "jhollis", "delivery", "grade", "W-1", on="2025-09-19")
    text = invoke("journal", "show", "W-1").output
    assert "graded W-1" in text
    assert "28.180t" in text


def test_a_rejection_is_written_down_with_the_reason(invoke: Invoke) -> None:
    intake(invoke)
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        "--harvested",
        "2025-08-14",
        on="2025-09-18",
    )
    weak = tuple(item if item != "germ_capacity=99.0" else "germ_capacity=90.0" for item in GOOD)
    invoke("delivery", "sample", "W-1", "B-1", *weak, on="2025-09-19")
    invoke("delivery", "grade", "W-1", on="2025-09-19")
    assert "rejected W-1: germination" in invoke("journal", "show", "W-1").output


def test_a_command_nobody_signed_is_still_written_down(invoke: Invoke) -> None:
    """Pretending the work did not happen is worse than admitting nobody asked."""
    intake(invoke)
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    assert "unknown" in invoke("journal", "show", "W-1").output


def test_the_who_list_says_how_much_is_unattributed(invoke: Invoke) -> None:
    intake(invoke)
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    text = invoke("journal", "who").output
    assert "unknown" in text
    assert "entries have nobody against them" in text


def test_the_journal_narrows_to_one_person(invoke: Invoke) -> None:
    intake(invoke)
    invoke(
        "--by",
        "jhollis",
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    invoke(
        "--by",
        "dkehoe",
        "delivery",
        "add",
        "W-2",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    text = invoke("journal", "list", "--by", "dkehoe", on="2025-09-30").output
    assert "W-2" in text
    assert "W-1" not in text


def test_nothing_done_to_a_thing_says_so(invoke: Invoke) -> None:
    invoke("init")
    assert "nothing has been done to W-9." in invoke("journal", "show", "W-9").output


def test_a_journal_entry_cannot_be_edited_through_the_book(invoke: Invoke, book_path: Path) -> None:
    intake(invoke)
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    from culmbin.errors import ConflictError
    from culmbin.store.book import Book

    with Book.open(str(book_path)) as book, pytest.raises(ConflictError, match="append only"):
        book.execute("UPDATE entry SET actor = 'somebody else'")


def test_reading_the_book_writes_nothing(invoke: Invoke) -> None:
    """The journal is what was done, and looking at something is not doing anything."""
    intake(invoke)
    invoke("purchase", "list")
    invoke("report", "intake")
    assert "nothing was done." in invoke("journal", "list", on="2025-11-30").output
