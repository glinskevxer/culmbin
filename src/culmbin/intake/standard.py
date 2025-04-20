"""The quality standard a purchase was signed against, and the screen.

A standard is two different sorts of number in one record, and keeping them
apart is the whole point of this module.

The rejection thresholds decide whether a load comes in at all. The schedule
thresholds decide what an accepted load is worth. They look alike, they sit
in the same table on the contract, and they are not the same kind of thing:
a load over a rejection threshold has no settlement, and asking what it
would have been worth is a question with no answer.

The other thing here is that one of the rejections depends on the date. New
crop barley inside dormancy has to pass germinative energy as well as
capacity, because capacity says the grain is alive and energy says it will
actually come away in the steep. Old crop only has to pass capacity, and the
same sample, arriving three weeks later, is a different answer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from culmbin.errors import ValidationError
from culmbin.model.analytes import analyte
from culmbin.model.enums import Basis, Material, RejectionReason
from culmbin.model.results import Analysis
from culmbin.units.season import is_new_crop

SCREEN_CODES: tuple[str, ...] = (
    "moisture",
    "nitrogen",
    "screenings",
    "germ_capacity",
    "admixture",
)
"""Every analyte the screen looks at on any load.

Germinative energy is not here because it is only looked at on new crop, and
a list that included it would say every old crop sample was short of a
result it does not need.
"""


@dataclass(frozen=True, slots=True)
class Standard:
    """The quality standard named on a purchase.

    Every threshold is on the basis the analyte is reported on: nitrogen on
    dry matter, everything else as it lies. That is not a convention this
    record enforces, it is what the assessment does, and the analysis is
    what converts.
    """

    name: str
    moisture_base: float = 12.5
    moisture_reject: float = 20.0
    nitrogen_min: float = 1.35
    nitrogen_max: float = 1.85
    nitrogen_reject: float = 2.05
    screenings_free: float = 2.0
    screenings_reject: float = 5.0
    germination_floor: float = 98.0
    energy_floor: float = 95.0
    admixture_reject: float = 2.0
    drying_per_point: Decimal = Decimal("2.40")
    nitrogen_step: float = 0.05
    nitrogen_per_step: Decimal = Decimal("1.50")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("a standard needs a name")
        if self.moisture_base >= self.moisture_reject:
            raise ValidationError(
                f"{self.name} pays down to {self.moisture_base} "
                f"and rejects at {self.moisture_reject}"
            )
        if self.nitrogen_min > self.nitrogen_max:
            raise ValidationError(f"{self.name} has a nitrogen band the wrong way round")
        if self.nitrogen_max > self.nitrogen_reject:
            raise ValidationError(
                f"{self.name} rejects at {self.nitrogen_reject} nitrogen "
                f"and deducts up to {self.nitrogen_max}"
            )
        if self.screenings_free >= self.screenings_reject:
            raise ValidationError(f"{self.name} allows more screenings than it rejects at")
        if self.nitrogen_step <= 0.0:
            raise ValidationError(f"{self.name} has a nitrogen step of nothing")
        if not 0.0 < self.germination_floor <= 100.0:
            raise ValidationError(
                f"{self.name} has a germination floor of {self.germination_floor}"
            )
        if not 0.0 < self.energy_floor <= 100.0:
            raise ValidationError(f"{self.name} has an energy floor of {self.energy_floor}")


def missing_for_screen(analysis: Analysis, new_crop: bool) -> tuple[str, ...]:
    """Every result the screen needs and the analysis has not got.

    New crop needs germinative energy as well, which is the one place the
    list of results a sample needs depends on when it arrived.
    """
    wanted = [*SCREEN_CODES, "germ_energy"] if new_crop else list(SCREEN_CODES)
    return tuple(code for code in wanted if code not in analysis)


def screen(
    standard: Standard,
    analysis: Analysis,
    harvested: dt.date,
    arrived: dt.date,
    findings: frozenset[RejectionReason] = frozenset(),
) -> tuple[RejectionReason, ...]:
    """Every reason this load cannot be taken in, in a settled order.

    An empty result means the load is accepted, which may still be on a
    deduction. The order is the order of `RejectionReason`, so two loads
    that fail on the same things list them the same way and a report can be
    compared with last week's.
    """
    if analysis.material is not Material.BARLEY:
        raise ValidationError(
            f"the screen is for barley and this is a {analysis.material} analysis"
        )
    new_crop = is_new_crop(arrived, harvested)
    missing = missing_for_screen(analysis, new_crop)
    if missing:
        raise ValidationError(
            f"this sample cannot be screened without {', '.join(analyte(c).label for c in missing)}"
        )
    reasons = set(findings)
    if analysis.value_on("germ_capacity", None) < standard.germination_floor:
        reasons.add(RejectionReason.GERMINATION)
    if new_crop and analysis.value_on("germ_energy", None) < standard.energy_floor:
        reasons.add(RejectionReason.GERMINATION)
    if analysis.value_on("moisture", None) > standard.moisture_reject:
        reasons.add(RejectionReason.MOISTURE)
    if analysis.value_on("screenings", None) > standard.screenings_reject:
        reasons.add(RejectionReason.SCREENINGS)
    if analysis.value_on("nitrogen", Basis.DRY) > standard.nitrogen_reject:
        reasons.add(RejectionReason.NITROGEN)
    if analysis.value_on("admixture", None) > standard.admixture_reject:
        reasons.add(RejectionReason.ADMIXTURE)
    return tuple(reason for reason in RejectionReason if reason in reasons)
