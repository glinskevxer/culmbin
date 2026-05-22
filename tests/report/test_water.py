"""The steep water page."""

from __future__ import annotations

import datetime as dt

from culmbin.process.floor import cast, charge
from culmbin.report.water import water_page
from culmbin.store.book import Book
from culmbin.store.water import record_water
from culmbin.units.season import Window
from tests.support.records import a_piece

CAST = dt.date(2025, 11, 5)
MONTH = Window(dt.date(2025, 11, 1), dt.date(2025, 11, 30))
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def a_cast_piece(plant: Book, code: str = "2025-118") -> None:
    charge(plant, a_piece(code), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, "G1", CAST, 71.8, 44.8, depth_cm=85.0)


def test_a_month_with_nothing_metered_says_so(plant: Book) -> None:
    assert "nobody metered a steep." in water_page(plant, MONTH)


def test_the_three_numbers_are_next_to_each_other(plant: Book) -> None:
    """Putting them apart lets a plant congratulate itself on a meter reading."""
    a_cast_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    text = water_page(plant, MONTH)
    assert "metered" in text
    assert "kept" in text
    assert "to drain" in text


def test_a_metered_steep_is_on_the_page(plant: Book) -> None:
    a_cast_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    text = water_page(plant, MONTH)
    assert "2025-118" in text
    assert "steeps metered  1" in text


def test_the_page_says_what_a_tidy_plant_runs_at(plant: Book) -> None:
    a_cast_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    assert "air rests and recycling" in water_page(plant, MONTH)


def test_a_heavy_steep_is_counted(plant: Book) -> None:
    a_cast_piece(plant)
    record_water(plant, "2025-118", 600.0, CAST)
    assert "over the band   1" in water_page(plant, MONTH)


def test_a_reading_outside_the_window_is_left_off(plant: Book) -> None:
    a_cast_piece(plant)
    record_water(plant, "2025-118", 150.0, dt.date(2025, 12, 5))
    assert "2025-118" not in water_page(plant, MONTH)


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(plant: Book) -> None:
    a_cast_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    text = water_page(plant, MONTH)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
