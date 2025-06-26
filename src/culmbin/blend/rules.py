"""Which weight each analyte averages over, and the two that do neither.

This is the module the rest of the blending sits on, and it is short because
the whole difficulty is in getting four lines right.

**Most results average over dry matter.** Extract, protein, nitrogen,
diastatic power and free amino nitrogen are all fractions of, or activities
per, the dry weight. Two lots of equal delivered tonnage do not contribute
equally if their moistures differ, and the wetter one contributes less.

**Colour averages over the weight as it lies.** Colour is measured on a wort
made from a fixed weight of malt as it comes out of the bag. Friability and
homogeneity are the same: they are measured on the malt in front of you.

**Moisture averages over the wet weight**, because water is a fraction of
the wet weight. It is the one that is neither of the other two.

**The Kolbach index does not average at all.** It is soluble protein over
total protein, and a ratio of two means is not the mean of the ratios unless
every denominator is the same. It is worked from the blended parts, which is
what `DERIVED` means here.

Getting one of these wrong is worth a few tenths of a percent of extract or
a point of colour. That is inside the range a specification argues about and
outside the range anybody notices, which is the worst place for a mistake to
sit.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum, unique

from culmbin.errors import NotFoundError
from culmbin.model.analytes import ANALYTES


@unique
class BlendRule(StrEnum):
    """How one analyte behaves when two lots are run together."""

    DRY_WEIGHT = "dry_weight"
    AS_IS_WEIGHT = "as_is_weight"
    MOISTURE = "moisture"
    DERIVED = "derived"


_RULES: Mapping[str, BlendRule] = {
    "malt_moisture": BlendRule.MOISTURE,
    "extract_fine": BlendRule.DRY_WEIGHT,
    "extract_coarse": BlendRule.DRY_WEIGHT,
    "total_protein": BlendRule.DRY_WEIGHT,
    "soluble_protein": BlendRule.DRY_WEIGHT,
    "diastatic_power": BlendRule.DRY_WEIGHT,
    "fan": BlendRule.DRY_WEIGHT,
    "beta_glucan": BlendRule.DRY_WEIGHT,
    "colour": BlendRule.AS_IS_WEIGHT,
    "friability": BlendRule.AS_IS_WEIGHT,
    "viscosity": BlendRule.AS_IS_WEIGHT,
    "homogeneity": BlendRule.AS_IS_WEIGHT,
    "kolbach": BlendRule.DERIVED,
}

DERIVED_FROM: Mapping[str, tuple[str, str]] = {
    "kolbach": ("soluble_protein", "total_protein"),
}
"""What a derived result is worked out of, once the parts have been blended."""


def rule_for(code: str) -> BlendRule:
    """How an analyte blends, or say that nothing here knows.

    A malt analyte with no rule is a gap in this table rather than something
    that cannot be blended, and the message says so, because the fix is one
    line here and not a conversation about arithmetic.
    """
    if code not in ANALYTES:
        raise NotFoundError(f"no analyte called {code!r}")
    if code not in _RULES:
        raise NotFoundError(f"nothing here says how {code!r} blends")
    return _RULES[code]


def blendable() -> frozenset[str]:
    """Every analyte a blend can be predicted for."""
    return frozenset(_RULES)


def blends_on_dry(code: str) -> bool:
    """Whether an analyte averages over dry matter."""
    return rule_for(code) is BlendRule.DRY_WEIGHT
