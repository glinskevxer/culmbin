"""Turning a grading into money."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import StateError, ValidationError
from culmbin.intake.grading import Adjustment, Grading, grade
from culmbin.intake.settlement import Settlement, settle, settle_or_none, statement_total
from culmbin.intake.standard import Standard
from culmbin.model.enums import Basis, IntakeOutcome, Material, RejectionReason
from culmbin.model.intake import Purchase
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.units.season import Window

HARVESTED = dt.date(2025, 8, 14)
ARRIVED = dt.date(2025, 11, 4)
STANDARD = Standard("malting 2025")
NET = 28.18


def purchase(**kwargs: object) -> Purchase:
    fields: dict[str, object] = {
        "code": "P-2025-014",
        "party": "HOLB",
        "variety": "LAUR",
        "crop_year": 2025,
        "tonnes": 480.0,
        "window": Window(dt.date(2025, 9, 1), dt.date(2025, 11, 30)),
        "standard": "malting 2025",
        "price_per_tonne": Decimal("232.50"),
        "signed": dt.date(2025, 3, 12),
    }
    fields.update(kwargs)
    return Purchase(**fields)  # type: ignore[arg-type]


def sample(**overrides: float) -> Analysis:
    values: dict[str, float] = {
        "moisture": 12.5,
        "screenings": 1.4,
        "germ_capacity": 99.0,
        "germ_energy": 98.0,
        "admixture": 0.4,
    }
    nitrogen = overrides.pop("nitrogen", 1.62)
    values.update(overrides)
    results = [Result(code, value) for code, value in values.items()]
    results.append(Result("nitrogen", nitrogen, Basis.DRY))
    return analysis_of("B-1", Material.BARLEY, ARRIVED, results)


def graded(**overrides: float) -> Grading:
    return grade("W-24188", STANDARD, NET, sample(**overrides), HARVESTED, ARRIVED)


def test_a_clean_load_is_worth_tonnes_times_price() -> None:
    settlement = settle(graded(), purchase())
    assert settlement.net_per_tonne == Decimal("232.50")
    assert settlement.value == Decimal("6551.85")


def test_a_deduction_comes_off_every_settled_tonne() -> None:
    """2.5 points of drying at 2.40 is 6.00 a tonne off 232.50."""
    settlement = settle(graded(moisture=15.0), purchase())
    assert settlement.net_per_tonne == Decimal("226.50")
    assert settlement.settled_tonnes < NET


def test_the_value_is_to_the_penny() -> None:
    settlement = settle(graded(moisture=15.0, nitrogen=1.95), purchase())
    assert settlement.value == settlement.value.quantize(Decimal("0.01"))


def test_a_rejected_load_cannot_be_settled() -> None:
    with pytest.raises(StateError, match="nothing to settle"):
        settle(graded(germ_capacity=90.0), purchase())


def test_the_refusal_says_what_it_was_rejected_for() -> None:
    with pytest.raises(StateError, match="germination"):
        settle(graded(germ_capacity=90.0), purchase())


def test_a_rejected_load_is_nothing_rather_than_zero_on_the_statement() -> None:
    assert settle_or_none(graded(germ_capacity=90.0), purchase()) is None


def test_an_accepted_load_comes_back_from_the_statement_walk() -> None:
    settlement = settle_or_none(graded(), purchase())
    assert settlement is not None
    assert settlement.value > Decimal("0")


def test_a_grading_on_another_standard_is_refused() -> None:
    with pytest.raises(ValidationError, match="is on"):
        settle(graded(), purchase(standard="malting 2024"))


def test_a_deduction_bigger_than_the_price_is_capped_at_nothing() -> None:
    """We pay nothing. The grower does not owe us for having delivered barley."""
    heavy = Grading(
        ticket="W-1",
        standard="malting 2025",
        outcome=IntakeOutcome.ACCEPTED_ON_DEDUCTION,
        net_tonnes=NET,
        settled_tonnes=NET,
        adjustments=(Adjustment(kind="drying", note="a very wet load", per_tonne=Decimal("400")),),
    )
    settlement = settle(heavy, purchase())
    assert settlement.capped
    assert settlement.net_per_tonne == Decimal("0.00")
    assert settlement.value == Decimal("0.00")


def test_an_ordinary_settlement_is_not_capped() -> None:
    assert not settle(graded(moisture=15.0), purchase()).capped


def test_a_settlement_prints_the_way_a_statement_line_reads() -> None:
    settlement = settle(graded(), purchase())
    assert str(settlement) == "W-24188 28.180t at 232.50 = 6551.85"


def test_a_settlement_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="settles"):
        Settlement("W-1", "P-1", 0.0, Decimal("232.50"), Decimal("0.00"), capped=False)


def test_a_settlement_at_no_price_is_refused() -> None:
    with pytest.raises(ValidationError, match="base price"):
        Settlement("W-1", "P-1", 10.0, Decimal("0"), Decimal("0.00"), capped=False)


def test_a_settlement_deducting_past_the_price_is_refused() -> None:
    with pytest.raises(ValidationError, match="more than the base price"):
        Settlement("W-1", "P-1", 10.0, Decimal("232.50"), Decimal("300.00"), capped=False)


def test_a_negative_deduction_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative deduction"):
        Settlement("W-1", "P-1", 10.0, Decimal("232.50"), Decimal("-1.00"), capped=False)


def test_a_statement_adds_the_rounded_lines() -> None:
    """Each line is rounded before the total, which is what the statement shows."""
    settlements = tuple(
        settle(grade(f"W-{n}", STANDARD, 11.111, sample(), HARVESTED, ARRIVED), purchase())
        for n in range(3)
    )
    assert statement_total(settlements) == Decimal("7749.93")


def test_rounding_once_at_the_end_would_give_a_different_total() -> None:
    """A penny out, and the penny is why the lines are rounded first."""
    settlements = tuple(
        settle(grade(f"W-{n}", STANDARD, 11.111, sample(), HARVESTED, ARRIVED), purchase())
        for n in range(3)
    )
    once = sum(
        (
            settlement.net_per_tonne * Decimal(str(settlement.settled_tonnes))
            for settlement in settlements
        ),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    assert once == Decimal("7749.92")
    assert statement_total(settlements) != once


def test_a_statement_of_nothing_is_nothing() -> None:
    assert statement_total(()) == Decimal("0.00")


def test_a_rejection_reason_is_readable_in_the_refusal() -> None:
    rejected = grade(
        "W-1",
        STANDARD,
        NET,
        sample(),
        HARVESTED,
        ARRIVED,
        findings=frozenset({RejectionReason.INSECT}),
    )
    with pytest.raises(StateError, match="insect"):
        settle(rejected, purchase())
