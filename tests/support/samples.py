"""Analyses the tests build on.

`barley_sample` passes every screen. `malt_analysis` carries a moisture and
whatever else it is given, because an analysis without one is refused.
"""

from __future__ import annotations

import datetime as dt

from culmbin.model.enums import Basis, Material
from culmbin.model.results import Analysis, Result, analysis_of

GOOD_BARLEY: dict[str, float] = {
    "moisture": 12.5,
    "screenings": 1.4,
    "germ_capacity": 99.0,
    "germ_energy": 98.0,
    "admixture": 0.4,
}
GOOD_NITROGEN = 1.62

DRY_BASIS_CODES = frozenset(
    {"nitrogen", "extract_fine", "extract_coarse", "total_protein", "soluble_protein"}
)


def barley_sample(
    reference: str = "B-1", taken: dt.date = dt.date(2025, 11, 4), **overrides: float
) -> Analysis:
    """A barley sample that passes every screen, with anything overridden.

    Germinative energy is always here, because a new crop screen needs it
    and an old crop screen ignores it. Leaving it out by default is what let
    two files disagree about what this helper meant.
    """
    values = dict(GOOD_BARLEY)
    nitrogen = overrides.pop("nitrogen", GOOD_NITROGEN)
    values.update(overrides)
    results = [Result(code, value) for code, value in values.items()]
    results.append(Result("nitrogen", nitrogen, Basis.DRY))
    return analysis_of(reference, Material.BARLEY, taken, results)


def malt_analysis(
    reference: str = "M-1",
    taken: dt.date = dt.date(2025, 11, 12),
    moisture: float = 4.2,
    **values: float,
) -> Analysis:
    """A malt analysis with a moisture in it and whatever else is asked for."""
    results = [Result("malt_moisture", moisture)]
    for code, value in values.items():
        basis = Basis.DRY if code in DRY_BASIS_CODES else None
        results.append(Result(code, value, basis))
    return analysis_of(reference, Material.MALT, taken, results)
