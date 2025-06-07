"""The germination floor, which does not run on the wall clock.

A piece is not ready after four days. It is ready after so much warmth, and
a box that spent a night at eleven degrees when it should have been at
sixteen is behind even though the calendar says otherwise. Everything here
is therefore counted in degree hours over the growth base, and hours only
appear as the thing you multiply by a temperature.

The consequence that catches people is the turning schedule. Turns are
written against the same clock, so a cold box gets *fewer* turns in the same
number of days, not more. That is right: turning is about the bed heating up
and matting together, and a cold bed is doing neither. Every attempt to
schedule turns on the wall clock ends with somebody turning a cold piece
four times for nothing and compacting it.

The modification curve is a fit off this plant's own friability figures. It
is used for planning the kiln, never for deciding a piece is ready. What
decides that is the maltster's hand and the laboratory.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.model.enums import MaltStyle
from culmbin.units.clock import GROWTH_BASE_C, Leg, degree_hours, elapsed_hours, hours_at

MODIFICATION_CEILING = 96.0
"""The friability a piece approaches and does not pass on this plant.

Past this the malt is over modified: the extract is there and the wort runs
badly and the brewer notices. It is a ceiling on the curve, not a target.
"""

MODIFICATION_HALF_LIFE_DH = 900.0
"""Degree hours to close half the gap to the ceiling.

Fitted, off two seasons of box friability against box thermocouples. It
moves a little with variety and it is not refitted per variety, because the
number is used for planning a kiln slot and not for a certificate.
"""

MODIFICATION_START = 8.0
"""Friability of freshly cast green malt, before anything has happened."""


@dataclass(frozen=True, slots=True)
class Schedule:
    """A named germination schedule.

    `turns_at` is degree hours, not hours. The list is what the schedule
    says, and a piece gets the turns whose point it has passed.
    """

    name: str
    style: MaltStyle
    target_degree_hours: float
    turns_at: tuple[float, ...] = ()
    base_c: float = GROWTH_BASE_C

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("a schedule needs a name")
        if self.target_degree_hours <= 0.0:
            raise ValidationError(f"{self.name} targets {self.target_degree_hours} degree hours")
        if list(self.turns_at) != sorted(self.turns_at):
            raise ValidationError(f"{self.name} has its turns out of order")
        if len(set(self.turns_at)) != len(self.turns_at):
            raise ValidationError(f"{self.name} turns twice at the same point")
        for point in self.turns_at:
            if point <= 0.0:
                raise ValidationError(f"{self.name} turns at {point} degree hours")
            if point > self.target_degree_hours:
                raise ValidationError(
                    f"{self.name} turns at {point} and casts off at {self.target_degree_hours}"
                )

    @property
    def turns(self) -> int:
        """How many turns the schedule asks for over a whole piece."""
        return len(self.turns_at)

    def days_at(self, celsius: float) -> float:
        """How long the schedule takes at a steady temperature, in days."""
        return hours_at(celsius, self.target_degree_hours, self.base_c) / 24.0


def accumulated(schedule: Schedule, legs: Sequence[Leg]) -> float:
    """The degree hours a piece has earned so far."""
    return degree_hours(legs, base_c=schedule.base_c)


def progress(schedule: Schedule, legs: Sequence[Leg]) -> float:
    """How far through the schedule a piece is, as a percentage.

    Can go over a hundred. A piece held on the floor because the kiln is
    full is over its schedule and the number says so rather than stopping.
    """
    return accumulated(schedule, legs) / schedule.target_degree_hours * 100.0


def ready(schedule: Schedule, legs: Sequence[Leg]) -> bool:
    """Whether a piece has earned its schedule's degree hours."""
    return accumulated(schedule, legs) >= schedule.target_degree_hours


def turns_due(schedule: Schedule, legs: Sequence[Leg]) -> int:
    """How many turns a piece should have had by now.

    Counted on the degree hour clock, which is why a cold box gets fewer.
    """
    earned = accumulated(schedule, legs)
    return sum(1 for point in schedule.turns_at if earned >= point)


def next_turn_at(schedule: Schedule, legs: Sequence[Leg]) -> float | None:
    """The degree hour point of the next turn, or nothing if they are all done."""
    earned = accumulated(schedule, legs)
    for point in schedule.turns_at:
        if earned < point:
            return point
    return None


def hours_to_next_turn(schedule: Schedule, legs: Sequence[Leg], celsius: float) -> float | None:
    """How long until the next turn if the box stays where it is.

    This is the number the shift sheet wants, and it is why the box
    temperature is an argument: the answer changes if somebody turns the
    attemperation down overnight.
    """
    point = next_turn_at(schedule, legs)
    if point is None:
        return None
    return hours_at(celsius, point - accumulated(schedule, legs), schedule.base_c)


def hours_to_cast(schedule: Schedule, legs: Sequence[Leg], celsius: float) -> float:
    """How long until the piece is ready, at a steady temperature.

    Nothing left to run is zero rather than a negative, because a kiln slot
    cannot be booked for minus four hours.
    """
    remaining = schedule.target_degree_hours - accumulated(schedule, legs)
    if remaining <= 0.0:
        return 0.0
    return hours_at(celsius, remaining, schedule.base_c)


def predicted_modification(schedule: Schedule, legs: Sequence[Leg]) -> float:
    """Where the friability is expected to be, for planning the kiln."""
    earned = accumulated(schedule, legs)
    gap = MODIFICATION_CEILING - MODIFICATION_START
    closed = 1.0 - float(0.5 ** (earned / MODIFICATION_HALF_LIFE_DH))
    return MODIFICATION_START + gap * closed


def stalled(schedule: Schedule, legs: Sequence[Leg], hours: float = 12.0) -> bool:
    """Whether the piece has earned nothing over its last stretch of hours.

    A bed that has been at or below the growth base for half a day is not
    growing slowly, it is stopped, and somebody should be standing in front
    of it rather than reading a report about it tomorrow.
    """
    if hours <= 0.0:
        raise ValidationError(f"a stall over {hours} hours is not a stall")
    tail: list[Leg] = []
    remaining = hours
    for leg in reversed(legs):
        if remaining <= 0.0:
            break
        take = min(leg.hours, remaining)
        tail.append(Leg(hours=take, celsius=leg.celsius))
        remaining -= take
    if elapsed_hours(tail) < hours:
        return False
    return degree_hours(tail, base_c=schedule.base_c) == 0.0
