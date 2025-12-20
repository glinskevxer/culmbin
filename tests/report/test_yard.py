"""The barley yard page."""

from __future__ import annotations

import datetime as dt

from culmbin.model.silo import Silo
from culmbin.report.yard import yard_page
from culmbin.store.book import Book
from culmbin.store.silos import add_silo, tip
from tests.report.conftest import lorry

TIPPED = dt.date(2025, 9, 19)


def test_a_yard_with_no_silos_says_so(week: Book) -> None:
    assert "there are no silos." in yard_page(week)


def test_an_empty_silo_is_on_the_page(week: Book) -> None:
    add_silo(week, Silo("SL1", 400.0))
    text = yard_page(week)
    assert "SL1" in text
    assert "silos               1" in text


def test_a_load_in_the_pit_is_at_the_top(week: Book) -> None:
    """The pit is where barley goes bad, so it is the thing with a clock on it."""
    lorry(week, "W-1")
    text = yard_page(week)
    lines = text.splitlines()
    assert "still in the pit" in text
    assert lines.index("still in the pit") < len(lines)
    assert "waiting in the pit  1" in text


def test_a_tipped_load_is_off_the_pit_list(week: Book) -> None:
    add_silo(week, Silo("SL1", 400.0))
    lorry(week, "W-1")
    tip(week, "SL1", "W-1", TIPPED)
    text = yard_page(week)
    assert "still in the pit" not in text
    assert "28.18" in text


def test_the_page_counts_the_loads_in_a_silo(week: Book) -> None:
    add_silo(week, Silo("SL1", 400.0))
    lorry(week, "W-1")
    lorry(week, "W-2")
    tip(week, "SL1", "W-1", TIPPED)
    tip(week, "SL1", "W-2", TIPPED)
    assert "loads" in yard_page(week)
    assert "LAUR" in yard_page(week)


def test_a_mixed_silo_is_marked(week: Book) -> None:
    add_silo(week, Silo("SL1", 400.0, mixed=True))
    text = yard_page(week)
    assert "MIXED" in text
    assert "marked mixed        1" in text


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(week: Book) -> None:
    add_silo(week, Silo("SL1", 400.0))
    lorry(week, "W-1")
    text = yard_page(week)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
