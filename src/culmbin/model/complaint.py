"""Customer complaints, and what came of them.

A complaint is a telephone call. It becomes a record because six months
later somebody wants to know how many complaints there were about colour,
and the answer has to be a number rather than a recollection.

Two things about the shape.

**A complaint has a state and the closed states are not one state.** Upheld
means we accepted it. Rejected means we looked into it and did not, which
the customer is entitled to be told. Withdrawn means the customer said never
mind. Counting them together turns a quality figure into a nonsense.

**A complaint names a shipment where it can, and not always.** A customer
ringing about "the malt you sent in March" has not given a shipment, and
recording a guess is worse than recording that nobody knew. The
investigation is where the shipment gets attached, if it ever does.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import ComplaintKind, ComplaintState

CLOSED_STATES = frozenset(
    {ComplaintState.UPHELD, ComplaintState.REJECTED, ComplaintState.WITHDRAWN}
)
ABOUT_THE_MALT = frozenset(
    {
        ComplaintKind.COLOUR,
        ComplaintKind.EXTRACT,
        ComplaintKind.MODIFICATION,
        ComplaintKind.CONTAMINATION,
    }
)


@dataclass(frozen=True, slots=True)
class Complaint:
    """One telephone call, and where it got to."""

    code: str
    customer: str
    kind: ComplaintKind
    raised: dt.date
    summary: str
    state: ComplaintState = ComplaintState.OPEN
    shipment: str | None = None
    closed: dt.date | None = None
    finding: str = ""

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a complaint needs a code")
        if not self.summary.strip():
            raise ValidationError(f"{self.code} says nothing about what is wrong")
        if (self.state in CLOSED_STATES) != (self.closed is not None):
            raise ValidationError(
                f"{self.code} is {self.state} and its closing date does not agree"
            )
        if self.closed is not None and self.closed < self.raised:
            raise ValidationError(f"{self.code} was closed before it was raised")

    @property
    def open(self) -> bool:
        """Whether anybody still has to do something about it."""
        return self.state not in CLOSED_STATES

    @property
    def about_the_malt(self) -> bool:
        """Whether this is about the malt rather than about how we behaved."""
        return self.kind in ABOUT_THE_MALT

    @property
    def traceable(self) -> bool:
        """Whether a shipment has been attached, so it can be walked back."""
        return self.shipment is not None

    def days_open(self, on: dt.date) -> int:
        """How long it has been open, or how long it was."""
        end = self.closed if self.closed is not None else on
        return max(0, (end - self.raised).days)

    def attached_to(self, shipment: str) -> Complaint:
        """The same complaint with a shipment on it.

        Refuses to move one. A complaint attached to the wrong load and then
        quietly re-attached leaves a walk that was done against the wrong
        malt and no record that it was.
        """
        if self.shipment is not None:
            raise StateError(f"{self.code} is already against {self.shipment}")
        return Complaint(
            code=self.code,
            customer=self.customer,
            kind=self.kind,
            raised=self.raised,
            summary=self.summary,
            state=self.state,
            shipment=shipment,
            closed=self.closed,
            finding=self.finding,
        )

    def closed_as(self, state: ComplaintState, on: dt.date, finding: str) -> Complaint:
        """The same complaint closed, with what was found written down."""
        if state not in CLOSED_STATES:
            raise StateError(f"{state} is not a way of closing a complaint")
        if not self.open:
            raise StateError(f"{self.code} was closed as {self.state} on {self.closed}")
        if not finding.strip():
            raise StateError(f"{self.code} is being closed and nothing says what was found")
        return Complaint(
            code=self.code,
            customer=self.customer,
            kind=self.kind,
            raised=self.raised,
            summary=self.summary,
            state=state,
            shipment=self.shipment,
            closed=on,
            finding=finding,
        )

    def __str__(self) -> str:
        against = f" against {self.shipment}" if self.shipment else ""
        return f"{self.code} {self.customer} {self.kind}{against} ({self.state})"
