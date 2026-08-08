"""A walk for a machine that has just installed the wheel."""

from __future__ import annotations

import pytest

from culmbin.store.book import Book
from culmbin.tools import smoke


def test_the_walk_gets_a_lorry_to_a_settlement(book: Book) -> None:
    said = smoke.walk(book)
    assert "registers written" in said
    assert any("settled at 6551.85" in line for line in said)


def test_the_walk_says_what_is_left_on_the_purchase(book: Book) -> None:
    said = smoke.walk(book)
    assert any("still to come on P-1" in line for line in said)


def test_the_smoke_test_runs_in_a_book_of_its_own(capsys: pytest.CaptureFixture[str]) -> None:
    """It writes into a temporary directory, so it runs anywhere."""
    assert smoke.main([]) == 0
    assert "the wheel works." in capsys.readouterr().out


def test_the_quiet_form_says_only_whether_it_worked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert smoke.main(["--quiet"]) == 0
    output = capsys.readouterr().out
    assert output.strip() == "smoke: the wheel works."


def test_the_walk_goes_all_the_way_out_of_the_gate(book: Book) -> None:
    """The point of the walk is the far end of it, not the near end."""
    said = smoke.walk(book)
    assert any("tipped into the silo" in line for line in said)
    assert any("malting loss" in line for line in said)
    assert any("lot sealed and certified" in line for line in said)
    assert any("contract tonnes despatched" in line for line in said)


def test_the_walk_traces_the_shipment_back_to_a_grower(book: Book) -> None:
    """A shipment that cannot be walked back is a traceability failure."""
    said = smoke.walk(book)
    assert any("walks back to HOLB" in line for line in said)


def test_the_walk_writes_a_certificate_worth_reading(book: Book) -> None:
    said = smoke.walk(book)
    line = next(line for line in said if "certificate" in line)
    assert int(line.split()[3]) > 10


def test_the_walk_touches_most_of_the_package(book: Book) -> None:
    """Nine packages, and the walk is only worth running if it reaches them."""
    smoke.walk(book)
    written = {table for table in book.tables() if book.row_count(table)}
    for table in ("silo_receipt", "piece", "malt_bin", "malt_lot", "shipment", "contract"):
        assert table in written
