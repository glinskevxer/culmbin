"""The floor pages."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.model.enums import PieceStage
from culmbin.process.floor import cast, charge, load_kiln
from culmbin.report.floor import in_process_page, plant_page, shift_sheet
from culmbin.store.book import Book
from culmbin.store.pieces import add_reading
from culmbin.units.clock import GROWTH_BASE_C, Leg
from tests.support.records import a_piece

STARTED = dt.date(2025, 11, 3)
CAST = dt.date(2025, 11, 5)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def on_the_floor(plant: Book, code: str = "2025-118", steep: str = "S1", box: str = "G1") -> None:
    charge(plant, a_piece(code, vessel=steep), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, box, CAST, 71.8, 44.8, depth_cm=85.0)


def test_an_empty_floor_says_so(plant: Book) -> None:
    assert "nothing is on the floor." in shift_sheet(plant)


def test_a_piece_on_the_floor_is_on_the_sheet(plant: Book) -> None:
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    text = shift_sheet(plant)
    assert "2025-118" in text
    assert "G1" in text
    assert "288" in text


def test_a_stalled_bed_is_at_the_top(plant: Book) -> None:
    """It is not growing slowly, it is stopped."""
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=40.0, celsius=16.0))
    add_reading(
        plant, "2025-118", PieceStage.GERMINATING, Leg(hours=14.0, celsius=GROWTH_BASE_C - 1.0)
    )
    text = shift_sheet(plant)
    lines = text.splitlines()
    assert "stalled" in text
    assert lines.index("stalled") < len(lines)


def test_a_turn_that_is_owed_is_counted(plant: Book) -> None:
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    assert "turns owed" in shift_sheet(plant)


def test_a_piece_that_has_earned_its_schedule_is_ready(plant: Book) -> None:
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=200.0, celsius=16.0))
    text = shift_sheet(plant)
    assert "ready" in text


def test_the_sheet_says_what_temperature_the_clock_assumed(plant: Book) -> None:
    on_the_floor(plant)
    assert "box temperature      17.0C" in shift_sheet(plant, at_celsius=17.0)


def test_the_plant_page_lists_what_is_free(plant: Book) -> None:
    text = plant_page(plant)
    assert "free" in text
    assert "S1" in text
    assert "in use" not in text


def test_a_vessel_with_something_in_it_is_in_use(plant: Book) -> None:
    on_the_floor(plant)
    text = plant_page(plant)
    assert "in use" in text
    assert "2025-118" in text


def test_the_plant_page_counts_by_kind(plant: Book) -> None:
    text = plant_page(plant)
    assert "steep" in text
    assert "kiln" in text


def test_the_in_process_page_splits_by_stage(plant: Book) -> None:
    charge(plant, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    on_the_floor(plant, "2025-119", steep="S2", box="G2")
    load_kiln(plant, "2025-119", "K1", dt.date(2025, 11, 8))
    text = in_process_page(plant)
    assert "steeping" in text
    assert "kilning" in text
    assert "germinating" not in text


def test_an_empty_plant_says_nothing_is_in_it(plant: Book) -> None:
    assert "nothing is in the plant." in in_process_page(plant)


def test_every_page_ends_in_a_newline_and_has_no_trailing_space(plant: Book) -> None:
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    for text in (shift_sheet(plant), plant_page(plant), in_process_page(plant)):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())


def test_a_piece_appears_exactly_once_on_the_shift_sheet(plant: Book) -> None:
    """The four blocks partition the floor, so nothing is in two of them."""
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    text = shift_sheet(plant)
    assert text.count("2025-118") == 1


@pytest.mark.parametrize("temperature", [12.0, 16.0, 18.0])
def test_the_clock_moves_with_the_temperature_the_sheet_is_run_at(
    plant: Book, temperature: float
) -> None:
    on_the_floor(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    assert f"{temperature:.1f}C" in shift_sheet(plant, at_celsius=temperature)
