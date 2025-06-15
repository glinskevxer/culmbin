"""Pieces in the book, with their movements, readings and weights."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.store.book import Book
from culmbin.store.pieces import (
    add_piece,
    add_reading,
    find_piece,
    get_piece,
    in_vessel,
    list_pieces,
    move_piece,
    movements,
    readings,
    recipes_of,
    record_weighing,
    weighings,
    write_off_piece,
)
from culmbin.units.clock import Leg

STARTED = dt.date(2025, 11, 3)


def piece(code: str = "2025-118", **kwargs: object) -> Piece:
    fields: dict[str, object] = {
        "variety": "LAUR",
        "crop_year": 2025,
        "style": MaltStyle.PALE_ALE,
        "charge_tonnes": 45.0,
        "charge_moisture": 12.0,
        "started": STARTED,
        "stage": PieceStage.STEEPING,
        "vessel": "S1",
    }
    fields.update(kwargs)
    return Piece(code=code, **fields)  # type: ignore[arg-type]


def test_a_piece_reads_back_the_way_it_went_in(stocked: Book) -> None:
    add_piece(stocked, piece())
    assert get_piece(stocked, "2025-118") == piece()


def test_charging_writes_the_first_movement(stocked: Book) -> None:
    add_piece(stocked, piece())
    assert movements(stocked, "2025-118") == ((PieceStage.STEEPING, "S1", STARTED, ""),)


def test_a_piece_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="2025-999"):
        get_piece(stocked, "2025-999")
    assert find_piece(stocked, "2025-999") is None


def test_a_piece_on_a_variety_that_is_not_listed_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_piece(stocked, piece(variety="NOPE"))


def test_a_piece_in_a_vessel_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        add_piece(stocked, piece(vessel="S9"))


def test_the_recipes_are_kept_against_the_piece(stocked: Book) -> None:
    add_piece(stocked, piece())
    assert recipes_of(stocked, "2025-118") == (None, None, None)


def test_the_recipes_of_something_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        recipes_of(stocked, "2025-999")


def test_moving_a_piece_updates_it_and_records_it(stocked: Book) -> None:
    add_piece(stocked, piece())
    move_piece(stocked, "2025-118", PieceStage.GERMINATING, dt.date(2025, 11, 5), "G1")
    read = get_piece(stocked, "2025-118")
    assert read.stage is PieceStage.GERMINATING
    assert read.vessel == "G1"
    assert len(movements(stocked, "2025-118")) == 2


def test_moving_a_piece_backwards_is_refused(stocked: Book) -> None:
    add_piece(stocked, piece())
    move_piece(stocked, "2025-118", PieceStage.GERMINATING, dt.date(2025, 11, 5), "G1")
    with pytest.raises(StateError, match="cannot go to"):
        move_piece(stocked, "2025-118", PieceStage.STEEPING, dt.date(2025, 11, 6), "S1")


def test_a_refused_move_leaves_the_piece_where_it_was(stocked: Book) -> None:
    add_piece(stocked, piece())
    move_piece(stocked, "2025-118", PieceStage.GERMINATING, dt.date(2025, 11, 5), "G1")
    with pytest.raises(StateError):
        move_piece(stocked, "2025-118", PieceStage.STEEPING, dt.date(2025, 11, 6), "S1")
    assert get_piece(stocked, "2025-118").stage is PieceStage.GERMINATING
    assert len(movements(stocked, "2025-118")) == 2


def test_a_piece_out_of_the_plant_has_no_vessel(stocked: Book) -> None:
    add_piece(stocked, piece())
    move_piece(stocked, "2025-118", PieceStage.KILNED, dt.date(2025, 11, 9))
    assert get_piece(stocked, "2025-118").vessel is None


def test_writing_off_needs_a_reason(stocked: Book) -> None:
    add_piece(stocked, piece())
    with pytest.raises(StateError, match="nothing says why"):
        write_off_piece(stocked, "2025-118", dt.date(2025, 11, 5), "  ")


def test_writing_off_records_the_reason(stocked: Book) -> None:
    add_piece(stocked, piece())
    write_off_piece(stocked, "2025-118", dt.date(2025, 11, 5), "steep flooded, grain drowned")
    assert get_piece(stocked, "2025-118").stage is PieceStage.WRITTEN_OFF
    assert movements(stocked, "2025-118")[-1][3] == "steep flooded, grain drowned"


def test_movements_of_something_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        movements(stocked, "2025-999")


def test_readings_are_kept_apart_by_stage(stocked: Book) -> None:
    """The germination clock must not count the hours in the steep."""
    add_piece(stocked, piece())
    add_reading(stocked, "2025-118", PieceStage.STEEPING, Leg(hours=8.0, celsius=14.0))
    move_piece(stocked, "2025-118", PieceStage.GERMINATING, dt.date(2025, 11, 5), "G1")
    add_reading(stocked, "2025-118", PieceStage.GERMINATING, Leg(hours=12.0, celsius=16.0))
    add_reading(stocked, "2025-118", PieceStage.GERMINATING, Leg(hours=12.0, celsius=17.0))
    assert len(readings(stocked, "2025-118")) == 3
    assert len(readings(stocked, "2025-118", PieceStage.GERMINATING)) == 2


def test_readings_come_back_in_the_order_they_went_in(stocked: Book) -> None:
    add_piece(stocked, piece())
    add_reading(stocked, "2025-118", PieceStage.STEEPING, Leg(hours=8.0, celsius=14.0))
    add_reading(stocked, "2025-118", PieceStage.STEEPING, Leg(hours=6.0, celsius=15.0))
    assert [leg.hours for leg in readings(stocked, "2025-118")] == [8.0, 6.0]


def test_a_reading_at_a_stage_nothing_is_measured_over_is_refused(stocked: Book) -> None:
    add_piece(stocked, piece())
    with pytest.raises(ConflictError, match="not a stage"):
        add_reading(stocked, "2025-118", PieceStage.BINNED, Leg(hours=8.0, celsius=14.0))


def test_a_reading_against_a_piece_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        add_reading(stocked, "2025-999", PieceStage.STEEPING, Leg(hours=8.0, celsius=14.0))


def test_a_piece_with_no_readings_has_none(stocked: Book) -> None:
    add_piece(stocked, piece())
    assert readings(stocked, "2025-118") == ()


def test_the_three_weights_are_kept_by_point(stocked: Book) -> None:
    add_piece(stocked, piece())
    record_weighing(stocked, "2025-118", "steep_out", 71.8, 44.8)
    record_weighing(stocked, "2025-118", "off_kiln", 37.9, 4.4)
    record_weighing(stocked, "2025-118", "culm", 1.9)
    weights = weighings(stocked, "2025-118")
    assert weights["steep_out"] == (71.8, 44.8)
    assert weights["culm"] == (1.9, None)


def test_the_same_weighing_twice_is_refused(stocked: Book) -> None:
    add_piece(stocked, piece())
    record_weighing(stocked, "2025-118", "steep_out", 71.8, 44.8)
    with pytest.raises(ConflictError):
        record_weighing(stocked, "2025-118", "steep_out", 72.0, 44.9)


def test_a_point_nothing_is_weighed_at_is_refused(stocked: Book) -> None:
    add_piece(stocked, piece())
    with pytest.raises(ConflictError, match="not a point"):
        record_weighing(stocked, "2025-118", "halfway", 50.0, 30.0)


def test_a_steep_out_without_a_moisture_is_refused_by_the_book(stocked: Book) -> None:
    add_piece(stocked, piece())
    with pytest.raises(ConflictError):
        record_weighing(stocked, "2025-118", "steep_out", 71.8)


def test_a_weighing_against_a_piece_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        record_weighing(stocked, "2025-999", "culm", 1.9)


def test_the_listing_narrows_three_ways(stocked: Book) -> None:
    add_piece(stocked, piece("2025-118"))
    add_piece(stocked, piece("2025-119", variety="DIAB", vessel=None, stage=PieceStage.KILNED))
    assert [item.code for item in list_pieces(stocked)] == ["2025-118", "2025-119"]
    assert [item.code for item in list_pieces(stocked, variety="DIAB")] == ["2025-119"]
    steeping = list_pieces(stocked, stage=PieceStage.STEEPING)
    assert [item.code for item in steeping] == ["2025-118"]
    assert len(list_pieces(stocked, crop_year=2024)) == 0


def test_a_vessel_says_what_is_in_it(stocked: Book) -> None:
    add_piece(stocked, piece())
    found = in_vessel(stocked, "S1")
    assert found is not None
    assert found.code == "2025-118"


def test_an_empty_vessel_has_nothing_in_it(stocked: Book) -> None:
    assert in_vessel(stocked, "G1") is None
