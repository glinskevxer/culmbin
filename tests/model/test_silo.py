"""Barley silos, and the proportional draw.

A silo is a mixed mass. The tests that carry the design are the ones about
apportioning a draw, because that is where the honest answer differs from
the one a first-in-first-out model would give.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import SegregationError, StateError, ValidationError
from culmbin.model.silo import Holding, Share, Silo, holding_of

BUILT = dt.date(1998, 4, 1)


def silo(code: str = "SL1", **kwargs: object) -> Silo:
    fields: dict[str, object] = {"capacity_tonnes": 400.0}
    fields.update(kwargs)
    return Silo(code=code, **fields)  # type: ignore[arg-type]


def holding(**kwargs: object) -> Holding:
    fields: dict[str, object] = {
        "code": "SL1",
        "tonnes": 400.0,
        "moisture": 12.4,
        "varieties": frozenset({"LAUR"}),
        "crop_years": frozenset({2025}),
        "shares": (Share("W-1", 300.0), Share("W-2", 100.0)),
    }
    fields.update(kwargs)
    return Holding(**fields)  # type: ignore[arg-type]


def test_a_silo_prints_its_size_and_its_mark() -> None:
    assert str(silo()) == "SL1 400t"
    assert str(silo().marked_mixed()) == "SL1 400t mixed"


def test_a_silo_needs_a_code_and_a_capacity() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        silo(" ")
    with pytest.raises(ValidationError, match="holds 0.0"):
        silo(capacity_tonnes=0.0)


def test_marking_a_silo_mixed_sticks_to_it() -> None:
    assert silo().marked_mixed().mixed
    assert silo().marked_mixed().marked_mixed().mixed


def test_sweeping_a_silo_takes_the_mark_off() -> None:
    assert not silo().marked_mixed().swept().mixed


def test_a_share_of_a_negative_tonnage_is_refused() -> None:
    with pytest.raises(ValidationError, match="share of"):
        Share("W-1", -1.0)


def test_a_holding_prints_what_is_in_it() -> None:
    assert str(holding()) == "SL1 400.00t LAUR at 12.40%"
    assert str(holding(varieties=frozenset({"LAUR", "DIAB"}))).endswith("mixed at 12.40%")


def test_an_empty_silo_is_empty() -> None:
    assert holding(tonnes=0.0, shares=()).empty
    assert not holding().empty


def test_one_variety_in_the_silo_is_the_variety() -> None:
    assert holding().variety == "LAUR"
    assert holding().crop_year == 2025


def test_two_varieties_in_the_silo_is_no_variety() -> None:
    assert holding(varieties=frozenset({"LAUR", "DIAB"})).variety is None
    assert holding(crop_years=frozenset({2024, 2025})).crop_year is None


def test_a_piece_of_the_right_variety_can_be_charged() -> None:
    holding().check_charges("LAUR")


def test_a_piece_of_the_wrong_variety_cannot_be() -> None:
    with pytest.raises(SegregationError, match="the piece says DIAB"):
        holding().check_charges("DIAB")


def test_nothing_can_be_charged_out_of_a_mixed_silo() -> None:
    """A piece out of it could not declare a variety, so it is refused here."""
    mixed = holding(varieties=frozenset({"LAUR", "DIAB"}))
    with pytest.raises(SegregationError, match="cannot declare a variety"):
        mixed.check_charges("LAUR")


def test_nothing_can_be_charged_out_of_an_empty_silo() -> None:
    with pytest.raises(StateError, match="nothing in it to charge"):
        holding(tonnes=0.0, shares=()).check_charges("LAUR")


def test_a_draw_carries_a_share_of_every_load() -> None:
    """Forty tonnes out of four hundred is a tenth of each."""
    shares = holding().apportion(40.0)
    assert {share.ticket: share.tonnes for share in shares} == {"W-1": 30.0, "W-2": 10.0}


def test_the_shares_add_up_to_exactly_what_was_drawn() -> None:
    """The last share takes the rounding, so nothing is lost or invented."""
    odd = holding(tonnes=333.0, shares=(Share("W-1", 111.0), Share("W-2", 222.0)))
    shares = odd.apportion(100.0)
    assert sum(share.tonnes for share in shares) == pytest.approx(100.0)


def test_drawing_the_whole_silo_takes_every_load() -> None:
    shares = holding().apportion(400.0)
    assert sum(share.tonnes for share in shares) == pytest.approx(400.0)
    assert len(shares) == 2


def test_drawing_more_than_is_there_is_refused() -> None:
    with pytest.raises(StateError, match="was drawn"):
        holding().apportion(500.0)


def test_a_draw_of_nothing_is_not_a_draw() -> None:
    with pytest.raises(ValidationError, match="not a draw"):
        holding().apportion(0.0)


def test_a_silo_with_nothing_recorded_cannot_apportion() -> None:
    with pytest.raises(StateError, match="nothing recorded as going into it"):
        holding(shares=()).apportion(10.0)


def test_what_is_left_is_what_was_not_drawn() -> None:
    left = holding().after(40.0)
    assert {share.ticket: share.tonnes for share in left} == {"W-1": 270.0, "W-2": 90.0}


def test_a_load_drawn_right_out_is_not_left_behind() -> None:
    one_load = holding(tonnes=100.0, shares=(Share("W-1", 100.0),))
    assert one_load.after(100.0) == ()


def test_a_holding_builds_out_of_the_loads_that_went_in() -> None:
    built = holding_of("SL1", [("W-1", 30.0, 12.0), ("W-2", 10.0, 13.0)], ["LAUR"], [2025])
    assert built.tonnes == pytest.approx(40.0)
    assert built.moisture == pytest.approx(12.25)
    assert built.variety == "LAUR"


def test_a_silo_nothing_has_gone_into_is_empty() -> None:
    assert holding_of("SL1", [], [], []).empty


def test_a_negative_holding_is_refused() -> None:
    with pytest.raises(ValidationError, match="holds -1.0"):
        holding(tonnes=-1.0)
