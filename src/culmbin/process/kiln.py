"""Kiln curves, and why two pieces cured at the same temperature come off
different colours.

A kiln curve is steps. Free drying pulls the bulk of the water out on high
air and modest temperature, the break is where the bed stops giving water up
freely and the air-on can be lifted, and curing is the hot hours at the end
that make the flavour and the colour.

The thing worth understanding here is that **colour is made out of heat and
water together**. Sugars and amino acids brown when they are hot and wet.
Malt that has already been dried to four percent can sit at eighty five
degrees for hours and hardly move, and the same malt taken to eighty five
with ten percent still in it goes several EBC darker. So the colour a curve
produces depends on how *fast* it dried before it got hot, which is not
something the curing temperature knows.

That is why a kiln that is running with a fan down produces pale malt on a
curve that has not changed, and why the fix is on the drying end rather than
on the curing end where everybody looks first.

The two models here are fits off this plant's kilns. They are for planning:
what to expect, and whether a curve is going to land inside a specification.
The certificate quotes the laboratory.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.model.enums import KilnPhase, MaltStyle
from culmbin.units.clock import check_temperature

PHASE_ORDER: tuple[KilnPhase, ...] = (KilnPhase.FREE_DRYING, KilnPhase.BREAK, KilnPhase.CURING)

AMBIENT_C = 20.0
"""The air the fans are drawing off the yard before the burner touches it."""

DRYING_RATE = 0.055
"""How fast the gap to equilibrium closes, per hour, per ten degrees of lift."""

EQUILIBRIUM_AT_50 = 6.2
"""The moisture malt sits at in fifty degree air and will not go below."""

EQUILIBRIUM_FALL_PER_DEGREE = 0.075
"""How much lower that equilibrium goes for each degree above fifty."""

EQUILIBRIUM_FLOOR = 1.6
"""No amount of heat takes malt below this, and nothing here pretends it does."""

COLOUR_BASE_C = 55.0
"""Below this nothing browns at any moisture worth having on a kiln."""

COLOUR_RATE = 0.00048
"""EBC per hour, per degree over the base, per point of moisture present.

Three things multiplied, which is the whole point: heat alone does nothing,
water alone does nothing, and time turns the pair of them into colour.
"""

BASE_COLOUR_EBC = 2.2
"""The colour green malt would come off at with no browning at all."""


@dataclass(frozen=True, slots=True)
class KilnStep:
    """One stretch of a kiln curve at one air-on temperature."""

    phase: KilnPhase
    hours: float
    air_celsius: float

    def __post_init__(self) -> None:
        if self.hours <= 0.0:
            raise ValidationError(f"a {self.phase} step of {self.hours} hours is not a step")
        check_temperature(self.air_celsius, field=f"{self.phase} air")
        if self.air_celsius <= AMBIENT_C:
            raise ValidationError(
                f"a {self.phase} step at {self.air_celsius}C is not a kiln, it is a fan"
            )

    def __str__(self) -> str:
        return f"{self.phase} {self.hours:g}h at {self.air_celsius:g}C"


@dataclass(frozen=True, slots=True)
class Curve:
    """A named kiln curve.

    The steps go free drying, then break, then curing, and the air-on never
    goes down. A curve that turned a kiln down partway is either a mistake
    or an incident, and an incident is recorded against the piece rather
    than written into the curve everything else runs on.
    """

    name: str
    style: MaltStyle
    steps: tuple[KilnStep, ...]
    target_moisture: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("a curve needs a name")
        if not self.steps:
            raise ValidationError(f"{self.name} has no steps")
        if self.steps[0].phase is not KilnPhase.FREE_DRYING:
            raise ValidationError(f"{self.name} starts on {self.steps[0].phase}, not free drying")
        if not any(step.phase is KilnPhase.CURING for step in self.steps):
            raise ValidationError(f"{self.name} never cures, so it makes wet green malt")
        seen = -1
        for step in self.steps:
            index = PHASE_ORDER.index(step.phase)
            if index < seen:
                raise ValidationError(f"{self.name} goes back to {step.phase} after a later phase")
            seen = index
        for earlier, later in zip(self.steps, self.steps[1:], strict=False):
            if later.air_celsius < earlier.air_celsius:
                raise ValidationError(
                    f"{self.name} turns the kiln down from {earlier.air_celsius:g} "
                    f"to {later.air_celsius:g}"
                )
        if not 0.0 < self.target_moisture < 12.0:
            raise ValidationError(f"{self.name} targets {self.target_moisture} percent off kiln")

    @property
    def hours(self) -> float:
        """How long the whole curve takes."""
        return sum(step.hours for step in self.steps)

    def hours_in(self, phase: KilnPhase) -> float:
        """How long is spent in one phase."""
        return sum(step.hours for step in self.steps if step.phase is phase)

    @property
    def peak_c(self) -> float:
        """The hottest air the curve calls for."""
        return max(step.air_celsius for step in self.steps)

    def __len__(self) -> int:
        return len(self.steps)


def equilibrium_moisture(air_celsius: float) -> float:
    """The moisture malt settles at in air of a given temperature."""
    fall = (air_celsius - 50.0) * EQUILIBRIUM_FALL_PER_DEGREE
    return max(EQUILIBRIUM_FLOOR, EQUILIBRIUM_AT_50 - fall)


def after_step(moisture: float, step: KilnStep) -> float:
    """The moisture at the end of one step, given the moisture at the start."""
    settled = equilibrium_moisture(step.air_celsius)
    if moisture <= settled:
        return moisture
    rate = DRYING_RATE * (step.air_celsius - AMBIENT_C) / 10.0
    closed = 1.0 - float((1.0 - min(rate, 0.95)) ** step.hours)
    return moisture - (moisture - settled) * closed


def colour_from_step(moisture_in: float, moisture_out: float, step: KilnStep) -> float:
    """The EBC a step adds, out of its heat, its water and its hours.

    The moisture used is the mean across the step, because the bed is drying
    while it browns and taking either end alone is out by a useful amount on
    a long curing step.
    """
    over = step.air_celsius - COLOUR_BASE_C
    if over <= 0.0:
        return 0.0
    mean_moisture = (moisture_in + moisture_out) / 2.0
    return COLOUR_RATE * step.hours * over * mean_moisture


def dry_down(curve: Curve, green_moisture: float) -> tuple[float, ...]:
    """The moisture at the end of every step, in order."""
    if not 0.0 < green_moisture < 60.0:
        raise ValidationError(f"green malt at {green_moisture} percent is not going on a kiln")
    moisture = green_moisture
    trace = []
    for step in curve.steps:
        moisture = after_step(moisture, step)
        trace.append(moisture)
    return tuple(trace)


def off_kiln_moisture(curve: Curve, green_moisture: float) -> float:
    """What the curve is expected to leave in the malt."""
    return dry_down(curve, green_moisture)[-1]


def predicted_colour(curve: Curve, green_moisture: float) -> float:
    """The colour the curve is expected to produce, in EBC."""
    moisture = green_moisture
    colour = BASE_COLOUR_EBC
    for step in curve.steps:
        after = after_step(moisture, step)
        colour += colour_from_step(moisture, after, step)
        moisture = after
    return colour


def break_moisture(curve: Curve, green_moisture: float) -> float:
    """The moisture at the end of free drying, which is what sets the colour.

    A curve with no break step reports the moisture when the air first goes
    above the free drying steps, which comes to the same thing.
    """
    moisture = green_moisture
    for step in curve.steps:
        if step.phase is not KilnPhase.FREE_DRYING:
            return moisture
        moisture = after_step(moisture, step)
    return moisture


def meets_target(curve: Curve, green_moisture: float, tolerance: float = 0.3) -> bool:
    """Whether the curve is expected to dry to its own target."""
    return off_kiln_moisture(curve, green_moisture) <= curve.target_moisture + tolerance


def curve_of(
    name: str, style: MaltStyle, steps: Sequence[KilnStep], target_moisture: float
) -> Curve:
    """Build a curve from a sequence."""
    return Curve(name, style, tuple(steps), target_moisture)
