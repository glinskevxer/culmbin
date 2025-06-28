"""Contracts, call-offs and shipments.

A contract is a customer agreeing to take so many tonnes of malt to a named
specification over a year. A call is the customer ringing up in March and
asking for two hundred of them in the second week of April. A shipment is a
tanker leaving the yard.

The number that has to be got right is the **contract tonne**, and it is not
the weighbridge tonne. A contract is written at a moisture, usually four and
a half percent, and the malt that goes out is whatever moisture it came off
the kiln at. A tanker of twenty eight tonnes at 4.2 percent carries more dry
malt than twenty eight tonnes at 4.5, so it draws the contract down by more
than twenty eight, and the customer is quite right to expect that. Both
numbers are correct and they are different, which is the whole difficulty.

So a shipment carries its own weight and its own moisture, and the contract
draw-down is worked, never stored. Storing it would be one more number that
can disagree with the two it came from.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import ContractState, ShipmentState
from culmbin.units.mass import at_moisture, dry_matter
from culmbin.units.season import Window

PENCE = Decimal("0.01")

DEFAULT_CONTRACT_MOISTURE = 4.5
"""What nearly every malt contract in the trade is written at."""


@dataclass(frozen=True, slots=True)
class Contract:
    """A customer agreeing to take malt over a year."""

    code: str
    customer: str
    specification: str
    tonnes: float
    moisture: float
    price_per_tonne: Decimal
    window: Window
    signed: dt.date
    state: ContractState = ContractState.DRAFT
    variety: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a contract needs a code")
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.code} is for {self.tonnes} tonnes")
        if self.price_per_tonne <= 0:
            raise ValidationError(f"{self.code} has a price of {self.price_per_tonne}")
        if not 0.0 < self.moisture < 12.0:
            raise ValidationError(f"{self.code} is written at {self.moisture} percent moisture")
        if not self.specification.strip():
            raise ValidationError(f"{self.code} names no specification")
        if self.window.start < self.signed:
            raise ValidationError(f"{self.code} opens on {self.window.start} and was signed later")

    @property
    def value(self) -> Decimal:
        """What the whole contract is worth at the contract price."""
        return (self.price_per_tonne * Decimal(str(self.tonnes))).quantize(PENCE, ROUND_HALF_UP)

    @property
    def dry_tonnes(self) -> float:
        """The dry malt the contract is actually for."""
        return dry_matter(self.tonnes, self.moisture)

    @property
    def open(self) -> bool:
        """Whether malt can be shipped against this contract."""
        return self.state is ContractState.SIGNED

    @property
    def names_a_variety(self) -> bool:
        """Whether this contract can only be served by a lot that declares one."""
        return self.variety is not None

    def takes_shipment_on(self, day: dt.date) -> bool:
        """Whether a shipment on a day falls in the contract's window."""
        return self.window.contains(day)

    def check_open(self) -> None:
        """Raise unless malt can be shipped against this contract today."""
        if self.state is not ContractState.SIGNED:
            raise StateError(f"{self.code} is {self.state} and nothing ships against it")

    def __str__(self) -> str:
        variety = f" {self.variety}" if self.variety else ""
        return f"{self.code} {self.customer} {self.tonnes:.0f}t{variety}"


@dataclass(frozen=True, slots=True)
class Call:
    """A customer asking for part of a contract in a particular week."""

    code: str
    contract: str
    tonnes: float
    wanted: Window
    placed: dt.date

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a call needs a code")
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.code} calls for {self.tonnes} tonnes")
        if self.wanted.end < self.placed:
            raise ValidationError(f"{self.code} was placed after the week it wants")

    def __str__(self) -> str:
        return f"{self.code} {self.tonnes:.0f}t {self.wanted}"


@dataclass(frozen=True, slots=True)
class Shipment:
    """One load of malt leaving the yard."""

    code: str
    contract: str
    lot: str
    tonnes: float
    moisture: float
    despatched: dt.date
    state: ShipmentState = ShipmentState.PLANNED
    call: str | None = None
    haulier: str | None = None
    vehicle: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a shipment needs a code")
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.code} is {self.tonnes} tonnes")
        dry_matter(self.tonnes, self.moisture)

    @property
    def dry_tonnes(self) -> float:
        """The dry malt on the lorry."""
        return dry_matter(self.tonnes, self.moisture)

    @property
    def gone(self) -> bool:
        """Whether this shipment has actually left."""
        return self.state is ShipmentState.DESPATCHED

    @property
    def counts(self) -> bool:
        """Whether this shipment draws a contract down.

        A cancelled shipment does not, and a planned one does not either: it
        is a slot in the loading diary and the malt is still in the bin.
        """
        return self.state in (ShipmentState.LOADED, ShipmentState.DESPATCHED)

    def contract_tonnes(self, contract_moisture: float) -> float:
        """What this shipment draws off a contract written at a moisture.

        Drier malt draws down by more than it weighs, because there is more
        malt in it. This is the number the customer's contract position is
        kept in and it is not the number on the weighbridge ticket.
        """
        return at_moisture(self.tonnes, self.moisture, contract_moisture)

    def value(self, price_per_tonne: Decimal, contract_moisture: float) -> Decimal:
        """What the load is worth, priced on the contract tonne.

        Priced on the contract tonne and not the weighbridge tonne, because
        that is what the contract says and because otherwise a wet load
        would be worth more than a dry one.
        """
        tonnes = Decimal(str(self.contract_tonnes(contract_moisture)))
        return (price_per_tonne * tonnes).quantize(PENCE, ROUND_HALF_UP)

    def __str__(self) -> str:
        return f"{self.code} {self.tonnes:.2f}t at {self.moisture:.1f} on {self.despatched}"
