"""Fixtures every test directory shares.

The important one is `book`, and the important thing about it is that it
closes. An unclosed sqlite connection is silence on 3.12 and a
`ResourceWarning` on 3.13, blamed on whichever test the collector happened
to be running when the garbage collector got round to it, which is never the
test that opened it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from culmbin.store.book import MEMORY, Book
from culmbin.store.migrations import migrate

APPLIED_AT = "2025-07-01T08:00:00+00:00"
TODAY = dt.date(2025, 11, 4)


@pytest.fixture
def book() -> Iterator[Book]:
    """An empty book at the current schema version."""
    with Book.open(MEMORY) as opened:
        migrate(opened, APPLIED_AT)
        yield opened
