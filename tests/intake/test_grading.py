"""Grading a load.

The rule these are mostly about is that a rejection is not the bottom of the
schedule, and the second one is that the price adjustments are per settled
tonne, so a weight adjustment moves them.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ValidationError
from culmbin.intake.grading import Adjustment, Grading, grade
from culmbin.intake.standard import Standard
from culmbin.model.enums import IntakeOutcome, RejectionReason
from culmbin.model.results import Analysis
from culmbin.units.mass import at_moisture
from tests.support.samples import barley_sample

HARVESTED = dt.date(2025, 8, 14)
ARRIVED = dt.date(2025, 11, 4)
STANDARD = Standard("malting 2025")
NET = 28.18


def sample(**overrides: float) -> Analysis:
    return barley_sample("B-2025-1104-01", ARRIVED, **overrides)


def graded(**overrides: float) -> Grading:
    return grade("W-24188", STANDARD, NET, sample(**overrides), HARVESTED, ARRIVED)


def test_a_clean_load_settles_at_what_arrived() -> None:
    result = graded()
    assert result.outcome is IntakeOutcome.ACCEPTED
    assert result.settled_tonnes == pytest.approx(NET)
    assert result.adjustments == ()
    assert result.shrinkage_tonnes == pytest.approx(0.0)


def test_a_rejected_load_has_no_settlement_at_all() -> None:
    """The schedule does not apply, which is the difference from a heavy deduction."""
    result = graded(germ_capacity=90.0)
    assert result.rejected
    assert result.settled_tonnes == 0.0
    assert result.adjustments == ()
    assert result.rejections == (RejectionReason.GERMINATION,)


def test_a_load_that_would_have_been_deducted_and_is_rejected_is_just_rejected() -> None:
    result = graded(germ_capacity=90.0, moisture=15.0, screenings=3.0, nitrogen=1.95)
    assert result.rejected
    assert result.adjustments == ()
    assert result.price_adjustment == Decimal("0.00")


def test_screenings_over_the_free_allowance_come_off_the_weight() -> None:
    """3.4 percent against a 2.0 allowance is 1.4 percent of the load."""
    result = graded(screenings=3.4)
    assert result.settled_tonnes == pytest.approx(NET * (1 - 0.014))
    assert [line.kind for line in result.adjustments] == ["screenings"]


def test_screenings_inside_the_allowance_come_off_nothing() -> None:
    assert graded(screenings=2.0).adjustments == ()


def test_moisture_over_the_base_comes_off_the_weight() -> None:
    result = graded(moisture=15.0)
    assert result.settled_tonnes == pytest.approx(at_moisture(NET, 15.0, 12.5))
    assert "moisture" in [line.kind for line in result.adjustments]


def test_moisture_under_the_base_does_not_add_weight() -> None:
    """The contract is written one way round and this is the way round it is."""
    result = graded(moisture=11.0)
    assert result.settled_tonnes == pytest.approx(NET)
    assert result.lines_of("moisture") == ()


def test_a_drying_charge_is_per_point_over_the_base() -> None:
    """2.5 points at 2.40 a point is 6.00 off every settled tonne."""
    result = graded(moisture=15.0)
    charge = result.lines_of("drying")[0]
    assert charge.per_tonne == Decimal("6.00")
    assert charge.tonnes == 0.0


def test_there_is_no_drying_charge_at_the_base() -> None:
    assert graded(moisture=12.5).lines_of("drying") == ()


def test_a_nitrogen_deduction_is_in_whole_steps() -> None:
    """1.95 against a 1.85 band is two steps of 0.05, which is 3.00 a tonne."""
    line = graded(nitrogen=1.95).lines_of("nitrogen")[0]
    assert line.per_tonne == Decimal("3.00")


def test_a_hundredth_over_the_band_pays_the_whole_first_step() -> None:
    line = graded(nitrogen=1.86).lines_of("nitrogen")[0]
    assert line.per_tonne == Decimal("1.50")


def test_nitrogen_on_the_band_is_not_deducted() -> None:
    assert graded(nitrogen=1.85).lines_of("nitrogen") == ()


def test_low_nitrogen_is_not_deducted() -> None:
    assert graded(nitrogen=1.20).lines_of("nitrogen") == ()


def test_the_screenings_come_off_before_the_moisture() -> None:
    """Both are multiplicative, so the settled weight is the same either way."""
    result = graded(screenings=3.4, moisture=15.0)
    expected = at_moisture(NET * (1 - 0.014), 15.0, 12.5)
    assert result.settled_tonnes == pytest.approx(expected)


def test_the_weight_adjustments_move_what_the_charges_are_worth() -> None:
    """The drying charge is per settled tonne, so screenings make it smaller."""
    clean = graded(moisture=15.0)
    screened = graded(moisture=15.0, screenings=3.4)
    per_tonne = clean.lines_of("drying")[0].per_tonne
    assert per_tonne == screened.lines_of("drying")[0].per_tonne
    assert screened.settled_tonnes < clean.settled_tonnes


def test_the_price_adjustment_adds_the_lines_up() -> None:
    result = graded(moisture=15.0, nitrogen=1.95)
    assert result.price_adjustment == Decimal("9.00")


def test_a_deducted_load_says_so_in_its_outcome() -> None:
    assert graded(moisture=15.0).outcome is IntakeOutcome.ACCEPTED_ON_DEDUCTION


def test_a_load_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="net weight of"):
        grade("W-1", STANDARD, 0.0, sample(), HARVESTED, ARRIVED)


def test_a_finding_rejects_a_load_that_grades_perfectly() -> None:
    result = grade(
        "W-1",
        STANDARD,
        NET,
        sample(),
        HARVESTED,
        ARRIVED,
        findings=frozenset({RejectionReason.TREATED_SEED}),
    )
    assert result.rejected
    assert result.rejections == (RejectionReason.TREATED_SEED,)


def test_an_adjustment_is_a_weight_or_a_price_and_not_both() -> None:
    with pytest.raises(ValidationError, match="both a weight and a price"):
        Adjustment(kind="drying", note="both", tonnes=1.0, per_tonne=Decimal("1.00"))


def test_an_adjustment_needs_a_kind() -> None:
    with pytest.raises(ValidationError, match="needs a kind"):
        Adjustment(kind=" ", note="nothing", tonnes=1.0)


def test_a_negative_adjustment_is_refused() -> None:
    with pytest.raises(ValidationError, match="takes off"):
        Adjustment(kind="drying", note="negative", tonnes=-1.0)
    with pytest.raises(ValidationError, match="a tonne"):
        Adjustment(kind="drying", note="negative", per_tonne=Decimal("-1.00"))


def test_an_adjustment_prints_the_way_the_note_reads() -> None:
    weight = Adjustment(kind="screenings", note="screenings 3.4 over 2.0", tonnes=0.394)
    price = Adjustment(kind="drying", note="drying 2.5 points", per_tonne=Decimal("6.00"))
    assert str(weight) == "screenings 3.4 over 2.0 -0.394t"
    assert str(price) == "drying 2.5 points -6.00/t"


def test_a_rejection_with_no_reason_is_refused() -> None:
    with pytest.raises(ValidationError, match="no reason says why"):
        Grading("W-1", "s", IntakeOutcome.REJECTED, NET, 0.0)


def test_a_rejection_that_still_settles_is_refused() -> None:
    with pytest.raises(ValidationError, match="still has a settlement"):
        Grading(
            "W-1",
            "s",
            IntakeOutcome.REJECTED,
            NET,
            10.0,
            rejections=(RejectionReason.MOISTURE,),
        )


def test_an_acceptance_carrying_a_reason_is_refused() -> None:
    with pytest.raises(ValidationError, match="carries a rejection reason"):
        Grading(
            "W-1",
            "s",
            IntakeOutcome.ACCEPTED,
            NET,
            NET,
            rejections=(RejectionReason.MOISTURE,),
        )


def test_settling_more_than_arrived_is_refused() -> None:
    with pytest.raises(ValidationError, match="on 28.180t delivered"):
        Grading("W-1", "s", IntakeOutcome.ACCEPTED, NET, NET + 1.0)
