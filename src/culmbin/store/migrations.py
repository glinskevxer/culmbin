"""The migrations, in order, and the machinery that applies them.

A migration is a version, a name and a script. It is applied once, inside a
transaction, and the version is written down in the same transaction. There
is no down migration: a book that has to go backwards goes backwards from a
backup, because a down migration is a piece of code that is written once,
never run, and wrong.

The scripts are here rather than in files because a wheel that has lost its
data directory is a wheel that cannot open a book, and that failure happens
on somebody else's machine at the wrong time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.errors import StateError, ValidationError
from culmbin.store.book import Book


@dataclass(frozen=True, slots=True)
class Migration:
    """One step of the schema."""

    version: int
    name: str
    script: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValidationError(f"migration version {self.version} is not one")
        if not self.name.strip():
            raise ValidationError(f"migration {self.version} has no name")
        if not self.script.strip():
            raise ValidationError(f"migration {self.version} has no script")


_META = """
CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
);
"""

_REGISTERS = """
CREATE TABLE party (
    code    TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    role    TEXT NOT NULL,
    opened  TEXT NOT NULL,
    closed  TEXT,
    holding TEXT,
    note    TEXT NOT NULL DEFAULT '',
    CHECK (role IN ('grower', 'merchant', 'customer', 'haulier')),
    CHECK (closed IS NULL OR closed >= opened),
    CHECK (holding IS NULL OR role = 'grower')
);

CREATE INDEX party_by_role ON party (role, code);

CREATE TABLE variety (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    habit     TEXT NOT NULL,
    approval  TEXT NOT NULL,
    listed    TEXT NOT NULL,
    withdrawn TEXT,
    CHECK (habit IN ('spring', 'winter')),
    CHECK (approval IN ('approved', 'provisional', 'under_test', 'withdrawn')),
    CHECK (withdrawn IS NULL OR withdrawn >= listed),
    CHECK ((approval = 'withdrawn') = (withdrawn IS NOT NULL))
);

CREATE TABLE vessel (
    code           TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    kind           TEXT NOT NULL,
    commissioned   TEXT NOT NULL,
    charge_limit_t REAL,
    floor_area_m2  REAL,
    depth_limit_cm REAL,
    retired        TEXT,
    CHECK (kind IN ('steep', 'box', 'floor', 'kiln')),
    CHECK (retired IS NULL OR retired >= commissioned),
    CHECK (
        (kind = 'steep') = (charge_limit_t IS NOT NULL)
    ),
    CHECK (
        (kind != 'steep') = (floor_area_m2 IS NOT NULL AND depth_limit_cm IS NOT NULL)
    )
);

CREATE INDEX vessel_by_kind ON vessel (kind, code);
"""

_ANALYSES = """
CREATE TABLE analysis (
    reference TEXT PRIMARY KEY,
    material  TEXT NOT NULL,
    taken     TEXT NOT NULL,
    note      TEXT NOT NULL DEFAULT '',
    CHECK (material IN ('barley', 'malt'))
);

CREATE INDEX analysis_by_day ON analysis (taken, reference);

CREATE TABLE result (
    analysis TEXT NOT NULL REFERENCES analysis (reference) ON DELETE CASCADE,
    code     TEXT NOT NULL,
    value    REAL NOT NULL,
    basis    TEXT,
    PRIMARY KEY (analysis, code),
    CHECK (value >= 0.0),
    CHECK (basis IS NULL OR basis IN ('as_is', 'dry'))
);

CREATE INDEX result_by_code ON result (code, analysis);
"""

_STANDARDS = """
CREATE TABLE standard (
    name              TEXT PRIMARY KEY,
    moisture_base     REAL NOT NULL,
    moisture_reject   REAL NOT NULL,
    nitrogen_min      REAL NOT NULL,
    nitrogen_max      REAL NOT NULL,
    nitrogen_reject   REAL NOT NULL,
    screenings_free   REAL NOT NULL,
    screenings_reject REAL NOT NULL,
    germination_floor REAL NOT NULL,
    energy_floor      REAL NOT NULL,
    admixture_reject  REAL NOT NULL,
    drying_per_point  TEXT NOT NULL,
    nitrogen_step     REAL NOT NULL,
    nitrogen_per_step TEXT NOT NULL,
    CHECK (moisture_base < moisture_reject),
    CHECK (nitrogen_min <= nitrogen_max),
    CHECK (nitrogen_max <= nitrogen_reject),
    CHECK (screenings_free < screenings_reject),
    CHECK (nitrogen_step > 0.0),
    CHECK (germination_floor > 0.0 AND germination_floor <= 100.0),
    CHECK (energy_floor > 0.0 AND energy_floor <= 100.0)
);
"""

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "the version table itself", _META),
    Migration(2, "parties, varieties and vessels", _REGISTERS),
    Migration(3, "analyses and their results", _ANALYSES),
    Migration(4, "the intake quality standards", _STANDARDS),
)
"""Every migration this package knows about, in the order they are applied.

Appending to this is how the schema changes. Editing one that has shipped is
how a book somebody else is holding stops matching the code that reads it,
so it is not done.
"""


def latest_version() -> int:
    """The version a fully migrated book is at."""
    return MIGRATIONS[-1].version


def current_version(book: Book) -> int:
    """What version a book is at, with zero meaning nothing has been applied."""
    if "schema_version" not in book.tables():
        return 0
    highest = book.scalar("SELECT max(version) FROM schema_version")
    return 0 if highest is None else int(highest)


def pending(book: Book) -> tuple[Migration, ...]:
    """Every migration a book has not had yet, in order."""
    at = current_version(book)
    return tuple(migration for migration in MIGRATIONS if migration.version > at)


def migrate(book: Book, applied_at: str) -> tuple[Migration, ...]:
    """Bring a book up to date, and say what was applied.

    `applied_at` is passed in rather than read off the clock, because this
    layer does not know what day it is and a caller that stamps its own
    migrations can be tested.
    """
    _check_order(MIGRATIONS)
    done = []
    for migration in pending(book):
        with book.writing() as writing:
            writing.executescript(migration.script)
            writing.execute(
                "INSERT INTO schema_version (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, applied_at),
            )
        done.append(migration)
    return tuple(done)


def _check_order(migrations: Sequence[Migration]) -> None:
    """Refuse a migration list that is out of order or has a repeat."""
    versions = [migration.version for migration in migrations]
    if versions != sorted(versions):
        raise StateError("the migrations are out of order")
    if len(versions) != len(set(versions)):
        raise StateError("two migrations share a version")


def open_book(path: str, applied_at: str) -> Book:
    """Open a book and bring it up to date, which is what every caller wants."""
    book = Book.open(path)
    try:
        migrate(book, applied_at)
    except Exception:
        book.close()
        raise
    return book
