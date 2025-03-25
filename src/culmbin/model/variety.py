"""Barley varieties and where they have got to on the approved list.

A variety is not an enumeration because the list changes every year, and it
is not free text because a contract that names Laureate has to mean the same
Laureate the analysis names. So it is a register: a code, a name, a habit and
an approval that moves over time.

The approval is the interesting part. A variety is under test, then
provisional, then approved, and eventually withdrawn, and a contract that
names the approved list is served by some of those and not others. Which
ones is a decision the contract makes, not one this module makes, so what is
here is the fact and not the judgement.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import Approval, Habit

ON_THE_LIST = frozenset({Approval.APPROVED, Approval.PROVISIONAL})
"""The approvals that count as being on the list at all.

Under test is not on the list, it is being looked at. Withdrawn was on the
list and is not any more. Neither of them is a state a contract that names
the list will accept, whatever else the barley assays.
"""


@dataclass(frozen=True, slots=True)
class Variety:
    """One barley variety, as the list has it today."""

    code: str
    name: str
    habit: Habit
    approval: Approval
    listed: dt.date
    withdrawn: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a variety needs a code")
        if not self.name.strip():
            raise ValidationError(f"{self.code} has no name")
        if self.withdrawn is not None and self.withdrawn < self.listed:
            raise ValidationError(f"{self.code} was withdrawn before it was listed")
        if self.approval is Approval.WITHDRAWN and self.withdrawn is None:
            raise ValidationError(f"{self.code} is withdrawn and no date says when")
        if self.approval is not Approval.WITHDRAWN and self.withdrawn is not None:
            raise ValidationError(f"{self.code} has a withdrawal date and is not withdrawn")

    @property
    def on_the_list(self) -> bool:
        """Whether this variety is on the approved list at all today."""
        return self.approval in ON_THE_LIST

    def on_the_list_on(self, day: dt.date) -> bool:
        """Whether it was on the list on a given day.

        A withdrawal is dated, so this can look backwards. A promotion from
        provisional to approved is not, so this cannot, and a caller asking
        about a date before the listing gets `False` rather than a guess.
        """
        if day < self.listed:
            return False
        if self.withdrawn is not None and day >= self.withdrawn:
            return False
        return self.approval in ON_THE_LIST or self.approval is Approval.WITHDRAWN

    def __str__(self) -> str:
        return f"{self.name} ({self.habit})"


@dataclass(frozen=True, slots=True)
class VarietyList:
    """The list, looked up by code."""

    varieties: tuple[Variety, ...]

    def __post_init__(self) -> None:
        codes = [variety.code for variety in self.varieties]
        duplicates = {code for code in codes if codes.count(code) > 1}
        if duplicates:
            raise ValidationError(f"two varieties share the code {sorted(duplicates)[0]}")

    def __iter__(self) -> Iterator[Variety]:
        return iter(self.varieties)

    def __len__(self) -> int:
        return len(self.varieties)

    def __getitem__(self, code: str) -> Variety:
        for variety in self.varieties:
            if variety.code == code:
                return variety
        raise NotFoundError(f"no variety called {code!r}")

    def on_the_list_on(self, day: dt.date) -> tuple[Variety, ...]:
        """Every variety on the list on a day, in the order they were given."""
        return tuple(variety for variety in self.varieties if variety.on_the_list_on(day))

    def of_habit(self, habit: Habit) -> tuple[Variety, ...]:
        """Every spring or every winter variety."""
        return tuple(variety for variety in self.varieties if variety.habit is habit)


def variety_list_of(varieties: Sequence[Variety]) -> VarietyList:
    """Build a list from a sequence."""
    return VarietyList(tuple(varieties))
