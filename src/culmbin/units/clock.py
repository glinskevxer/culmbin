"""Time, temperature, and the clock the germination floor actually runs on.

A piece of malt is not ready after so many hours. It is ready after so much
warmth, and a box that ran two degrees cold is behind even though the wall
clock says otherwise. Everything on the floor is therefore counted in degree
hours, and hours only ever appear as the thing you multiply.

Temperatures are degrees Celsius. Durations are hours as a float, because
half hours are common and quarter hours happen.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import ValidationError

GROWTH_BASE_C = 4.0
"""Below this barley does not grow enough to count and the clock stops.

It is not a physical threshold. It is the number the malthouse has always
used, and every schedule in the building is written against it, so changing
it would silently restate every historical piece.
"""

TEMPERATURE_FLOOR_C = -5.0
TEMPERATURE_CEILING_C = 120.0
"""The two ends of what any probe in the building can legitimately read.

The floor is the chill of the steep water main in February and the ceiling
is the top of a curing kiln with room to spare.
"""

_HOURS = re.compile(r"^(?P<h>\d+)h(?P<m>[0-5]\d)?$")
_MINUTES = re.compile(r"^(?P<m>\d{1,3})m$")


@dataclass(frozen=True, slots=True)
class Leg:
    """A stretch of time held at one temperature.

    Legs are what a schedule is written in and what a chart is read as. A leg
    with no hours is legal and contributes nothing, which is how a schedule
    can carry a step that a particular piece skipped.
    """

    hours: float
    celsius: float

    def __post_init__(self) -> None:
        if self.hours < 0.0:
            raise ValidationError(f"leg of {self.hours:.2f} hours is negative")
        check_temperature(self.celsius)


def check_temperature(celsius: float, field: str = "temperature") -> float:
    """Return the temperature, or raise if no probe in the building reads it."""
    if celsius < TEMPERATURE_FLOOR_C:
        raise ValidationError(
            f"{field} {celsius:.1f}C is below the {TEMPERATURE_FLOOR_C:.0f}C floor"
        )
    if celsius > TEMPERATURE_CEILING_C:
        raise ValidationError(
            f"{field} {celsius:.1f}C is above the {TEMPERATURE_CEILING_C:.0f}C ceiling"
        )
    return celsius


def parse_duration(text: str) -> float:
    """Read the shorthand the floor writes on the board, `18h30`, as hours.

    Bare `6h` and bare `45m` both work. Anything else is refused rather than
    guessed at, because a mistyped duration on a steep programme moves a
    vessel by hours and nothing downstream would notice.
    """
    trimmed = text.strip()
    match = _HOURS.match(trimmed)
    if match is not None:
        return int(match.group("h")) + int(match.group("m") or 0) / 60.0
    match = _MINUTES.match(trimmed)
    if match is not None:
        return int(match.group("m")) / 60.0
    raise ValidationError(f"{text!r} is not a duration like 18h30")


def format_duration(hours: float) -> str:
    """Write hours back in the shorthand, rounded to the nearest minute."""
    if hours < 0.0:
        raise ValidationError(f"duration of {hours:.2f} hours is negative")
    total = round(hours * 60.0)
    return f"{total // 60}h{total % 60:02d}"


def degree_hours(legs: Sequence[Leg], base_c: float = GROWTH_BASE_C) -> float:
    """The warmth a piece got, in degree hours above the growth base.

    A leg below the base contributes nothing at all rather than a negative
    number. A cold night does not undo a warm day, it just does not count,
    which is what the floor means when it says a piece stalled.
    """
    total = 0.0
    for leg in legs:
        above = leg.celsius - base_c
        if above > 0.0:
            total += above * leg.hours
    return total


def hours_at(celsius: float, target_degree_hours: float, base_c: float = GROWTH_BASE_C) -> float:
    """How long a box held at one temperature takes to earn a degree hour target."""
    if target_degree_hours < 0.0:
        raise ValidationError(f"target of {target_degree_hours:.1f} degree hours is negative")
    above = check_temperature(celsius) - base_c
    if above <= 0.0:
        raise ValidationError(
            f"a box at {celsius:.1f}C is at or below the base and never gets there"
        )
    return target_degree_hours / above


def mean_temperature(legs: Sequence[Leg]) -> float:
    """The time weighted mean of a set of legs.

    Not the mean of the temperatures. Six hours at 16 and eighteen at 14 is
    14.5, and the difference matters on a long piece.
    """
    hours = sum(leg.hours for leg in legs)
    if hours <= 0.0:
        raise ValidationError("no time passed, so there is no mean temperature")
    return sum(leg.hours * leg.celsius for leg in legs) / hours


def elapsed_hours(legs: Sequence[Leg]) -> float:
    """The wall clock time a set of legs covers."""
    return sum(leg.hours for leg in legs)
