"""What a lorry load of barley is, and what it was bought under.

A purchase is an agreement to buy so many tonnes of one variety off one
crop, delivered inside a window, against a named quality standard. A
delivery is one lorry against one purchase. The weights are the weighbridge
in kilogrammes, because that is what the ticket says and converting on the
way in loses a rounding that somebody will eventually query.

The standard is named here and defined in the `intake` package. That split
is deliberate: what a delivery was bought under is a fact about the
delivery, and what the standard means is a rule that changes between seasons
without any delivery changing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from culmbin.errors import ValidationError
from culmbin.units.season import Window, crop_year

KILOGRAMMES_PER_TONNE = 1000.0

MAX_VEHICLE_TONNES = 32.0
"""Nothing legal on a British road delivers more than this in one load.

It is a sanity check on a weighbridge ticket, not a rule about lorries. A
net weight over it is a decimal point in the wrong place, which is the
single most common thing wrong with a typed in ticket.
"""


@dataclass(frozen=True, slots=True)
class Purchase:
    """An agreement to buy barley.

    `standard` names a quality standard rather than holding one, because two
    purchases signed a week apart can be on different standards and a
    standard gets corrected after both were signed.
    """

    code: str
    party: str
    variety: str
    crop_year: int
    tonnes: float
    window: Window
    standard: str
    price_per_tonne: Decimal
    signed: dt.date

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a purchase needs a code")
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.code} is for {self.tonnes} tonnes")
        if self.price_per_tonne <= 0:
            raise ValidationError(f"{self.code} has a price of {self.price_per_tonne}")
        if not self.standard.strip():
            raise ValidationError(f"{self.code} names no quality standard")
        if crop_year(self.window.start) < self.crop_year:
            raise ValidationError(
                f"{self.code} opens on {self.window.start}, "
                f"which is before crop year {self.crop_year}"
            )

    @property
    def value(self) -> Decimal:
        """What the whole purchase is worth at the contract price."""
        return (self.price_per_tonne * Decimal(str(self.tonnes))).quantize(Decimal("0.01"))

    def takes_delivery_on(self, day: dt.date) -> bool:
        """Whether a delivery on a day falls in the window."""
        return self.window.contains(day)


@dataclass(frozen=True, slots=True)
class Delivery:
    """One lorry load, as the weighbridge saw it.

    Both weights are kept rather than just the net, because a query about a
    ticket is nearly always about one of them and a net weight cannot be
    taken back apart.
    """

    ticket: str
    purchase: str
    party: str
    arrived: dt.date
    gross_kg: float
    tare_kg: float
    haulier: str | None = None
    vehicle: str | None = None
    sample: str | None = None
    harvested: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.ticket.strip():
            raise ValidationError("a delivery needs a ticket number")
        if self.gross_kg <= 0.0 or self.tare_kg <= 0.0:
            raise ValidationError(f"ticket {self.ticket} has a weight of nothing on it")
        if self.tare_kg >= self.gross_kg:
            raise ValidationError(
                f"ticket {self.ticket} tares at {self.tare_kg:.0f}kg "
                f"and grosses at {self.gross_kg:.0f}kg"
            )
        if self.harvested is not None and self.harvested > self.arrived:
            raise ValidationError(
                f"ticket {self.ticket} was cut on {self.harvested} and delivered on {self.arrived}"
            )
        if self.net_tonnes > MAX_VEHICLE_TONNES:
            raise ValidationError(
                f"ticket {self.ticket} is {self.net_tonnes:.1f} tonnes, "
                f"which is over the {MAX_VEHICLE_TONNES:.0f} tonne check"
            )

    @property
    def net_kg(self) -> float:
        """What came off the lorry, in kilogrammes."""
        return self.gross_kg - self.tare_kg

    @property
    def net_tonnes(self) -> float:
        """What came off the lorry, in tonnes."""
        return self.net_kg / KILOGRAMMES_PER_TONNE

    @property
    def sampled(self) -> bool:
        """Whether a sample has been taken off this load yet."""
        return self.sample is not None

    @property
    def dated(self) -> bool:
        """Whether we know when this barley was cut.

        Without it the load cannot be graded at all, because whether it is
        new crop decides which rejections apply. The column is optional
        because the weighbridge takes the ticket before the grower's
        paperwork catches up, not because it is optional to know.
        """
        return self.harvested is not None

    def with_sample(self, reference: str) -> Delivery:
        """The same delivery with a sample reference on it."""
        if not reference.strip():
            raise ValidationError(f"ticket {self.ticket} was given a blank sample reference")
        return Delivery(
            ticket=self.ticket,
            purchase=self.purchase,
            party=self.party,
            arrived=self.arrived,
            gross_kg=self.gross_kg,
            tare_kg=self.tare_kg,
            haulier=self.haulier,
            vehicle=self.vehicle,
            sample=reference,
            harvested=self.harvested,
        )

    def cut_on(self, day: dt.date) -> Delivery:
        """The same delivery with a harvest date on it."""
        return Delivery(
            ticket=self.ticket,
            purchase=self.purchase,
            party=self.party,
            arrived=self.arrived,
            gross_kg=self.gross_kg,
            tare_kg=self.tare_kg,
            haulier=self.haulier,
            vehicle=self.vehicle,
            sample=self.sample,
            harvested=day,
        )

    def __str__(self) -> str:
        return f"{self.ticket} {self.net_tonnes:.2f}t on {self.arrived.isoformat()}"
