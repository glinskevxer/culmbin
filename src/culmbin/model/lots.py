"""Malt bins and the lots drawn out of them.

A bin is a hole in the ground with malt in it. Pieces are tipped in, lorries
are drawn out, and in between somebody has to be able to say what is in
there and what it can be sold as.

The rule that runs through this whole module is **segregation propagates and
never recovers**. A bin that has held one variety holds that variety. A bin
that has taken two is a mixed bin, and it is a mixed bin afterwards even if
it is drawn right down and refilled from one piece, because "right down" is
never quite right down: there is always a tonne in the boot of the bin and
under the sweep auger, and it is that tonne that turns up in the customer's
brewhouse.

So a bin is marked mixed when it takes a second variety and stays marked
until somebody physically cleans it out and says so. A lot drawn from a
mixed bin has no variety at all, and a contract that names a variety cannot
be served from it whatever the analysis says. That is not the analysis being
overruled. The analysis was never able to answer the question.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from culmbin.errors import SegregationError, StateError, ValidationError
from culmbin.model.enums import BinState, MaltStyle
from culmbin.units.mass import blend_moisture, dry_matter


@dataclass(frozen=True, slots=True)
class Bin:
    """One malt bin, as it stands."""

    code: str
    capacity_tonnes: float
    state: BinState = BinState.EMPTY
    mixed: bool = False
    commissioned: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a bin needs a code")
        if self.capacity_tonnes <= 0.0:
            raise ValidationError(f"{self.code} holds {self.capacity_tonnes} tonnes")

    @property
    def takes_malt(self) -> bool:
        """Whether malt can be tipped in.

        A sealed bin cannot take malt. That is the whole reason the state
        exists: it is what makes a lot's analysis mean anything, because the
        thing that was sampled is the thing that is still in there.
        """
        return self.state in (BinState.EMPTY, BinState.FILLING)

    @property
    def gives_malt(self) -> bool:
        """Whether malt can be drawn out."""
        return self.state in (BinState.SEALED, BinState.DRAWING)

    def marked_mixed(self) -> Bin:
        """The same bin, marked as having held more than one variety."""
        return Bin(self.code, self.capacity_tonnes, self.state, True, self.commissioned)

    def in_state(self, state: BinState) -> Bin:
        """The same bin in another state, carrying its mixed mark with it.

        A bin coming back to empty keeps the mark. Empty is what the level
        gauge says, and the mark is about the boot of the bin and the sweep
        auger, which the level gauge has never been able to see.
        """
        return Bin(self.code, self.capacity_tonnes, state, self.mixed, self.commissioned)

    def cleaned_out(self) -> Bin:
        """The same bin, emptied and swept, with its mixed mark taken off.

        This is the only thing that clears the mark, and it is a job with a
        man and a shovel in it rather than a state change.
        """
        if self.state is not BinState.EMPTY:
            raise StateError(f"{self.code} is {self.state} and cannot be cleaned out")
        return Bin(self.code, self.capacity_tonnes, BinState.EMPTY, False, self.commissioned)

    def __str__(self) -> str:
        mark = " mixed" if self.mixed else ""
        return f"{self.code} {self.state}{mark}"


@dataclass(frozen=True, slots=True)
class Contents:
    """What is in a bin, worked from what went in and what came out."""

    code: str
    tonnes: float
    moisture: float
    varieties: frozenset[str] = frozenset()
    crop_years: frozenset[int] = frozenset()
    styles: frozenset[MaltStyle] = frozenset()

    def __post_init__(self) -> None:
        if self.tonnes < 0.0:
            raise ValidationError(f"{self.code} holds {self.tonnes} tonnes")

    @property
    def dry_tonnes(self) -> float:
        """The dry matter in the bin, which is what a blend weighs on."""
        return dry_matter(self.tonnes, self.moisture)

    @property
    def empty(self) -> bool:
        """Whether there is anything worth drawing."""
        return self.tonnes <= 1e-9

    @property
    def variety(self) -> str | None:
        """The one variety in the bin, or nothing if it holds more than one."""
        return next(iter(self.varieties)) if len(self.varieties) == 1 else None

    @property
    def crop_year(self) -> int | None:
        """The one crop year in the bin, or nothing."""
        return next(iter(self.crop_years)) if len(self.crop_years) == 1 else None

    @property
    def style(self) -> MaltStyle | None:
        """The one style in the bin, or nothing."""
        return next(iter(self.styles)) if len(self.styles) == 1 else None


@dataclass(frozen=True, slots=True)
class MaltLot:
    """A sealed parcel of malt, ready to be sold.

    A lot is what a certificate of analysis is written against. It is sealed
    at a moment, and the tonnage and the moisture are what was in the bin at
    that moment, because that is what the sample was taken off.
    """

    code: str
    bin_code: str
    sealed: dt.date
    tonnes: float
    moisture: float
    analysis: str | None = None
    varieties: frozenset[str] = frozenset()
    crop_years: frozenset[int] = frozenset()
    style: MaltStyle | None = None
    parents: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a lot needs a code")
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.code} is {self.tonnes} tonnes")
        dry_matter(self.tonnes, self.moisture)
        if not self.varieties:
            raise ValidationError(f"{self.code} came from nothing")

    @property
    def dry_tonnes(self) -> float:
        """The dry matter in the lot."""
        return dry_matter(self.tonnes, self.moisture)

    @property
    def variety(self) -> str | None:
        """The variety this lot can be sold as, or nothing.

        Nothing means the lot came out of a mixed bin. It does not mean
        nobody has looked it up.
        """
        return next(iter(self.varieties)) if len(self.varieties) == 1 else None

    @property
    def declares_variety(self) -> bool:
        """Whether this lot can be sold against a contract naming a variety."""
        return self.variety is not None

    @property
    def certified(self) -> bool:
        """Whether an analysis has been written against this lot."""
        return self.analysis is not None

    def serves(self, variety: str) -> bool:
        """Whether this lot can serve a contract that names a variety."""
        return self.variety == variety

    def check_serves(self, variety: str) -> None:
        """Raise unless this lot can serve a contract naming a variety."""
        if self.variety is None:
            raise SegregationError(
                f"{self.code} came out of a mixed bin and has no variety to declare"
            )
        if self.variety != variety:
            raise SegregationError(
                f"{self.code} is {self.variety} and the contract wants {variety}"
            )

    def __str__(self) -> str:
        variety = self.variety or "mixed"
        return f"{self.code} {self.tonnes:.1f}t {variety}"


def blended_contents(code: str, parts: tuple[Contents, ...]) -> Contents:
    """What several bins would make if they were run together.

    The moisture averages over the wet weight, because water is a fraction
    of the wet weight. Everything else about the parts is unioned, which is
    how a blend of two varieties becomes a parcel with no variety.
    """
    if not parts:
        raise ValidationError("a blend needs at least one part")
    tonnes = sum(part.tonnes for part in parts)
    if tonnes <= 0.0:
        raise ValidationError("a blend of empty bins is not a blend")
    return Contents(
        code=code,
        tonnes=tonnes,
        moisture=blend_moisture([(part.tonnes, part.moisture) for part in parts]),
        varieties=frozenset().union(*(part.varieties for part in parts)),
        crop_years=frozenset().union(*(part.crop_years for part in parts)),
        styles=frozenset().union(*(part.styles for part in parts)),
    )
