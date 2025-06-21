"""Bins, what is in them, and the lots drawn out.

The rule these are about is that segregation propagates and does not
recover, and that a lot out of a mixed bin has no variety to declare rather
than a variety nobody has looked up.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import SegregationError, StateError, ValidationError
from culmbin.model.enums import BinState, MaltStyle
from culmbin.model.lots import Bin, Contents, MaltLot, blended_contents

SEALED = dt.date(2025, 11, 12)


def malt_bin(code: str = "B04", **kwargs: object) -> Bin:
    fields: dict[str, object] = {"capacity_tonnes": 220.0}
    fields.update(kwargs)
    return Bin(code=code, **fields)  # type: ignore[arg-type]


def contents(code: str = "B04", **kwargs: object) -> Contents:
    fields: dict[str, object] = {
        "tonnes": 180.0,
        "moisture": 4.3,
        "varieties": frozenset({"LAUR"}),
        "crop_years": frozenset({2025}),
        "styles": frozenset({MaltStyle.PALE_ALE}),
    }
    fields.update(kwargs)
    return Contents(code=code, **fields)  # type: ignore[arg-type]


def lot(code: str = "L-2025-0412", **kwargs: object) -> MaltLot:
    fields: dict[str, object] = {
        "bin_code": "B04",
        "sealed": SEALED,
        "tonnes": 180.0,
        "moisture": 4.3,
        "varieties": frozenset({"LAUR"}),
        "crop_years": frozenset({2025}),
        "style": MaltStyle.PALE_ALE,
    }
    fields.update(kwargs)
    return MaltLot(code=code, **fields)  # type: ignore[arg-type]


def test_a_bin_prints_its_state() -> None:
    assert str(malt_bin()) == "B04 empty"
    assert str(malt_bin(state=BinState.FILLING, mixed=True)) == "B04 filling mixed"


def test_a_bin_needs_a_code_and_a_capacity() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        malt_bin(" ")
    with pytest.raises(ValidationError, match="holds 0.0"):
        malt_bin(capacity_tonnes=0.0)


def test_an_empty_bin_can_still_be_marked_mixed() -> None:
    """That is the state a bin sits in between being drawn down and being swept."""
    assert malt_bin(mixed=True).mixed


def test_an_empty_or_filling_bin_takes_malt() -> None:
    assert malt_bin().takes_malt
    assert malt_bin(state=BinState.FILLING).takes_malt


def test_a_sealed_bin_takes_nothing() -> None:
    """That is what makes the analysis mean anything."""
    assert not malt_bin(state=BinState.SEALED).takes_malt
    assert malt_bin(state=BinState.SEALED).gives_malt


def test_an_empty_bin_gives_nothing() -> None:
    assert not malt_bin().gives_malt


def test_marking_mixed_sticks() -> None:
    marked = malt_bin(state=BinState.FILLING).marked_mixed()
    assert marked.mixed
    assert marked.marked_mixed().mixed


def test_a_bin_drawn_empty_is_still_marked() -> None:
    """Coming back to empty is the level gauge, and the mark is the boot."""
    marked = malt_bin(state=BinState.DRAWING).marked_mixed()
    assert marked.in_state(BinState.EMPTY).mixed


def test_a_bin_keeps_its_mark_while_it_holds_malt() -> None:
    marked = malt_bin(state=BinState.FILLING).marked_mixed()
    assert marked.in_state(BinState.SEALED).mixed


def test_cleaning_out_takes_the_mark_off() -> None:
    dirty = malt_bin(state=BinState.FILLING).marked_mixed().in_state(BinState.EMPTY)
    assert not dirty.cleaned_out().mixed


def test_a_bin_with_malt_in_it_cannot_be_cleaned_out() -> None:
    with pytest.raises(StateError, match="cannot be cleaned out"):
        malt_bin(state=BinState.SEALED).cleaned_out()


def test_contents_work_their_dry_matter() -> None:
    assert contents().dry_tonnes == pytest.approx(180.0 * 0.957)


def test_an_empty_bin_is_empty() -> None:
    assert contents(tonnes=0.0).empty
    assert not contents().empty


def test_negative_contents_are_refused() -> None:
    with pytest.raises(ValidationError, match="holds -1.0"):
        contents(tonnes=-1.0)


def test_one_variety_in_the_bin_is_the_variety() -> None:
    assert contents().variety == "LAUR"
    assert contents().crop_year == 2025
    assert contents().style is MaltStyle.PALE_ALE


def test_two_varieties_in_the_bin_is_no_variety() -> None:
    mixed = contents(varieties=frozenset({"LAUR", "DIAB"}))
    assert mixed.variety is None


def test_two_crop_years_in_the_bin_is_no_crop_year() -> None:
    mixed = contents(crop_years=frozenset({2024, 2025}))
    assert mixed.crop_year is None
    assert mixed.style is MaltStyle.PALE_ALE


def test_a_lot_prints_its_variety_or_says_mixed() -> None:
    assert str(lot()) == "L-2025-0412 180.0t LAUR"
    assert str(lot(varieties=frozenset({"LAUR", "DIAB"}))) == "L-2025-0412 180.0t mixed"


def test_a_lot_needs_a_code_a_weight_and_a_parent() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        lot(" ")
    with pytest.raises(ValidationError, match="is 0.0 tonnes"):
        lot(tonnes=0.0)
    with pytest.raises(ValidationError, match="came from nothing"):
        lot(varieties=frozenset())


def test_a_lot_from_one_variety_declares_it() -> None:
    assert lot().declares_variety
    assert lot().serves("LAUR")
    assert not lot().serves("DIAB")


def test_a_lot_from_a_mixed_bin_declares_nothing() -> None:
    mixed = lot(varieties=frozenset({"LAUR", "DIAB"}))
    assert not mixed.declares_variety
    assert not mixed.serves("LAUR")


def test_a_mixed_lot_says_why_it_cannot_serve() -> None:
    """It is not the analysis being overruled, the analysis never knew."""
    mixed = lot(varieties=frozenset({"LAUR", "DIAB"}))
    with pytest.raises(SegregationError, match="no variety to declare"):
        mixed.check_serves("LAUR")


def test_the_wrong_variety_says_which_one_it_is() -> None:
    with pytest.raises(SegregationError, match="is LAUR and the contract wants DIAB"):
        lot().check_serves("DIAB")


def test_the_right_variety_passes_quietly() -> None:
    lot().check_serves("LAUR")


def test_a_lot_is_uncertified_until_an_analysis_is_written() -> None:
    assert not lot().certified
    assert lot(analysis="M-2025-0412").certified


def test_a_lot_works_its_dry_matter() -> None:
    assert lot().dry_tonnes == pytest.approx(180.0 * 0.957)


def test_a_blend_of_one_bin_is_that_bin() -> None:
    blended = blended_contents("plan", (contents(),))
    assert blended.tonnes == pytest.approx(180.0)
    assert blended.variety == "LAUR"


def test_a_blend_averages_moisture_over_the_wet_weight() -> None:
    """10 at 4.0 and 30 at 5.0 is 4.75, which is not 4.5."""
    parts = (contents("A", tonnes=10.0, moisture=4.0), contents("B", tonnes=30.0, moisture=5.0))
    assert blended_contents("plan", parts).moisture == pytest.approx(4.75)


def test_a_blend_of_two_varieties_has_none() -> None:
    parts = (
        contents("A", varieties=frozenset({"LAUR"})),
        contents("B", varieties=frozenset({"DIAB"})),
    )
    assert blended_contents("plan", parts).variety is None


def test_a_blend_of_one_variety_keeps_it() -> None:
    parts = (contents("A"), contents("B"))
    assert blended_contents("plan", parts).variety == "LAUR"


def test_a_blend_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least one part"):
        blended_contents("plan", ())


def test_a_blend_of_empty_bins_is_refused() -> None:
    with pytest.raises(ValidationError, match="empty bins"):
        blended_contents("plan", (contents(tonnes=0.0),))
