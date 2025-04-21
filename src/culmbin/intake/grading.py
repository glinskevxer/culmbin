"""Grading an accepted load: what weight is settled and what comes off the price.

There are two sorts of adjustment and they are not interchangeable.

A **weight** adjustment changes how many tonnes we agree arrived. Screenings
are the obvious one: the small corns go over the 2.2 millimetre sieve and
into the screenings bin, and nobody is paying malting barley money for them.
Moisture is the other: a load at fifteen percent has three percent more water
in it than the contract base, and the contract is written on weight at the
base moisture.

A **price** adjustment changes what a settled tonne is worth. The drying
charge is a real cost we incur, and the nitrogen deduction is the grower
being paid less for barley that will make less extract.

The order matters because the price adjustments are per settled tonne. Take
the screenings off first and the drying charge is smaller, which is right:
we do not dry the screenings, they went in a different bin.

And nothing in here applies to a rejected load. A rejection is not the bottom
row of the schedule. There is no settled weight and no deduction, because
the barley went back down the road.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from culmbin.errors import ValidationError
from culmbin.intake.standard import Standard, screen
from culmbin.model.enums import Basis, IntakeOutcome, RejectionReason
from culmbin.model.results import Analysis
from culmbin.units.mass import at_moisture

PENCE = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Adjustment:
    """One line of the grading, as it appears on the settlement note.

    `tonnes` is what came off the weight and `per_tonne` is what came off the
    price of every settled tonne. A line has one or the other and never
    both, because a line that had both could not be explained to a grower.
    """

    kind: str
    note: str
    tonnes: float = 0.0
    per_tonne: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValidationError("an adjustment needs a kind")
        if self.tonnes < 0.0:
            raise ValidationError(f"the {self.kind} line takes off {self.tonnes} tonnes")
        if self.per_tonne < 0:
            raise ValidationError(f"the {self.kind} line takes off {self.per_tonne} a tonne")
        if self.tonnes > 0.0 and self.per_tonne > 0:
            raise ValidationError(f"the {self.kind} line is both a weight and a price")

    @property
    def is_weight(self) -> bool:
        """Whether this line came off the weight."""
        return self.tonnes > 0.0

    def __str__(self) -> str:
        if self.is_weight:
            return f"{self.note} -{self.tonnes:.3f}t"
        return f"{self.note} -{self.per_tonne:.2f}/t"


@dataclass(frozen=True, slots=True)
class Grading:
    """What a load came to.

    A rejected grading has a settled weight of nothing and no adjustments,
    which is what makes it different from a load that was very heavily
    deducted.
    """

    ticket: str
    standard: str
    outcome: IntakeOutcome
    net_tonnes: float
    settled_tonnes: float
    rejections: tuple[RejectionReason, ...] = ()
    adjustments: tuple[Adjustment, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome is IntakeOutcome.REJECTED:
            if not self.rejections:
                raise ValidationError(f"{self.ticket} is rejected and no reason says why")
            if self.settled_tonnes != 0.0 or self.adjustments:
                raise ValidationError(f"{self.ticket} is rejected and still has a settlement")
        elif self.rejections:
            raise ValidationError(f"{self.ticket} was accepted and carries a rejection reason")
        if self.settled_tonnes > self.net_tonnes + 1e-9:
            raise ValidationError(
                f"{self.ticket} settles {self.settled_tonnes:.3f}t "
                f"on {self.net_tonnes:.3f}t delivered"
            )

    @property
    def rejected(self) -> bool:
        """Whether the load went back."""
        return self.outcome is IntakeOutcome.REJECTED

    @property
    def shrinkage_tonnes(self) -> float:
        """The difference between what arrived and what is paid for."""
        return self.net_tonnes - self.settled_tonnes

    @property
    def price_adjustment(self) -> Decimal:
        """Everything coming off the price of a settled tonne."""
        return sum((line.per_tonne for line in self.adjustments), Decimal("0.00"))

    def lines_of(self, kind: str) -> tuple[Adjustment, ...]:
        """Every adjustment of one kind."""
        return tuple(line for line in self.adjustments if line.kind == kind)


def _drying(standard: Standard, moisture: float) -> Adjustment | None:
    """The drying charge, or nothing if the load came in at or under base."""
    points = round(moisture - standard.moisture_base, 1)
    if points <= 0.0:
        return None
    charge = (standard.drying_per_point * Decimal(str(points))).quantize(PENCE, ROUND_HALF_UP)
    return Adjustment(
        kind="drying",
        note=f"drying {points:.1f} points from {standard.moisture_base:.1f}",
        per_tonne=charge,
    )


def _nitrogen(standard: Standard, nitrogen: float) -> Adjustment | None:
    """The nitrogen deduction, in whole steps, or nothing inside the band.

    The step is rounded up. A load a hundredth of a percent over the band
    pays the whole first step, which is what the contract says and what the
    grower expects, because the alternative is a schedule with no steps in
    it at all.
    """
    over = nitrogen - standard.nitrogen_max
    if over <= 0.0:
        return None
    steps = math.ceil(round(over / standard.nitrogen_step, 6))
    charge = (standard.nitrogen_per_step * steps).quantize(PENCE, ROUND_HALF_UP)
    plural = "" if steps == 1 else "s"
    return Adjustment(
        kind="nitrogen",
        note=f"nitrogen {nitrogen:.2f} over {standard.nitrogen_max:.2f}, {steps} step{plural}",
        per_tonne=charge,
    )


def grade(
    ticket: str,
    standard: Standard,
    net_tonnes: float,
    analysis: Analysis,
    harvested: dt.date,
    arrived: dt.date,
    findings: frozenset[RejectionReason] = frozenset(),
) -> Grading:
    """Screen a load and, if it comes in, work out what is settled.

    The screen runs first and its answer is final. Everything after it is
    only reached by a load that was accepted.
    """
    if net_tonnes <= 0.0:
        raise ValidationError(f"{ticket} has a net weight of {net_tonnes}")
    rejections = screen(standard, analysis, harvested, arrived, findings)
    if rejections:
        return Grading(
            ticket=ticket,
            standard=standard.name,
            outcome=IntakeOutcome.REJECTED,
            net_tonnes=net_tonnes,
            settled_tonnes=0.0,
            rejections=rejections,
        )

    adjustments: list[Adjustment] = []
    settled = net_tonnes

    screenings = analysis.value_on("screenings", None)
    over = round(screenings - standard.screenings_free, 3)
    if over > 0.0:
        taken = settled * over / 100.0
        settled -= taken
        adjustments.append(
            Adjustment(
                kind="screenings",
                note=f"screenings {screenings:.1f} over {standard.screenings_free:.1f}",
                tonnes=taken,
            )
        )

    moisture = analysis.value_on("moisture", None)
    if moisture > standard.moisture_base:
        dried = at_moisture(settled, moisture, standard.moisture_base)
        adjustments.append(
            Adjustment(
                kind="moisture",
                note=f"moisture {moisture:.1f} to {standard.moisture_base:.1f}",
                tonnes=settled - dried,
            )
        )
        settled = dried

    for line in (
        _drying(standard, moisture),
        _nitrogen(standard, analysis.value_on("nitrogen", Basis.DRY)),
    ):
        if line is not None:
            adjustments.append(line)

    outcome = IntakeOutcome.ACCEPTED_ON_DEDUCTION if adjustments else IntakeOutcome.ACCEPTED
    return Grading(
        ticket=ticket,
        standard=standard.name,
        outcome=outcome,
        net_tonnes=net_tonnes,
        settled_tonnes=settled,
        adjustments=tuple(adjustments),
    )
