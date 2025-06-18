"""The floor, end to end.

These run through the layers, so they are the tests that would notice a rule
that is implemented and never called.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError, ValidationError
from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.process.floor import (
    balance_of,
    cast,
    charge,
    floor_line,
    floor_sheet,
    load_kiln,
    ready_to_cast,
    schedule_of,
    strip_kiln,
)
from culmbin.store.book import Book
from culmbin.store.pieces import add_reading, get_piece, recipes_of
from culmbin.store.vessels import retire_vessel
from culmbin.units.clock import Leg

STARTED = dt.date(2025, 11, 3)
CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


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


def charged(plant: Book, code: str = "2025-118", **kwargs: object) -> Piece:
    return charge(plant, piece(code, **kwargs), PROGRAMME, SCHEDULE, CURVE)


def in_a_box(plant: Book, code: str = "2025-118", into: str = "G1") -> None:
    charged(plant, code)
    cast(plant, code, into, CAST, 71.8, 44.8, depth_cm=85.0)


def test_a_charge_goes_in_when_everything_lines_up(plant: Book) -> None:
    charged(plant)
    assert get_piece(plant, "2025-118").vessel == "S1"
    assert recipes_of(plant, "2025-118") == (PROGRAMME, SCHEDULE, CURVE)


def test_a_charge_over_what_the_steep_takes_is_refused(plant: Book) -> None:
    with pytest.raises(ConflictError, match="over what S1 takes"):
        charged(plant, charge_tonnes=60.0)


def test_a_charge_into_a_box_is_refused(plant: Book) -> None:
    with pytest.raises(ConflictError, match="this needs a steep"):
        charged(plant, vessel="G1")


def test_a_charge_into_an_occupied_steep_is_refused(plant: Book) -> None:
    charged(plant, "2025-118")
    with pytest.raises(ConflictError, match="already has 2025-118 in it"):
        charged(plant, "2025-119")


def test_two_pieces_in_one_steep_can_be_asked_for(plant: Book) -> None:
    """It happens when the plant is up against it, so it is a decision not a bug."""
    charged(plant, "2025-118")
    charge(plant, piece("2025-119"), PROGRAMME, SCHEDULE, CURVE, share=True)
    assert get_piece(plant, "2025-119").vessel == "S1"


def test_a_charge_into_a_retired_steep_is_refused(plant: Book) -> None:
    retire_vessel(plant, "S1", dt.date(2025, 1, 1))
    with pytest.raises(ConflictError, match="not in service"):
        charged(plant)


def test_a_recipe_for_another_style_is_refused(plant: Book) -> None:
    """A pale ale piece on a lager steep makes something, and not pale ale."""
    with pytest.raises(ConflictError, match="lager recipe"):
        charge(plant, piece(), "lager long steep", SCHEDULE, CURVE)


def test_a_recipe_that_is_not_there_is_refused(plant: Book) -> None:
    with pytest.raises(NotFoundError):
        charge(plant, piece(), "nothing", SCHEDULE, CURVE)


def test_a_piece_that_is_not_steeping_cannot_be_charged(plant: Book) -> None:
    with pytest.raises(StateError, match="says it is"):
        charge(
            plant,
            piece(stage=PieceStage.GERMINATING, vessel="G1"),
            PROGRAMME,
            SCHEDULE,
            CURVE,
        )


def test_casting_moves_the_piece_and_records_the_weight(plant: Book) -> None:
    in_a_box(plant)
    read = get_piece(plant, "2025-118")
    assert read.stage is PieceStage.GERMINATING
    assert read.vessel == "G1"


def test_a_bed_deeper_than_the_box_runs_is_refused(plant: Book) -> None:
    charged(plant)
    with pytest.raises(ValidationError, match="deeper than"):
        cast(plant, "2025-118", "G1", CAST, 71.8, 44.8, depth_cm=140.0)


def test_more_than_the_bed_holds_is_refused(plant: Book) -> None:
    """The box takes 59.4 tonnes at its deepest, and a steep out is heavier."""
    charged(plant)
    with pytest.raises(ConflictError, match="over the"):
        cast(plant, "2025-118", "G1", CAST, 71.8, 44.8, depth_cm=60.0)


def test_a_shallow_floor_will_not_take_a_box_charge(plant: Book) -> None:
    charged(plant)
    with pytest.raises(ConflictError, match="over the"):
        cast(plant, "2025-118", "F1", CAST, 71.8, 44.8, depth_cm=30.0)


def test_casting_into_a_kiln_is_refused(plant: Book) -> None:
    charged(plant)
    with pytest.raises(ConflictError, match="cast into a bed"):
        cast(plant, "2025-118", "K1", CAST, 71.8, 44.8, depth_cm=85.0)


def test_casting_into_an_occupied_box_is_refused(plant: Book) -> None:
    in_a_box(plant, "2025-118")
    charged(plant, "2025-119", vessel="S2")
    with pytest.raises(ConflictError, match="already has something in it"):
        cast(plant, "2025-119", "G1", CAST, 71.8, 44.8, depth_cm=85.0)


def test_a_piece_that_is_not_steeping_cannot_be_cast(plant: Book) -> None:
    in_a_box(plant)
    with pytest.raises(StateError, match="cannot be cast"):
        cast(plant, "2025-118", "G2", CAST, 71.8, 44.8, depth_cm=85.0)


def test_a_refused_cast_leaves_no_weighing_behind(plant: Book) -> None:
    charged(plant)
    with pytest.raises(ConflictError):
        cast(plant, "2025-118", "K1", CAST, 71.8, 44.8, depth_cm=85.0)
    assert plant.scalar("SELECT count(*) FROM weighing") == 0


def test_a_piece_goes_on_a_kiln_from_the_floor(plant: Book) -> None:
    in_a_box(plant)
    load_kiln(plant, "2025-118", "K1", dt.date(2025, 11, 8))
    assert get_piece(plant, "2025-118").vessel == "K1"


def test_a_piece_in_a_steep_does_not_go_on_a_kiln(plant: Book) -> None:
    charged(plant)
    with pytest.raises(StateError, match="cannot go on a kiln"):
        load_kiln(plant, "2025-118", "K1", dt.date(2025, 11, 8))


def test_a_piece_does_not_go_on_a_box_it_calls_a_kiln(plant: Book) -> None:
    in_a_box(plant)
    with pytest.raises(ConflictError, match="this needs a kiln"):
        load_kiln(plant, "2025-118", "G2", dt.date(2025, 11, 8))


def test_stripping_records_the_malt_and_the_culm(plant: Book) -> None:
    in_a_box(plant)
    load_kiln(plant, "2025-118", "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, "2025-118", KILNED, 37.9, 4.4, 1.9)
    assert get_piece(plant, "2025-118").stage is PieceStage.KILNED


def test_a_piece_not_on_a_kiln_cannot_be_stripped(plant: Book) -> None:
    in_a_box(plant)
    with pytest.raises(StateError, match="is not on a kiln"):
        strip_kiln(plant, "2025-118", KILNED, 37.9, 4.4, 1.9)


def test_a_finished_piece_balances(plant: Book) -> None:
    in_a_box(plant)
    load_kiln(plant, "2025-118", "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, "2025-118", KILNED, 37.9, 4.4, 1.9)
    balance = balance_of(plant, "2025-118")
    assert 6.0 < balance.malting_loss < 12.0
    assert balance.charge_dry_tonnes == pytest.approx(39.6)


def test_a_piece_without_every_weight_does_not_balance(plant: Book) -> None:
    in_a_box(plant)
    with pytest.raises(StateError, match="off_kiln, culm"):
        balance_of(plant, "2025-118")


def test_a_floor_line_reads_the_box_clock(plant: Book) -> None:
    in_a_box(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    line = floor_line(plant, "2025-118")
    assert line.degree_hours == pytest.approx(288.0)
    assert line.turns_wanted == 1
    assert line.turns_owed == 1
    assert not line.ready


def test_a_floor_line_ignores_the_hours_in_the_steep(plant: Book) -> None:
    """The steep readings are on the piece and are not on the box clock."""
    charged(plant)
    add_reading(plant, "2025-118", PieceStage.STEEPING, Leg(hours=48.0, celsius=16.0))
    cast(plant, "2025-118", "G1", CAST, 71.8, 44.8, depth_cm=85.0)
    assert floor_line(plant, "2025-118").degree_hours == pytest.approx(0.0)


def test_a_piece_that_is_not_on_the_floor_has_no_line(plant: Book) -> None:
    charged(plant)
    with pytest.raises(StateError, match="is not on the floor"):
        floor_line(plant, "2025-118")


def test_the_floor_sheet_has_every_piece_on_the_floor(plant: Book) -> None:
    in_a_box(plant, "2025-118", "G1")
    charged(plant, "2025-119", vessel="S2")
    cast(plant, "2025-119", "G2", CAST, 71.8, 44.8, depth_cm=85.0)
    assert [line.piece.code for line in floor_sheet(plant)] == ["2025-118", "2025-119"]


def test_an_empty_floor_has_an_empty_sheet(plant: Book) -> None:
    assert floor_sheet(plant) == ()


def test_a_piece_that_has_earned_its_schedule_is_ready(plant: Book) -> None:
    in_a_box(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=100.0, celsius=16.0))
    assert [item.code for item in ready_to_cast(plant)] == ["2025-118"]
    assert floor_line(plant, "2025-118").ready


def test_a_piece_short_of_its_schedule_is_not_ready(plant: Book) -> None:
    in_a_box(plant)
    add_reading(plant, "2025-118", PieceStage.GERMINATING, Leg(hours=24.0, celsius=16.0))
    assert ready_to_cast(plant) == ()


def test_a_piece_with_no_schedule_cannot_have_one_read(plant: Book) -> None:
    charge(plant, piece("2025-120"), PROGRAMME, SCHEDULE, CURVE)
    plant.execute("UPDATE piece SET schedule = NULL WHERE code = '2025-120'")
    with pytest.raises(NotFoundError, match="not on a germination schedule"):
        schedule_of(plant, "2025-120")
