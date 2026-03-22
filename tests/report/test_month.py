"""The month end page."""

from __future__ import annotations

import datetime as dt

from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.report.month import month_page
from culmbin.store.book import Book
from culmbin.store.energy import record_run
from culmbin.units.season import Window
from tests.support.records import a_piece

MONTH = Window(dt.date(2025, 11, 1), dt.date(2025, 11, 30))
CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def a_month(plant: Book, code: str = "2025-118", malt: float = 37.9) -> None:
    charge(plant, a_piece(code), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, "G1", CAST, 71.8, 44.8, depth_cm=85.0)
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, malt, 4.4, 1.9)


def test_a_month_with_nothing_in_it_still_prints(plant: Book) -> None:
    text = month_page(plant, MONTH)
    assert "month end 2025-11-01..2025-11-30" in text
    assert "nothing in the month needs explaining" in text


def test_the_walk_carries_both_columns(plant: Book) -> None:
    a_month(plant)
    text = month_page(plant, MONTH)
    assert "as it lies" in text
    assert "dry matter" in text
    assert "39.60" in text


def test_every_stage_of_the_building_is_a_row(plant: Book) -> None:
    a_month(plant)
    text = month_page(plant, MONTH)
    for stage in ("barley graded", "barley charged to steep", "malt off the kiln", "culm"):
        assert stage in text


def test_the_figures_carry_loss_and_yield(plant: Book) -> None:
    a_month(plant)
    text = month_page(plant, MONTH)
    assert "malting loss" in text
    assert "yield" in text


def test_the_gas_is_on_the_page_when_a_run_was_metered(plant: Book) -> None:
    a_month(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert "3160 m3" in month_page(plant, MONTH)


def test_a_piece_charged_outside_the_yard_is_a_gap(plant: Book) -> None:
    a_month(plant)
    text = month_page(plant, MONTH)
    assert "charged without going through a silo" in text


def test_a_bad_loss_says_to_look_at_a_weighbridge(plant: Book) -> None:
    a_month(plant, malt=30.0)
    assert "look at a weighbridge" in month_page(plant, MONTH)


def test_the_page_says_which_column_adds_up(plant: Book) -> None:
    assert "the one that adds up across the building" in month_page(plant, MONTH)


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(plant: Book) -> None:
    a_month(plant)
    text = month_page(plant, MONTH)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
