"""Steep water readings in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.store.book import Book
from culmbin.store.water import (
    find_water,
    get_water,
    heavy,
    list_water,
    metered,
    record_water,
    to_drain,
    unmetered,
)
from tests.support.records import a_piece

CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def a_cast_piece(plant: Book, code: str = "2025-118", steep: str = "S1", box: str = "G1") -> str:
    charge(plant, a_piece(code, vessel=steep), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, box, CAST, 71.8, 44.8, depth_cm=85.0)
    return code


def a_finished_piece(plant: Book, code: str = "2025-118") -> str:
    a_cast_piece(plant, code)
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, 37.9, 4.4, 1.9)
    return code


def test_a_reading_reads_back_with_the_weights_around_it(plant: Book) -> None:
    a_finished_piece(plant)
    use = record_water(plant, "2025-118", 150.0, CAST)
    assert use.metered_m3 == pytest.approx(150.0)
    assert use.malt_tonnes == pytest.approx(37.9)
    assert use.to_drain_m3 < 150.0


def test_a_piece_that_was_never_cast_cannot_carry_a_reading(plant: Book) -> None:
    """The split into kept and drained needs the steep out moisture."""
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    with pytest.raises(StateError, match="has not been cast"):
        record_water(plant, "2025-118", 150.0, CAST)


def test_a_cast_piece_can_be_metered_before_it_is_stripped(plant: Book) -> None:
    a_cast_piece(plant)
    use = record_water(plant, "2025-118", 150.0, CAST)
    assert use.malt_tonnes == pytest.approx(71.8)


def test_a_piece_that_is_not_there_is_refused(plant: Book) -> None:
    with pytest.raises(NotFoundError):
        record_water(plant, "2025-999", 150.0, CAST)


def test_a_reading_recorded_twice_is_refused(plant: Book) -> None:
    a_finished_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    with pytest.raises(ConflictError):
        record_water(plant, "2025-118", 160.0, CAST)


def test_a_reading_that_is_not_there_says_which_piece(plant: Book) -> None:
    with pytest.raises(NotFoundError, match="2025-118"):
        get_water(plant, "2025-118")
    assert find_water(plant, "2025-118") is None


def test_a_cast_piece_with_no_reading_is_on_the_list(plant: Book) -> None:
    a_cast_piece(plant)
    assert unmetered(plant) == ("2025-118",)


def test_a_metered_piece_is_off_the_list(plant: Book) -> None:
    a_finished_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    assert unmetered(plant) == ()


def test_a_piece_still_in_the_steep_is_not_on_the_list(plant: Book) -> None:
    charge(plant, a_piece(), PROGRAMME, SCHEDULE, CURVE)
    assert unmetered(plant) == ()


def test_the_water_adds_up_over_a_stretch(plant: Book) -> None:
    a_finished_piece(plant, "2025-118")
    a_cast_piece(plant, "2025-119", steep="S2", box="G2")
    record_water(plant, "2025-118", 150.0, dt.date(2025, 11, 5))
    record_water(plant, "2025-119", 160.0, dt.date(2025, 11, 12))
    assert metered(plant) == pytest.approx(310.0)
    assert metered(plant, since=dt.date(2025, 11, 8)) == pytest.approx(160.0)


def test_what_went_to_drain_is_less_than_what_was_metered(plant: Book) -> None:
    a_finished_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    assert to_drain(plant) < metered(plant)
    assert to_drain(plant) > 0.0


def test_a_heavy_piece_is_a_bill_rather_than_a_fault(plant: Book) -> None:
    a_finished_piece(plant)
    record_water(plant, "2025-118", 400.0, CAST)
    assert [use.piece for use in heavy(plant)] == ["2025-118"]


def test_a_tidy_piece_is_not_heavy(plant: Book) -> None:
    a_finished_piece(plant)
    record_water(plant, "2025-118", 150.0, CAST)
    assert heavy(plant) == ()


def test_an_empty_book_metered_nothing(plant: Book) -> None:
    assert metered(plant) == pytest.approx(0.0)
    assert list_water(plant) == ()
