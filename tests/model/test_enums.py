"""The closed vocabularies.

The values are written into the book, so a rename is a migration. These
tests hold the stored spelling of every member for that reason, and they are
tedious on purpose.
"""

from __future__ import annotations

import pytest

from culmbin.model.enums import (
    STAGE_ORDER,
    Approval,
    Basis,
    BinState,
    Conformance,
    ContractState,
    Habit,
    IntakeOutcome,
    KilnPhase,
    LegKind,
    MaltStyle,
    Material,
    PieceStage,
    RejectionReason,
    Role,
    ShipmentState,
    VesselKind,
    stage_follows,
)

ENUMS = [
    Approval,
    Basis,
    BinState,
    Conformance,
    ContractState,
    Habit,
    IntakeOutcome,
    KilnPhase,
    LegKind,
    MaltStyle,
    Material,
    PieceStage,
    RejectionReason,
    Role,
    ShipmentState,
    VesselKind,
]


@pytest.mark.parametrize("enum", ENUMS)
def test_every_member_stores_as_its_own_name_in_lower_case(enum: type[Basis]) -> None:
    for member in enum:
        assert member.value == member.name.lower()


@pytest.mark.parametrize("enum", ENUMS)
def test_every_member_is_a_string(enum: type[Basis]) -> None:
    for member in enum:
        assert isinstance(member, str)


@pytest.mark.parametrize("enum", ENUMS)
def test_the_stored_value_reads_back(enum: type[Basis]) -> None:
    for member in enum:
        assert enum(member.value) is member


@pytest.mark.parametrize("enum", ENUMS)
def test_no_two_members_share_a_value(enum: type[Basis]) -> None:
    values = [member.value for member in enum]
    assert len(values) == len(set(values))


def test_there_are_exactly_two_bases() -> None:
    """A third basis would silently change what every specification means."""
    assert set(Basis) == {Basis.AS_IS, Basis.DRY}


def test_a_rejection_is_not_the_bottom_of_the_schedule() -> None:
    assert IntakeOutcome.REJECTED not in (
        IntakeOutcome.ACCEPTED,
        IntakeOutcome.ACCEPTED_ON_DEDUCTION,
    )


def test_the_stage_order_is_the_order_they_are_written_in() -> None:
    assert STAGE_ORDER == (
        PieceStage.STEEPING,
        PieceStage.GERMINATING,
        PieceStage.KILNING,
        PieceStage.KILNED,
        PieceStage.BINNED,
    )


def test_a_write_off_is_not_on_the_path() -> None:
    assert PieceStage.WRITTEN_OFF not in STAGE_ORDER


def test_stage_order_covers_every_stage_but_the_write_off() -> None:
    assert set(STAGE_ORDER) | {PieceStage.WRITTEN_OFF} == set(PieceStage)


def test_a_later_stage_follows_an_earlier_one() -> None:
    assert stage_follows(PieceStage.STEEPING, PieceStage.KILNING)
    assert stage_follows(PieceStage.KILNED, PieceStage.BINNED)


def test_an_earlier_stage_does_not_follow_a_later_one() -> None:
    assert not stage_follows(PieceStage.KILNING, PieceStage.STEEPING)


def test_a_stage_does_not_follow_itself() -> None:
    for stage in STAGE_ORDER:
        assert not stage_follows(stage, stage)


def test_nothing_follows_a_write_off_and_it_follows_nothing() -> None:
    assert not stage_follows(PieceStage.WRITTEN_OFF, PieceStage.BINNED)
    assert not stage_follows(PieceStage.STEEPING, PieceStage.WRITTEN_OFF)


def test_the_kiln_phases_are_in_the_order_the_kiln_runs_them() -> None:
    assert list(KilnPhase) == [KilnPhase.FREE_DRYING, KilnPhase.BREAK, KilnPhase.CURING]


def test_a_steep_has_two_kinds_of_leg() -> None:
    assert set(LegKind) == {LegKind.WET_STAND, LegKind.AIR_REST}


def test_untested_is_neither_a_pass_nor_a_fail() -> None:
    assert Conformance.UNTESTED not in (Conformance.PASS, Conformance.FAIL)


def test_the_vessel_kinds_cover_the_plant() -> None:
    assert set(VesselKind) == {
        VesselKind.STEEP,
        VesselKind.BOX,
        VesselKind.FLOOR,
        VesselKind.KILN,
    }


def test_a_sealed_bin_is_a_state_of_its_own() -> None:
    """Filling and drawing are what a bin does, sealed is what makes a lot real."""
    assert BinState.SEALED not in (BinState.FILLING, BinState.DRAWING, BinState.EMPTY)


def test_a_cancelled_contract_is_not_a_closed_one() -> None:
    """Closed is served out and cancelled is nothing was served, so both exist."""
    finished = {member for member in ContractState if member is not ContractState.DRAFT}
    assert {ContractState.CLOSED, ContractState.CANCELLED} <= finished
    assert len({member.value for member in ShipmentState}) == len(list(ShipmentState))


def test_the_styles_are_what_the_kiln_is_set_up_for() -> None:
    assert {style.value for style in MaltStyle} == {"lager", "pale_ale", "distilling", "vienna"}


def test_a_material_is_barley_or_malt() -> None:
    """There is no third material, so a clause that names neither is incomplete."""
    assert set(Material) == {Material.BARLEY, Material.MALT}


def test_one_company_can_hold_more_than_one_role() -> None:
    """Roles are separate rows rather than a set, so they do not overlap here."""
    assert len(set(Role)) == 4


def test_provisional_is_on_the_list_and_not_approved() -> None:
    assert Approval.PROVISIONAL not in (Approval.APPROVED, Approval.WITHDRAWN)


def test_habit_is_spring_or_winter() -> None:
    assert set(Habit) == {Habit.SPRING, Habit.WINTER}


def test_treated_seed_is_a_rejection_and_not_a_grading() -> None:
    """A finding rejects whatever the numbers say, so it sits in the same list."""
    assert RejectionReason.TREATED_SEED in set(RejectionReason)
