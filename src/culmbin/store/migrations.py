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

_INTAKE = """
CREATE TABLE purchase (
    code            TEXT PRIMARY KEY,
    party           TEXT NOT NULL REFERENCES party (code),
    variety         TEXT NOT NULL REFERENCES variety (code),
    crop_year       INTEGER NOT NULL,
    tonnes          REAL NOT NULL,
    window_start    TEXT NOT NULL,
    window_end      TEXT NOT NULL,
    standard        TEXT NOT NULL REFERENCES standard (name),
    price_per_tonne TEXT NOT NULL,
    signed          TEXT NOT NULL,
    CHECK (tonnes > 0.0),
    CHECK (window_end >= window_start)
);

CREATE INDEX purchase_by_party ON purchase (party, code);
CREATE INDEX purchase_by_crop ON purchase (crop_year, code);

CREATE TABLE delivery (
    ticket   TEXT PRIMARY KEY,
    purchase TEXT NOT NULL REFERENCES purchase (code),
    party    TEXT NOT NULL REFERENCES party (code),
    arrived  TEXT NOT NULL,
    gross_kg REAL NOT NULL,
    tare_kg  REAL NOT NULL,
    haulier  TEXT REFERENCES party (code),
    vehicle  TEXT,
    sample   TEXT REFERENCES analysis (reference),
    CHECK (gross_kg > tare_kg),
    CHECK (tare_kg > 0.0)
);

CREATE INDEX delivery_by_purchase ON delivery (purchase, arrived);
CREATE INDEX delivery_by_day ON delivery (arrived, ticket);
"""

_GRADINGS = """
CREATE TABLE grading (
    ticket         TEXT PRIMARY KEY REFERENCES delivery (ticket) ON DELETE CASCADE,
    standard       TEXT NOT NULL REFERENCES standard (name),
    outcome        TEXT NOT NULL,
    net_tonnes     REAL NOT NULL,
    settled_tonnes REAL NOT NULL,
    graded_on      TEXT NOT NULL,
    CHECK (outcome IN ('accepted', 'accepted_on_deduction', 'rejected')),
    CHECK (net_tonnes > 0.0),
    CHECK (settled_tonnes >= 0.0),
    CHECK (settled_tonnes <= net_tonnes),
    CHECK ((outcome = 'rejected') = (settled_tonnes = 0.0))
);

CREATE INDEX grading_by_outcome ON grading (outcome, ticket);

CREATE TABLE rejection (
    ticket TEXT NOT NULL REFERENCES grading (ticket) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    PRIMARY KEY (ticket, reason),
    CHECK (reason IN (
        'germination', 'moisture', 'screenings', 'nitrogen', 'admixture',
        'insect', 'odour', 'treated_seed'
    ))
);

CREATE TABLE adjustment (
    ticket    TEXT NOT NULL REFERENCES grading (ticket) ON DELETE CASCADE,
    seq       INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    note      TEXT NOT NULL,
    tonnes    REAL NOT NULL DEFAULT 0.0,
    per_tonne TEXT NOT NULL DEFAULT '0.00',
    PRIMARY KEY (ticket, seq),
    CHECK (tonnes >= 0.0),
    CHECK (tonnes = 0.0 OR per_tonne = '0.00')
);
"""

_HARVESTED = """
ALTER TABLE delivery ADD COLUMN harvested TEXT;
"""

_RECIPES = """
CREATE TABLE programme (
    name            TEXT PRIMARY KEY,
    style           TEXT NOT NULL,
    target_moisture REAL NOT NULL,
    CHECK (style IN ('lager', 'pale_ale', 'distilling', 'vienna')),
    CHECK (target_moisture > 0.0 AND target_moisture <= 48.0)
);

CREATE TABLE programme_leg (
    programme TEXT NOT NULL REFERENCES programme (name) ON DELETE CASCADE,
    seq       INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    hours     REAL NOT NULL,
    celsius   REAL NOT NULL,
    PRIMARY KEY (programme, seq),
    CHECK (kind IN ('wet_stand', 'air_rest')),
    CHECK (hours > 0.0)
);

CREATE TABLE schedule (
    name                TEXT PRIMARY KEY,
    style               TEXT NOT NULL,
    target_degree_hours REAL NOT NULL,
    base_c              REAL NOT NULL,
    CHECK (style IN ('lager', 'pale_ale', 'distilling', 'vienna')),
    CHECK (target_degree_hours > 0.0)
);

CREATE TABLE schedule_turn (
    schedule     TEXT NOT NULL REFERENCES schedule (name) ON DELETE CASCADE,
    seq          INTEGER NOT NULL,
    degree_hours REAL NOT NULL,
    PRIMARY KEY (schedule, seq),
    CHECK (degree_hours > 0.0)
);

CREATE TABLE curve (
    name            TEXT PRIMARY KEY,
    style           TEXT NOT NULL,
    target_moisture REAL NOT NULL,
    CHECK (style IN ('lager', 'pale_ale', 'distilling', 'vienna')),
    CHECK (target_moisture > 0.0 AND target_moisture < 12.0)
);

CREATE TABLE curve_step (
    curve       TEXT NOT NULL REFERENCES curve (name) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    phase       TEXT NOT NULL,
    hours       REAL NOT NULL,
    air_celsius REAL NOT NULL,
    PRIMARY KEY (curve, seq),
    CHECK (phase IN ('free_drying', 'break', 'curing')),
    CHECK (hours > 0.0)
);
"""

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "the version table itself", _META),
    Migration(2, "parties, varieties and vessels", _REGISTERS),
    Migration(3, "analyses and their results", _ANALYSES),
    Migration(4, "the intake quality standards", _STANDARDS),
    Migration(5, "purchases and deliveries", _INTAKE),
    Migration(6, "gradings, their rejections and their adjustments", _GRADINGS),
    Migration(7, "when the barley on a delivery was cut", _HARVESTED),
    Migration(8, "steep programmes, germination schedules and kiln curves", _RECIPES),
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
