"""Pieces and how they move.

The rules these are about are that a piece goes forwards only, that a write
off is not a move, and that what is conserved is the dry matter rather than
the weight.
"""

from __future__ import annotations

import pytest

from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import PieceStage, VesselKind
from culmbin.model.process import GERMINATION_KINDS, Piece
from tests.support.records import STARTED, a_piece


def piece(code: str = "2025-118", **kwargs: object) -> Piece:
    return a_piece(code, **kwargs)


def test_a_piece_prints_as_a_code_a_weight_and_a_place() -> None:
    assert str(piece()) == "2025-118 45.0t steeping in S1"


def test_a_finished_piece_prints_without_a_place() -> None:
    binned = piece(stage=PieceStage.BINNED, vessel=None)
    assert str(binned) == "2025-118 45.0t binned"


def test_a_piece_needs_a_code_and_a_charge() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        piece(" ")
    with pytest.raises(ValidationError, match="charged with"):
        piece(charge_tonnes=0.0)


def test_a_charge_moisture_off_the_scale_is_refused() -> None:
    with pytest.raises(ValidationError):
        piece(charge_moisture=70.0)


def test_the_dry_matter_is_worked_and_not_stored() -> None:
    """45 tonnes at 12 percent is 39.6 tonnes of barley."""
    assert piece().charge_dry_tonnes == pytest.approx(39.6)


def test_a_wetter_charge_of_the_same_weight_carries_less_barley() -> None:
    assert piece(charge_moisture=14.0).charge_dry_tonnes < piece().charge_dry_tonnes


def test_a_piece_in_a_vessel_stage_needs_a_vessel() -> None:
    with pytest.raises(ValidationError, match="not in anything"):
        piece(vessel=None)


def test_a_finished_piece_must_not_still_be_in_something() -> None:
    with pytest.raises(ValidationError, match="still in"):
        piece(stage=PieceStage.BINNED, vessel="G1")


def test_a_piece_moves_forwards() -> None:
    moved = piece().moved_to(PieceStage.GERMINATING, "G1")
    assert moved.stage is PieceStage.GERMINATING
    assert moved.vessel == "G1"


def test_a_move_keeps_everything_else() -> None:
    moved = piece().moved_to(PieceStage.GERMINATING, "G1")
    assert moved.code == "2025-118"
    assert moved.charge_dry_tonnes == pytest.approx(piece().charge_dry_tonnes)
    assert moved.started == STARTED


def test_a_piece_does_not_go_backwards() -> None:
    germinating = piece(stage=PieceStage.GERMINATING, vessel="G1")
    with pytest.raises(StateError, match="cannot go to"):
        germinating.moved_to(PieceStage.STEEPING, "S1")


def test_a_piece_does_not_stand_still() -> None:
    """Moving a germinating piece to germinating is a split, which is not this."""
    germinating = piece(stage=PieceStage.GERMINATING, vessel="G1")
    with pytest.raises(StateError, match="cannot go to"):
        germinating.moved_to(PieceStage.GERMINATING, "G2")


def test_a_piece_can_skip_a_stage() -> None:
    """It is unusual and it happens, so the record does not stop it."""
    moved = piece().moved_to(PieceStage.KILNING, "K1")
    assert moved.stage is PieceStage.KILNING


def test_moving_to_written_off_is_refused() -> None:
    with pytest.raises(StateError, match="use write_off"):
        piece().moved_to(PieceStage.WRITTEN_OFF)


def test_a_piece_is_written_off_from_wherever_it_was() -> None:
    off = piece(stage=PieceStage.GERMINATING, vessel="G1").written_off()
    assert off.stage is PieceStage.WRITTEN_OFF
    assert off.vessel is None


def test_malt_can_be_condemned_in_the_bin() -> None:
    off = piece(stage=PieceStage.BINNED, vessel=None).written_off()
    assert off.stage is PieceStage.WRITTEN_OFF


def test_writing_off_twice_is_refused() -> None:
    off = piece().written_off()
    with pytest.raises(StateError, match="already written off"):
        off.written_off()


def test_a_piece_in_process_is_somewhere_in_the_plant() -> None:
    assert piece().in_process
    assert piece(stage=PieceStage.GERMINATING, vessel="G1").in_process
    assert not piece(stage=PieceStage.BINNED, vessel=None).in_process


def test_a_finished_piece_has_come_off_the_kiln_one_way_or_another() -> None:
    assert piece(stage=PieceStage.KILNED, vessel=None).finished
    assert piece(stage=PieceStage.BINNED, vessel=None).finished
    assert piece().written_off().finished
    assert not piece().finished


def test_a_steeping_piece_belongs_in_a_steep() -> None:
    assert piece().vessel_kind_ok(VesselKind.STEEP)
    assert not piece().vessel_kind_ok(VesselKind.BOX)


def test_a_germinating_piece_goes_in_a_box_or_on_a_floor() -> None:
    germinating = piece(stage=PieceStage.GERMINATING, vessel="G1")
    assert germinating.vessel_kind_ok(VesselKind.BOX)
    assert germinating.vessel_kind_ok(VesselKind.FLOOR)
    assert not germinating.vessel_kind_ok(VesselKind.KILN)


def test_the_two_germination_kinds_are_the_two_in_the_constant() -> None:
    assert frozenset({VesselKind.BOX, VesselKind.FLOOR}) == GERMINATION_KINDS


def test_a_kilning_piece_belongs_in_a_kiln() -> None:
    kilning = piece(stage=PieceStage.KILNING, vessel="K1")
    assert kilning.vessel_kind_ok(VesselKind.KILN)
    assert not kilning.vessel_kind_ok(VesselKind.STEEP)
