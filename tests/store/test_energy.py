"""Kiln runs in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.store.book import Book
from culmbin.store.energy import (
    find_run,
    gas_used,
    get_run,
    kiln_of,
    list_runs,
    record_run,
    suspect_runs,
    unmetered,
)
from tests.support.records import a_piece

CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def stripped(plant: Book, code: str = "2025-118", steep: str = "S1", box: str = "G1") -> str:
    charge(plant, a_piece(code, vessel=steep), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, box, CAST, 71.8, 44.8, depth_cm=85.0)
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, 37.9, 4.4, 1.9)
    return code


def test_a_run_reads_back_with_the_weights_around_it(plant: Book) -> None:
    stripped(plant)
    run = record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert run.green_tonnes == pytest.approx(71.8)
    assert run.malt_tonnes == pytest.approx(37.9)
    assert get_run(plant, "2025-118").gas_m3 == pytest.approx(3160.0)


def test_a_piece_that_was_never_weighed_cannot_carry_a_meter_reading(plant: Book) -> None:
    """Half the arithmetic needs the weight that came off the kiln."""
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    with pytest.raises(StateError, match="says nothing"):
        record_run(plant, "2025-118", "K1", 3160.0, KILNED)


def test_a_piece_that_is_not_there_is_refused(plant: Book) -> None:
    with pytest.raises(NotFoundError, match="2025-999"):
        record_run(plant, "2025-999", "K1", 3160.0, KILNED)


def test_a_run_recorded_twice_is_refused(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    with pytest.raises(ConflictError):
        record_run(plant, "2025-118", "K1", 3200.0, KILNED)


def test_a_run_on_a_kiln_that_is_not_there_is_refused(plant: Book) -> None:
    stripped(plant)
    with pytest.raises(ConflictError, match="does not hold"):
        record_run(plant, "2025-118", "K9", 3160.0, KILNED)


def test_a_run_that_is_not_there_says_which_piece(plant: Book) -> None:
    with pytest.raises(NotFoundError, match="2025-118"):
        get_run(plant, "2025-118")
    assert find_run(plant, "2025-118") is None
    with pytest.raises(NotFoundError):
        kiln_of(plant, "2025-118")


def test_a_run_says_which_kiln_it_was_on(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert kiln_of(plant, "2025-118") == "K1"


def test_a_stripped_piece_with_no_reading_is_on_the_list(plant: Book) -> None:
    """A month with half its runs unmetered cannot be compared with anything."""
    stripped(plant)
    assert unmetered(plant) == ("2025-118",)


def test_a_metered_piece_is_off_the_list(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert unmetered(plant) == ()


def test_a_piece_still_on_the_kiln_is_not_on_the_list(plant: Book) -> None:
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, "2025-118", "G1", CAST, 71.8, 44.8, depth_cm=85.0)
    load_kiln(plant, "2025-118", "K1", dt.date(2025, 11, 8))
    assert unmetered(plant) == ()


def test_the_listing_narrows_by_kiln_and_by_day(plant: Book) -> None:
    stripped(plant, "2025-118")
    stripped(plant, "2025-119", steep="S2", box="G2")
    record_run(plant, "2025-118", "K1", 3160.0, dt.date(2025, 11, 9))
    record_run(plant, "2025-119", "K2", 3200.0, dt.date(2025, 11, 16))
    assert [run.piece for run in list_runs(plant)] == ["2025-118", "2025-119"]
    assert [run.piece for run in list_runs(plant, kiln="K2")] == ["2025-119"]
    later = list_runs(plant, since=dt.date(2025, 11, 12))
    assert [run.piece for run in later] == ["2025-119"]


def test_the_gas_adds_up_over_a_stretch(plant: Book) -> None:
    stripped(plant, "2025-118")
    stripped(plant, "2025-119", steep="S2", box="G2")
    record_run(plant, "2025-118", "K1", 3160.0, dt.date(2025, 11, 9))
    record_run(plant, "2025-119", "K2", 3200.0, dt.date(2025, 11, 16))
    assert gas_used(plant) == pytest.approx(6360.0)
    assert gas_used(plant, since=dt.date(2025, 11, 12)) == pytest.approx(3200.0)


def test_an_empty_book_burnt_nothing(plant: Book) -> None:
    assert gas_used(plant) == pytest.approx(0.0)
    assert list_runs(plant) == ()


def test_a_run_outside_the_band_is_flagged(plant: Book) -> None:
    """One run at two hundred percent moves a month further than any real gain."""
    stripped(plant)
    record_run(plant, "2025-118", "K1", 1200.0, KILNED)
    assert [run.piece for run in suspect_runs(plant)] == ["2025-118"]


def test_a_normal_run_is_not_flagged(plant: Book) -> None:
    stripped(plant)
    record_run(plant, "2025-118", "K1", 3160.0, KILNED)
    assert suspect_runs(plant) == ()
