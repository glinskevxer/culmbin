"""One search across every register.

Somebody rings up with a code. They do not know, and should not have to
know, whether `L-2025-0412` is a lot, a ticket, a piece or a contract: they
have a number off a piece of paper and they want to know what it is.

The table below is the whole of it, and it is a table so that a register
added later is one line rather than an afternoon.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from culmbin.store.book import Book

_REGISTERS: Mapping[str, tuple[str, str, tuple[str, ...]]] = {
    "party": ("party", "code", ("name", "role")),
    "variety": ("variety", "code", ("name", "approval")),
    "vessel": ("vessel", "code", ("name", "kind")),
    "standard": ("standard", "name", ()),
    "specification": ("specification", "name", ("material",)),
    "purchase": ("purchase", "code", ("party", "variety")),
    "delivery": ("delivery", "ticket", ("party", "arrived")),
    "analysis": ("analysis", "reference", ("material", "taken")),
    "piece": ("piece", "code", ("variety", "stage")),
    "bin": ("malt_bin", "code", ("state",)),
    "lot": ("malt_lot", "code", ("malt_bin", "sealed")),
    "contract": ("contract", "code", ("customer", "state")),
    "call": ("call_off", "code", ("contract",)),
    "shipment": ("shipment", "code", ("contract", "state")),
    "programme": ("programme", "name", ("style",)),
    "schedule": ("schedule", "name", ("style",)),
    "curve": ("curve", "name", ("style",)),
}


@dataclass(frozen=True, slots=True)
class Found:
    """One thing a search turned up."""

    kind: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind:<14}{self.code:<24}{self.detail}".rstrip()


def searchable() -> tuple[str, ...]:
    """Every kind of thing a search looks in, in the order it looks."""
    return tuple(_REGISTERS)


def _look(book: Book, kind: str, code: str) -> Found:
    """Look in one register, giving back an empty result when nothing matches."""
    table, key, extra = _REGISTERS[kind]
    columns = ", ".join((key, *extra))
    row = book.first(f'SELECT {columns} FROM "{table}" WHERE {key} = ?', (code,))
    if row is None:
        return Found("", "", "")
    detail = " ".join(str(row[column]) for column in extra)
    return Found(kind, str(row[key]), detail)


def search(book: Book, code: str) -> tuple[Found, ...]:
    """Everything with that code, across every register."""
    out = []
    for kind in _REGISTERS:
        found = _look(book, kind, code)
        if found.kind:
            out.append(found)
    return tuple(out)


def counts(book: Book) -> Sequence[tuple[str, int]]:
    """How many rows each register holds, in table order.

    Reads the same table the search does, so a register that is searchable
    is counted and one that is not is neither.
    """
    out = []
    for kind, (table, _, _) in _REGISTERS.items():
        total = book.scalar(f'SELECT count(*) FROM "{table}"')
        out.append((kind, int(total or 0)))
    return out
