"""The gas page."""

from __future__ import annotations

import datetime as dt

from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.report.energy import energy_page
from culmbin.store.book import Book
from culmbin.store.energy import record_run
from culmbin.units.season import Window
from tests.support.records import a_piece

CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
MONTH = Window(dt.date(2025, 11, 1), dt.date(2025, 11, 30))
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def stripped(plant: Book, code: str = "2025-118", steep: str = "S1", box: str = "G1") -> str:
    charge(plant, a_piece(code, vessel=steep), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, box, CAST, 71.8, 44.8, depth_cm=85.0)
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, 37.9, 4.4, 1.9)
    return code


def test_a_month_with_nothing_metered_says_so(plant: Book) -> None:
    assert "nobody metered anything." in energy_page(plant, MONTH)


def test_a_run_is_on_the_page_with_both_figures(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    text = energy_page(plant, MONTH)
    assert "2025-118" in text
    assert "efficiency" in text
    assert "kWh/t" in text


def test_the_page_says_how_many_runs_nobody_metered(plant: Book) -> None:
    """A month with unmetered runs has gas over a tonnage the meter never saw."""
    stripped(plant, "2025-118")
    stripped(plant, "2025-119", steep="S2", box="G2")
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    text = energy_page(plant, MONTH)
    assert "runs metered    1" in text
    assert "runs unmetered  1" in text


def test_a_suspect_run_is_at_the_top(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 1200.0, KILNED)
    text = energy_page(plant, MONTH)
    lines = text.splitlines()
    assert "outside what a kiln can do" in text
    assert lines.index("outside what a kiln can do") < lines.index("runs")


def test_a_normal_run_is_not_at_the_top(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert "outside what a kiln can do" not in energy_page(plant, MONTH)


def test_the_page_says_which_number_to_compare(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert "efficiency is the number to compare" in energy_page(plant, MONTH)


def test_a_run_outside_the_window_is_left_off(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, dt.date(2025, 12, 9))
    assert "2025-118" not in energy_page(plant, MONTH)


def test_the_page_ends_in_a_newline_and_has_no_trailing_space(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    text = energy_page(plant, MONTH)
    assert text.endswith("\n")
    assert all(line == line.rstrip() for line in text.splitlines())
