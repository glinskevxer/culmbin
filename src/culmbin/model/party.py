"""Growers, merchants, customers and hauliers.

They are all one record because the differences between them are in what
they are attached to rather than in what they are. A grower has a holding
number, a customer has a delivery address and a haulier has a fleet, and all
three of those are somewhere else. What is here is the name, the code, the
role and whether they are still trading with us.

One company can hold two roles and it gets two rows. That looks like
duplication and it is not: the contracts, the settlement terms and the
person who answers the telephone are all different, and a single row with a
set of roles turns every query into a filter that somebody will forget.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import Role


@dataclass(frozen=True, slots=True)
class Party:
    """Somebody we buy from, sell to or send a lorry with."""

    code: str
    name: str
    role: Role
    opened: dt.date
    closed: dt.date | None = None
    holding: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a party needs a code")
        if not self.name.strip():
            raise ValidationError(f"{self.code} has no name")
        if self.closed is not None and self.closed < self.opened:
            raise ValidationError(f"{self.code} closed before it opened")
        if self.holding is not None and self.role is not Role.GROWER:
            raise ValidationError(f"{self.code} is a {self.role} and has no holding number")

    def trading_on(self, day: dt.date) -> bool:
        """Whether we were trading with them on a day."""
        if day < self.opened:
            return False
        return self.closed is None or day < self.closed

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


@dataclass(frozen=True, slots=True)
class Register:
    """Every party, looked up by code or by role."""

    parties: tuple[Party, ...]

    def __post_init__(self) -> None:
        codes = [party.code for party in self.parties]
        duplicates = {code for code in codes if codes.count(code) > 1}
        if duplicates:
            raise ValidationError(f"two parties share the code {sorted(duplicates)[0]}")

    def __iter__(self) -> Iterator[Party]:
        return iter(self.parties)

    def __len__(self) -> int:
        return len(self.parties)

    def __getitem__(self, code: str) -> Party:
        for party in self.parties:
            if party.code == code:
                return party
        raise NotFoundError(f"no party called {code!r}")

    def of_role(self, role: Role) -> tuple[Party, ...]:
        """Everybody in one role, in the order they were given."""
        return tuple(party for party in self.parties if party.role is role)

    def trading_on(self, day: dt.date) -> tuple[Party, ...]:
        """Everybody we were trading with on a day."""
        return tuple(party for party in self.parties if party.trading_on(day))


def register_of(parties: Sequence[Party]) -> Register:
    """Build a register from a sequence."""
    return Register(tuple(parties))
