"""Turning a grading into money.

The arithmetic is one line. Everything else in this module is about the two
places it can go wrong.

The first is that a rejected load has nothing to settle. Not a settlement of
zero: nothing. A zero would go on the grower's statement as a line, and a
line saying we took twenty eight tonnes off him for nothing is worse than no
line at all.

The second is that deductions cannot take a price below zero. A load can in
principle be deducted past what it is worth, and when the schedule says that
the answer is that we pay nothing, not that the grower owes us money for
having delivered barley. The note says the deduction was capped, because
somebody will ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from culmbin.errors import StateError, ValidationError
from culmbin.intake.grading import Grading
from culmbin.model.intake import Purchase

PENCE = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Settlement:
    """What one load is worth, ready to go on a statement."""

    ticket: str
    purchase: str
    settled_tonnes: float
    base_per_tonne: Decimal
    deduction_per_tonne: Decimal
    capped: bool

    def __post_init__(self) -> None:
        if self.settled_tonnes <= 0.0:
            raise ValidationError(f"{self.ticket} settles {self.settled_tonnes} tonnes")
        if self.base_per_tonne <= 0:
            raise ValidationError(f"{self.ticket} has a base price of {self.base_per_tonne}")
        if self.deduction_per_tonne < 0:
            raise ValidationError(f"{self.ticket} has a negative deduction")
        if self.deduction_per_tonne > self.base_per_tonne:
            raise ValidationError(f"{self.ticket} deducts more than the base price")

    @property
    def net_per_tonne(self) -> Decimal:
        """What a settled tonne is actually paid at."""
        return self.base_per_tonne - self.deduction_per_tonne

    @property
    def value(self) -> Decimal:
        """What the load is worth, to the penny."""
        return (self.net_per_tonne * Decimal(str(self.settled_tonnes))).quantize(
            PENCE, ROUND_HALF_UP
        )

    def __str__(self) -> str:
        return f"{self.ticket} {self.settled_tonnes:.3f}t at {self.net_per_tonne} = {self.value}"


def settle(grading: Grading, purchase: Purchase) -> Settlement:
    """What a graded load is worth against the purchase it came in on.

    Refuses a rejected load, because a settlement of nothing is a line on a
    statement and a rejection is the absence of one.
    """
    if grading.rejected:
        raise StateError(
            f"{grading.ticket} was rejected for "
            f"{', '.join(reason for reason in grading.rejections)}, so there is nothing to settle"
        )
    if grading.standard != purchase.standard:
        raise ValidationError(
            f"{grading.ticket} was graded against {grading.standard} "
            f"and {purchase.code} is on {purchase.standard}"
        )
    deduction = grading.price_adjustment
    capped = deduction > purchase.price_per_tonne
    if capped:
        deduction = purchase.price_per_tonne
    return Settlement(
        ticket=grading.ticket,
        purchase=purchase.code,
        settled_tonnes=grading.settled_tonnes,
        base_per_tonne=purchase.price_per_tonne,
        deduction_per_tonne=deduction,
        capped=capped,
    )


def settle_or_none(grading: Grading, purchase: Purchase) -> Settlement | None:
    """The settlement, or nothing for a rejected load.

    For the statement, which walks every load of the month and has to skip
    the rejections rather than stop at the first one.
    """
    if grading.rejected:
        return None
    return settle(grading, purchase)


def statement_total(settlements: tuple[Settlement, ...]) -> Decimal:
    """What a run of loads is worth, added up to the penny.

    Each load is rounded to the penny first and then added, which is what
    the grower's statement does. Adding first and rounding once gives a
    total that is right and does not match the lines above it.
    """
    return sum((settlement.value for settlement in settlements), Decimal("0.00"))
