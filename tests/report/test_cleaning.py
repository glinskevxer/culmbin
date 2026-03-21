"""The cleaning page."""

from __future__ import annotations

import datetime as dt

from culmbin.model.enums import Role
from culmbin.model.party import Party
from culmbin.report.cleaning import cleaning_page, vessel_history
from culmbin.store.book import Book
from culmbin.store.cleaning import record_cleaning, set_interval
from culmbin.store.parties import add_party

CLEANED = dt.date(2025, 11, 1)
TODAY = dt.date(2025, 11, 15)


def cleaner(plant: Book) -> Book:
    add_party(plant, Party("DKEHOE", "D Kehoe", Role.HAULIER, dt.date(2011, 6, 1)))
    return plant


def test_a_plant_nobody_polices_says_so(plant: Book) -> None:
    """It looks identical on every other page to a vessel that is clean."""
    text = cleaning_page(plant, TODAY)
    assert "no interval set" in text
    assert "nobody policing  7" in text
    assert "overdue          0" in text


def test_a_policed_vessel_that_is_overdue_is_at_the_top(plant: Book) -> None:
    set_interval(plant, "S1", 7, 4)
    text = cleaning_page(plant, TODAY)
    lines = text.splitlines()
    assert "overdue" in text
    assert lines.index("overdue") < lines.index("no interval set")
    assert "never been cleaned" in text


def test_a_recently_cleaned_vessel_is_not_overdue(plant: Book) -> None:
    cleaner(plant)
    set_interval(plant, "S1", 30, 12)
    record_cleaning(plant, "S1", CLEANED, "DKEHOE")
    text = cleaning_page(plant, TODAY)
    assert "overdue          0" in text
    assert "2025-11-01" in text


def test_the_page_says_the_interval_both_ways(plant: Book) -> None:
    set_interval(plant, "S1", 30, 12)
    assert "30d / 12p" in cleaning_page(plant, TODAY)


def test_a_book_with_no_plant_says_so(book: Book) -> None:
    assert "there is no plant." in cleaning_page(book, TODAY)


def test_a_vessel_nobody_cleaned_has_no_history(plant: Book) -> None:
    assert "S1 has never been cleaned." in vessel_history(plant, "S1")


def test_the_history_is_oldest_first(plant: Book) -> None:
    cleaner(plant)
    record_cleaning(plant, "S1", CLEANED, "DKEHOE", "hot wash")
    record_cleaning(plant, "S1", dt.date(2025, 11, 20), "DKEHOE", "hot wash and rinse")
    text = vessel_history(plant, "S1")
    lines = [line for line in text.splitlines() if line.startswith("2025-")]
    assert lines[0].startswith("2025-11-01")


def test_both_pages_end_in_a_newline_and_have_no_trailing_space(plant: Book) -> None:
    cleaner(plant)
    record_cleaning(plant, "S1", CLEANED, "DKEHOE")
    for text in (cleaning_page(plant, TODAY), vessel_history(plant, "S1")):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
