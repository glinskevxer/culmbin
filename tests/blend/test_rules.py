"""Which weight each analyte blends over."""

from __future__ import annotations

import pytest

from culmbin.blend.rules import BlendRule, blendable, blends_on_dry, rule_for
from culmbin.errors import NotFoundError
from culmbin.model.analytes import analytes_for
from culmbin.model.enums import Material


def test_extract_blends_over_dry_matter() -> None:
    assert rule_for("extract_fine") is BlendRule.DRY_WEIGHT
    assert blends_on_dry("total_protein")


def test_colour_blends_over_the_weight_as_it_lies() -> None:
    """It is measured on a wort made from malt out of the bag."""
    assert rule_for("colour") is BlendRule.AS_IS_WEIGHT
    assert not blends_on_dry("colour")


def test_moisture_is_neither_of_the_other_two() -> None:
    assert rule_for("malt_moisture") is BlendRule.MOISTURE


def test_the_kolbach_index_does_not_blend_at_all() -> None:
    assert rule_for("kolbach") is BlendRule.DERIVED


def test_an_analyte_that_is_not_one_says_so() -> None:
    with pytest.raises(NotFoundError, match="no analyte called"):
        rule_for("pH")


def test_a_malt_analyte_with_no_rule_says_it_is_a_gap_here() -> None:
    """A barley analyte is not blended, and the message points at this table."""
    with pytest.raises(NotFoundError, match="how 'moisture' blends"):
        rule_for("moisture")


def test_every_blendable_analyte_is_a_malt_analyte() -> None:
    malt = {item.code for item in analytes_for(Material.MALT)}
    assert blendable() <= malt


def test_every_malt_analyte_has_a_rule() -> None:
    """A gap here is a certificate line a blend cannot predict."""
    malt = {item.code for item in analytes_for(Material.MALT)}
    assert blendable() == malt
