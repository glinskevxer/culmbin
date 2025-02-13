"""The analytical scales, and the two of them that do not average.

A malt analysis is reported on half a dozen scales that mean the same thing
to different customers. A German brewer wants colour in EBC and diastatic
power in Windisch Kolbach. An American one wants Lovibond and Lintner. A
Scottish distiller wants hot water extract in litre degrees per kilogram and
does not care about colour at all.

The conversions are exact in the sense that they are the industry formulae,
which are themselves fits. Converting round the loop and back is stable to
well inside the precision anything is reported at, and there is a test that
holds it there.
"""

from __future__ import annotations

from collections.abc import Sequence

from culmbin.errors import ValidationError

SRM_PER_LOVIBOND = 1.3546
SRM_LOVIBOND_OFFSET = 0.76
EBC_PER_SRM = 1.97
"""The two hops between Lovibond and EBC, kept apart because SRM is a stop.

Nobody here reports SRM. It is in the middle of the Lovibond to EBC formula
and pretending otherwise would make the constants look arbitrary.
"""

WK_PER_LINTNER = 3.5
WK_LINTNER_OFFSET = 16.0

HWE_PER_EXTRACT_POINT = 3.8674
"""Litre degrees per kilogram for each percent of extract as it lies.

This is the conversion the Institute of Brewing tables use and it is the one
the distilling customers check our certificate against, so it is a constant
here rather than a number somebody types into a report.
"""

NITROGEN_TO_PROTEIN = 6.25
"""Barley and malt protein are nitrogen times this, and only this.

Wheat uses 5.7 and the difference is large enough to fail a specification.
The package does not malt wheat, so the factor is fixed rather than an
argument that could be got wrong.
"""


def _check_positive(value: float, field: str) -> float:
    """Return the value, or raise if it is not something a scale can hold."""
    if value < 0.0:
        raise ValidationError(f"{field} {value:.3f} is negative")
    return value


def ebc_from_lovibond(lovibond: float) -> float:
    """Colour in EBC from colour in degrees Lovibond."""
    _check_positive(lovibond, "colour")
    return (lovibond * SRM_PER_LOVIBOND - SRM_LOVIBOND_OFFSET) * EBC_PER_SRM


def lovibond_from_ebc(ebc: float) -> float:
    """Colour in degrees Lovibond from colour in EBC."""
    _check_positive(ebc, "colour")
    return (ebc / EBC_PER_SRM + SRM_LOVIBOND_OFFSET) / SRM_PER_LOVIBOND


def wk_from_lintner(lintner: float) -> float:
    """Diastatic power in Windisch Kolbach from degrees Lintner."""
    _check_positive(lintner, "diastatic power")
    return lintner * WK_PER_LINTNER - WK_LINTNER_OFFSET


def lintner_from_wk(wk: float) -> float:
    """Diastatic power in degrees Lintner from Windisch Kolbach.

    The offset means the WK scale runs below zero and a small negative WK is
    a real reading on a very weak malt. Zero Lintner is minus sixteen WK, and
    below that there is no Lintner figure to report at all.
    """
    lintner = (wk + WK_LINTNER_OFFSET) / WK_PER_LINTNER
    if lintner < 0.0:
        raise ValidationError(f"{wk:.1f} WK is below the bottom of the Lintner scale")
    return lintner


def kolbach_index(soluble_protein: float, total_protein: float) -> float:
    """Soluble protein as a percentage of total protein, both on dry matter.

    The number the trade calls modification. Mixing bases here is the classic
    way to get a plausible wrong answer, so both arguments must already be on
    dry matter and the caller is the one who has to have done that.
    """
    _check_positive(soluble_protein, "soluble protein")
    if total_protein <= 0.0:
        raise ValidationError(f"total protein {total_protein:.2f} is not a divisor")
    if soluble_protein > total_protein:
        raise ValidationError(
            f"soluble protein {soluble_protein:.2f} is above total protein {total_protein:.2f}"
        )
    return soluble_protein / total_protein * 100.0


def protein_from_nitrogen(nitrogen: float) -> float:
    """Protein from a nitrogen figure, on whatever basis the nitrogen was on."""
    return _check_positive(nitrogen, "nitrogen") * NITROGEN_TO_PROTEIN


def nitrogen_from_protein(protein: float) -> float:
    """Nitrogen from a protein figure, on whatever basis the protein was on."""
    return _check_positive(protein, "protein") / NITROGEN_TO_PROTEIN


def hot_water_extract(extract_as_is: float) -> float:
    """Litre degrees per kilogram from extract as it lies.

    The argument is on the weight as it lies rather than on dry matter,
    because that is what the customer's mash tun sees, and passing a dry
    basis extract in here quietly overstates the malt by about four percent.
    """
    return _check_positive(extract_as_is, "extract") * HWE_PER_EXTRACT_POINT


def weighted_mean(parts: Sequence[tuple[float, float]]) -> float:
    """The dry weight weighted mean of a set of results.

    This is the right rule for extract, protein, nitrogen, diastatic power
    and beta-glucan, and the wrong rule for colour. Each part is a dry weight
    and the result on that weight.
    """
    if not parts:
        raise ValidationError("a weighted mean needs at least one part")
    weight = 0.0
    total = 0.0
    for part_weight, value in parts:
        _check_positive(part_weight, "weight")
        weight += part_weight
        total += part_weight * value
    if weight == 0.0:
        raise ValidationError("a weighted mean over no weight has no value")
    return total / weight


def blend_kolbach_index(parts: Sequence[tuple[float, float, float]]) -> float:
    """The Kolbach index of a blend, which is not the mean of the indices.

    Each part is a dry weight, its soluble protein and its total protein,
    both on dry matter. The blend's index is the blended soluble over the
    blended total, because a ratio of two averages is not the average of the
    ratios unless every denominator is the same.

    This is the one place in the package where doing the obvious thing gives
    an answer that is wrong by a couple of points, which is inside the range
    a specification argues about and outside the range anybody notices.
    """
    if not parts:
        raise ValidationError("a blend needs at least one part")
    soluble = weighted_mean([(weight, value) for weight, value, _ in parts])
    total = weighted_mean([(weight, value) for weight, _, value in parts])
    return kolbach_index(soluble, total)
