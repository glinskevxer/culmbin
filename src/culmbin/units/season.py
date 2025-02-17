"""The two years a malthouse works in, and the windows hung off them.

Nothing here is the calendar year. Barley is a crop year, which opens before
harvest so that it contains its own harvest, and malt is sold in a contract
year, which opens a quarter later so that a contract is always served out of
a crop that is already in the shed. The two disagree from July to September,
and confusing them there puts a delivery in the wrong year, which is the sort
of mistake that gets found in the following October.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import ValidationError

CROP_YEAR_START_MONTH = 7
"""Crop year 2025 opens on 1 July 2025, which is before the combines.

It has to open before harvest or the year would not contain its own crop.
Barley cut in the second week of August is crop year 2025 barley, and there
is a test that says so because getting this backwards is silent.
"""

CONTRACT_YEAR_START_MONTH = 10
"""Contract year 2025 opens on 1 October 2025, a quarter into crop year 2025."""

DORMANCY_WEEKS = 6
"""New crop barley will not germinate evenly until dormancy has broken.

Six weeks is what this malthouse has always allowed. It is a floor and not a
guarantee: a germination energy test still has to pass before the barley is
steeped, and this only stops anybody scheduling it before there is any point
running the test.
"""


def crop_year(day: dt.date) -> int:
    """The crop year a day falls in."""
    return day.year if day.month >= CROP_YEAR_START_MONTH else day.year - 1


def contract_year(day: dt.date) -> int:
    """The contract year a day falls in."""
    return day.year if day.month >= CONTRACT_YEAR_START_MONTH else day.year - 1


def crop_year_opens(year: int) -> dt.date:
    """The first day of a crop year."""
    return dt.date(year, CROP_YEAR_START_MONTH, 1)


def contract_year_opens(year: int) -> dt.date:
    """The first day of a contract year."""
    return dt.date(year, CONTRACT_YEAR_START_MONTH, 1)


def dormancy_clears(harvested: dt.date) -> dt.date:
    """The first day barley cut on a given day may be scheduled to steep."""
    return harvested + dt.timedelta(weeks=DORMANCY_WEEKS)


def is_new_crop(day: dt.date, harvested: dt.date) -> bool:
    """Whether barley cut on one day is still new crop on another.

    New crop means the same crop year and inside dormancy. Barley cut in
    August is new crop in September and old crop the following June without
    anything having happened to it.
    """
    return crop_year(harvested) == crop_year(day) and day < dormancy_clears(harvested)


@dataclass(frozen=True, slots=True, order=True)
class Window:
    """A closed span of days, both ends included.

    Delivery windows, contract call periods and inspection periods are all
    this. Both ends are inclusive because that is how a contract is written:
    a March delivery window is the first to the thirty first.
    """

    start: dt.date
    end: dt.date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError(f"window ends {self.end} before it starts {self.start}")

    @property
    def days(self) -> int:
        """How many days the window covers, counting both ends."""
        return (self.end - self.start).days + 1

    def contains(self, day: dt.date) -> bool:
        """Whether a day falls in the window."""
        return self.start <= day <= self.end

    def overlaps(self, other: Window) -> bool:
        """Whether two windows share at least one day."""
        return self.start <= other.end and other.start <= self.end

    def clipped_to(self, other: Window) -> Window | None:
        """The part of this window inside another, or nothing if they miss."""
        if not self.overlaps(other):
            return None
        return Window(max(self.start, other.start), min(self.end, other.end))

    def __str__(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


def month_window(year: int, month: int) -> Window:
    """The window covering a calendar month."""
    if not 1 <= month <= 12:
        raise ValidationError(f"month {month} is not a month")
    start = dt.date(year, month, 1)
    end = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    return Window(start, end)


def crop_year_window(year: int) -> Window:
    """The window covering a whole crop year."""
    return Window(crop_year_opens(year), crop_year_opens(year + 1) - dt.timedelta(days=1))


def contract_year_window(year: int) -> Window:
    """The window covering a whole contract year."""
    return Window(contract_year_opens(year), contract_year_opens(year + 1) - dt.timedelta(days=1))


def parse_date(text: str, field: str = "date") -> dt.date:
    """Read an ISO date, and say which field it was when it is not one."""
    try:
        return dt.date.fromisoformat(text.strip())
    except ValueError as exc:
        raise ValidationError(f"{field} {text!r} is not a date like 2025-03-14") from exc
