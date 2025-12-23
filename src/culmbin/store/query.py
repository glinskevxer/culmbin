"""Building a narrowed query, and asking for something that may not be there.

Eight modules had each grown the same fifteen lines: a list of clauses, a
list of parameters, an `if` per filter, and a join at the end. They were not
identical either. Two of them put the `WHERE` in with a leading space and
six did not, one of them added the parameter before the clause, and every
one of them was one editing mistake away from a query that filtered on the
wrong column.

`Narrowing` is that, once. Add a filter with `maybe`, which does nothing at
all when the value is `None`, and ask for the clause at the end.

`optional` is the other thing every register had a copy of: a `find_x` that
is a `get_x` with the not-found turned into `None`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from culmbin.errors import NotFoundError
from culmbin.store.rows import date_text

T = TypeVar("T")


@dataclass(slots=True)
class Narrowing:
    """The `WHERE` clause of a listing, built one filter at a time."""

    clauses: list[str] = field(default_factory=list)
    params: list[object] = field(default_factory=list)

    def always(self, clause: str, *values: object) -> Narrowing:
        """Add a clause that is always applied."""
        self.clauses.append(clause)
        self.params.extend(values)
        return self

    def maybe(self, clause: str, value: object) -> Narrowing:
        """Add a clause, unless the value is nothing.

        This is the whole point. The caller writes one line per filter and
        never writes an `if`, so a filter cannot be added to the clause list
        and forgotten in the parameter list.
        """
        if value is None:
            return self
        return self.always(clause, value)

    def since(self, column: str, day: dt.date | None) -> Narrowing:
        """Narrow to days on or after one, if there is one."""
        return self.maybe(f"{column} >= ?", None if day is None else date_text(day))

    def until(self, column: str, day: dt.date | None) -> Narrowing:
        """Narrow to days on or before one, if there is one."""
        return self.maybe(f"{column} <= ?", None if day is None else date_text(day))

    @property
    def where(self) -> str:
        """The clause, with its leading space, or nothing at all."""
        return f" WHERE {' AND '.join(self.clauses)}" if self.clauses else ""

    @property
    def values(self) -> list[object]:
        """The parameters, in the order the clauses use them."""
        return self.params

    def __len__(self) -> int:
        return len(self.clauses)


def narrowing() -> Narrowing:
    """An empty narrowing, for a listing to add filters to."""
    return Narrowing()


def optional(getter: Callable[[], T]) -> T | None:
    """Whatever a getter gives back, or nothing if it says there is none.

    Every register had its own copy of this, and every copy was a `try`, an
    `except NotFoundError` and a `return None`.
    """
    try:
        return getter()
    except NotFoundError:
        return None
