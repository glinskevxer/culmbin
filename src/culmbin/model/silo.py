"""Barley silos: the shed between the weighbridge and the steep.

A silo is a mixed mass. Twelve lorries go in over three weeks and what comes
out of the bottom is some of all of them in a proportion nobody measured.
That is not a failure of record keeping, it is what a silo is, and pretending
otherwise is how a traceability walk ends up claiming a precision it does
not have.

So the model here is proportional. A draw of forty tonnes out of a four
hundred tonne silo carries a tenth of every load in it. That is the honest
answer and it is the one the walk in `culmbin.trace.walk` was already
written against.

Segregation is the same rule as the malt bins and for the same reason. A
silo that has taken two varieties is a mixed silo, and it stays one until
somebody has been in with a shovel, because there is always a tonne under
the sweep auger.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import SegregationError, StateError, ValidationError
from culmbin.units.mass import blend_moisture


@dataclass(frozen=True, slots=True)
class Silo:
    """One barley silo, as it stands."""

    code: str
    capacity_tonnes: float
    mixed: bool = False
    commissioned: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a silo needs a code")
        if self.capacity_tonnes <= 0.0:
            raise ValidationError(f"{self.code} holds {self.capacity_tonnes} tonnes")

    def marked_mixed(self) -> Silo:
        """The same silo, marked as having held more than one variety."""
        return Silo(self.code, self.capacity_tonnes, True, self.commissioned)

    def swept(self) -> Silo:
        """The same silo with the mixed mark taken off.

        Only worth doing when the silo is empty, which the store checks: a
        mark cleared with barley still in it is a mark that was wrong.
        """
        return Silo(self.code, self.capacity_tonnes, False, self.commissioned)

    def __str__(self) -> str:
        mark = " mixed" if self.mixed else ""
        return f"{self.code} {self.capacity_tonnes:.0f}t{mark}"


@dataclass(frozen=True, slots=True)
class Share:
    """One lorry load's share of what is in a silo."""

    ticket: str
    tonnes: float

    def __post_init__(self) -> None:
        if self.tonnes < 0.0:
            raise ValidationError(f"{self.ticket} has a share of {self.tonnes} tonnes")


@dataclass(frozen=True, slots=True)
class Holding:
    """What is in a silo, and which loads it came off."""

    code: str
    tonnes: float
    moisture: float
    varieties: frozenset[str] = frozenset()
    crop_years: frozenset[int] = frozenset()
    shares: tuple[Share, ...] = ()

    def __post_init__(self) -> None:
        if self.tonnes < 0.0:
            raise ValidationError(f"{self.code} holds {self.tonnes} tonnes")

    @property
    def empty(self) -> bool:
        """Whether there is anything worth drawing."""
        return self.tonnes <= 1e-9

    @property
    def variety(self) -> str | None:
        """The one variety in the silo, or nothing if it holds more than one."""
        return next(iter(self.varieties)) if len(self.varieties) == 1 else None

    @property
    def crop_year(self) -> int | None:
        """The one crop year in the silo, or nothing."""
        return next(iter(self.crop_years)) if len(self.crop_years) == 1 else None

    def check_charges(self, variety: str) -> None:
        """Raise unless a piece of a variety can be charged out of this silo."""
        if self.empty:
            raise StateError(f"{self.code} has nothing in it to charge")
        if self.variety is None:
            raise SegregationError(
                f"{self.code} holds {', '.join(sorted(self.varieties))} and a piece "
                f"charged out of it cannot declare a variety"
            )
        if self.variety != variety:
            raise SegregationError(f"{self.code} holds {self.variety} and the piece says {variety}")

    def apportion(self, tonnes: float) -> tuple[Share, ...]:
        """Split a draw across the loads in the silo, in proportion.

        A draw of forty tonnes out of four hundred carries a tenth of every
        load. The last share takes whatever rounding is left over, so the
        shares always add up to exactly what was drawn.
        """
        if tonnes <= 0.0:
            raise ValidationError(f"a draw of {tonnes} tonnes is not a draw")
        if tonnes > self.tonnes + 1e-9:
            raise StateError(f"{self.code} holds {self.tonnes:.2f}t and {tonnes:.2f}t was drawn")
        if not self.shares:
            raise StateError(f"{self.code} has nothing recorded as going into it")
        out = []
        taken = 0.0
        for share in self.shares[:-1]:
            part = round(tonnes * share.tonnes / self.tonnes, 6)
            taken += part
            out.append(Share(share.ticket, part))
        out.append(Share(self.shares[-1].ticket, round(tonnes - taken, 6)))
        return tuple(part for part in out if part.tonnes > 0.0)

    def after(self, tonnes: float) -> tuple[Share, ...]:
        """What is left in the silo once a draw has been taken out."""
        drawn = {share.ticket: share.tonnes for share in self.apportion(tonnes)}
        return tuple(
            Share(share.ticket, round(share.tonnes - drawn.get(share.ticket, 0.0), 6))
            for share in self.shares
            if share.tonnes - drawn.get(share.ticket, 0.0) > 1e-9
        )

    def __str__(self) -> str:
        variety = self.variety or "mixed"
        return f"{self.code} {self.tonnes:.2f}t {variety} at {self.moisture:.2f}%"


def holding_of(
    code: str,
    parts: Sequence[tuple[str, float, float]],
    varieties: Sequence[str],
    crop_years: Sequence[int],
) -> Holding:
    """Build a holding from the loads that went in, each with its moisture."""
    if not parts:
        return Holding(code=code, tonnes=0.0, moisture=0.0)
    tonnes = sum(weight for _, weight, _ in parts)
    return Holding(
        code=code,
        tonnes=tonnes,
        moisture=blend_moisture([(weight, moisture) for _, weight, moisture in parts]),
        varieties=frozenset(varieties),
        crop_years=frozenset(crop_years),
        shares=tuple(Share(ticket, weight) for ticket, weight, _ in parts),
    )
