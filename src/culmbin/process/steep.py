"""Steep programmes, and how much water the barley actually took up.

A steep programme is legs: a wet stand with the vessel flooded, then an air
rest with it drained and the grain breathing, then another wet stand, and so
on. Two wet stands in a row is one long wet stand written down badly, so the
legs have to alternate and this module says so.

The uptake model is a fit, not physics. Barley in water approaches a
ceiling, faster when the water is warm, and it keeps taking up a little
during an air rest because the surface water is still going in. The three
constants below came off this plant's own steep-out figures over a season,
which is why they are here rather than in a textbook, and why they are
allowed to be approximately right.

What the model is *for* is planning: it says whether a programme will reach
its steep-out target from a given barley moisture, and roughly when. It does
not decide anything. The measured steep-out figure is what gets recorded and
what everything downstream uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.model.enums import LegKind, MaltStyle
from culmbin.units.clock import check_temperature

UPTAKE_CEILING = 48.0
"""The moisture barley approaches in water and does not pass.

Steeping past this does not make wetter barley, it makes drowned barley, and
the piece never comes away on the floor.
"""

WET_RATE_PER_HOUR = 0.14
"""How fast the gap to the ceiling closes in a wet stand at 14 degrees.

Most of the water goes in early. Barley out of the shed at twelve percent is
past thirty within the first wet stand and then it slows right down, which
is why the model is a closing gap and not a rate.
"""

WET_RATE_PER_DEGREE = 0.045
"""How much faster it closes per degree above 14, as a fraction of the rate.

Warm steep water is quicker and it is also how you get uneven pieces, which
is why the programmes on this plant are written cold and long.
"""

REFERENCE_C = 14.0

AIR_RATE_PER_HOUR = 0.09
"""Percentage points of moisture gained per hour of air rest.

The grain is draining and breathing, and the water already on the corn is
still going in. It is small, it is not nothing, and a programme with long
air rests that ignored it would plan for a steep-out a point low.
"""


@dataclass(frozen=True, slots=True)
class SteepLeg:
    """One wet stand or one air rest."""

    kind: LegKind
    hours: float
    celsius: float

    def __post_init__(self) -> None:
        if self.hours <= 0.0:
            raise ValidationError(f"a {self.kind} of {self.hours} hours is not a leg")
        check_temperature(self.celsius, field=f"{self.kind} temperature")

    def __str__(self) -> str:
        word = "wet" if self.kind is LegKind.WET_STAND else "air"
        return f"{word} {self.hours:g}h at {self.celsius:g}C"


@dataclass(frozen=True, slots=True)
class Programme:
    """A named steep programme.

    The target is the steep-out moisture the maltster wants, and it is part
    of the programme rather than of the piece, because it is what the
    programme was written to achieve.
    """

    name: str
    style: MaltStyle
    legs: tuple[SteepLeg, ...]
    target_moisture: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("a programme needs a name")
        if not self.legs:
            raise ValidationError(f"{self.name} has no legs")
        if self.legs[0].kind is not LegKind.WET_STAND:
            raise ValidationError(f"{self.name} starts on an air rest, with dry barley in it")
        for earlier, later in zip(self.legs, self.legs[1:], strict=False):
            if earlier.kind is later.kind:
                raise ValidationError(
                    f"{self.name} has two {earlier.kind} legs together, which is one long one"
                )
        if not 0.0 < self.target_moisture <= UPTAKE_CEILING:
            raise ValidationError(
                f"{self.name} targets {self.target_moisture}, and the ceiling is {UPTAKE_CEILING}"
            )

    @property
    def wet_hours(self) -> float:
        """Hours under water."""
        return sum(leg.hours for leg in self.legs if leg.kind is LegKind.WET_STAND)

    @property
    def air_hours(self) -> float:
        """Hours drained."""
        return sum(leg.hours for leg in self.legs if leg.kind is LegKind.AIR_REST)

    @property
    def total_hours(self) -> float:
        """How long the whole programme takes."""
        return self.wet_hours + self.air_hours

    @property
    def stands(self) -> int:
        """How many wet stands the programme has."""
        return sum(1 for leg in self.legs if leg.kind is LegKind.WET_STAND)

    def __len__(self) -> int:
        return len(self.legs)


def wet_rate(celsius: float) -> float:
    """How fast the gap to the ceiling closes, per hour, at a temperature.

    Never below zero. Steep water at four degrees is slow, and slow is not
    the same as running backwards.
    """
    rate = WET_RATE_PER_HOUR * (1.0 + WET_RATE_PER_DEGREE * (celsius - REFERENCE_C))
    return max(rate, 0.0)


def after_leg(moisture: float, leg: SteepLeg) -> float:
    """The moisture at the end of one leg, given the moisture at the start."""
    if moisture >= UPTAKE_CEILING:
        return UPTAKE_CEILING
    if leg.kind is LegKind.WET_STAND:
        gap = UPTAKE_CEILING - moisture
        closed = 1.0 - float((1.0 - wet_rate(leg.celsius)) ** leg.hours)
        return moisture + gap * closed
    return min(UPTAKE_CEILING, moisture + AIR_RATE_PER_HOUR * leg.hours)


def uptake(programme: Programme, start_moisture: float) -> tuple[float, ...]:
    """The moisture at the end of every leg, in order.

    The first entry is after the first wet stand, not the barley moisture,
    because that is what the steep sheet has a column for.
    """
    if not 0.0 <= start_moisture < UPTAKE_CEILING:
        raise ValidationError(f"barley at {start_moisture} percent is not going into a steep")
    moisture = start_moisture
    trace = []
    for leg in programme.legs:
        moisture = after_leg(moisture, leg)
        trace.append(moisture)
    return tuple(trace)


def predicted_steep_out(programme: Programme, start_moisture: float) -> float:
    """What the programme is expected to come out at."""
    return uptake(programme, start_moisture)[-1]


def reaches_target(programme: Programme, start_moisture: float, tolerance: float = 0.5) -> bool:
    """Whether a programme is expected to hit its own target from a moisture."""
    return predicted_steep_out(programme, start_moisture) >= programme.target_moisture - tolerance


def hours_to_target(programme: Programme, start_moisture: float) -> float | None:
    """When in the programme the target is first reached, or nothing.

    Answers to the nearest tenth of an hour inside the leg it happens in,
    because a steep sheet is written to six minutes and no finer.
    """
    moisture = start_moisture
    elapsed = 0.0
    for leg in programme.legs:
        step = 0.1
        remaining = leg.hours
        while remaining > 0.0:
            hours = min(step, remaining)
            moisture = after_leg(moisture, SteepLeg(leg.kind, hours, leg.celsius))
            elapsed += hours
            remaining -= hours
            if moisture >= programme.target_moisture:
                return round(elapsed, 1)
    return None


def programme_of(
    name: str, style: MaltStyle, legs: Sequence[SteepLeg], target_moisture: float
) -> Programme:
    """Build a programme from a sequence."""
    return Programme(name, style, tuple(legs), target_moisture)
