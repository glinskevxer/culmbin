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

_PIECES = """
CREATE TABLE piece (
    code            TEXT PRIMARY KEY,
    variety         TEXT NOT NULL REFERENCES variety (code),
    crop_year       INTEGER NOT NULL,
    style           TEXT NOT NULL,
    charge_tonnes   REAL NOT NULL,
    charge_moisture REAL NOT NULL,
    started         TEXT NOT NULL,
    stage           TEXT NOT NULL,
    vessel          TEXT REFERENCES vessel (code),
    programme       TEXT REFERENCES programme (name),
    schedule        TEXT REFERENCES schedule (name),
    curve           TEXT REFERENCES curve (name),
    CHECK (charge_tonnes > 0.0),
    CHECK (charge_moisture >= 0.0 AND charge_moisture < 60.0),
    CHECK (style IN ('lager', 'pale_ale', 'distilling', 'vienna')),
    CHECK (stage IN (
        'steeping', 'germinating', 'kilning', 'kilned', 'binned', 'written_off'
    )),
    CHECK ((stage IN ('steeping', 'germinating', 'kilning')) = (vessel IS NOT NULL))
);

CREATE INDEX piece_by_stage ON piece (stage, code);
CREATE INDEX piece_by_vessel ON piece (vessel, code);

CREATE TABLE movement (
    piece  TEXT NOT NULL REFERENCES piece (code) ON DELETE CASCADE,
    seq    INTEGER NOT NULL,
    stage  TEXT NOT NULL,
    vessel TEXT REFERENCES vessel (code),
    on_day TEXT NOT NULL,
    note   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (piece, seq),
    CHECK (stage IN (
        'steeping', 'germinating', 'kilning', 'kilned', 'binned', 'written_off'
    ))
);

CREATE TABLE reading (
    piece   TEXT NOT NULL REFERENCES piece (code) ON DELETE CASCADE,
    seq     INTEGER NOT NULL,
    stage   TEXT NOT NULL,
    hours   REAL NOT NULL,
    celsius REAL NOT NULL,
    PRIMARY KEY (piece, seq),
    CHECK (hours > 0.0),
    CHECK (stage IN ('steeping', 'germinating', 'kilning'))
);

CREATE INDEX reading_by_stage ON reading (piece, stage, seq);

CREATE TABLE weighing (
    piece    TEXT NOT NULL REFERENCES piece (code) ON DELETE CASCADE,
    point    TEXT NOT NULL,
    tonnes   REAL NOT NULL,
    moisture REAL,
    PRIMARY KEY (piece, point),
    CHECK (point IN ('steep_out', 'off_kiln', 'culm')),
    CHECK (tonnes >= 0.0),
    CHECK (moisture IS NULL OR (moisture >= 0.0 AND moisture < 60.0)),
    CHECK ((point = 'culm') OR moisture IS NOT NULL)
);
"""

_BINS = """
CREATE TABLE malt_bin (
    code             TEXT PRIMARY KEY,
    capacity_tonnes  REAL NOT NULL,
    state            TEXT NOT NULL,
    mixed            INTEGER NOT NULL DEFAULT 0,
    commissioned     TEXT,
    CHECK (capacity_tonnes > 0.0),
    CHECK (state IN ('empty', 'filling', 'sealed', 'drawing')),
    CHECK (mixed IN (0, 1))
);

CREATE TABLE bin_receipt (
    malt_bin TEXT NOT NULL REFERENCES malt_bin (code) ON DELETE CASCADE,
    seq      INTEGER NOT NULL,
    piece    TEXT NOT NULL REFERENCES piece (code),
    tonnes   REAL NOT NULL,
    moisture REAL NOT NULL,
    on_day   TEXT NOT NULL,
    PRIMARY KEY (malt_bin, seq),
    CHECK (tonnes > 0.0),
    CHECK (moisture >= 0.0 AND moisture < 60.0)
);

CREATE INDEX bin_receipt_by_piece ON bin_receipt (piece, malt_bin);

CREATE TABLE bin_issue (
    malt_bin TEXT NOT NULL REFERENCES malt_bin (code) ON DELETE CASCADE,
    seq      INTEGER NOT NULL,
    tonnes   REAL NOT NULL,
    on_day   TEXT NOT NULL,
    note     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (malt_bin, seq),
    CHECK (tonnes > 0.0)
);

CREATE TABLE malt_lot (
    code     TEXT PRIMARY KEY,
    malt_bin TEXT NOT NULL REFERENCES malt_bin (code),
    sealed   TEXT NOT NULL,
    tonnes   REAL NOT NULL,
    moisture REAL NOT NULL,
    analysis TEXT REFERENCES analysis (reference),
    style    TEXT,
    CHECK (tonnes > 0.0),
    CHECK (moisture >= 0.0 AND moisture < 60.0),
    CHECK (style IS NULL OR style IN ('lager', 'pale_ale', 'distilling', 'vienna'))
);

CREATE INDEX malt_lot_by_bin ON malt_lot (malt_bin, code);

CREATE TABLE lot_variety (
    lot     TEXT NOT NULL REFERENCES malt_lot (code) ON DELETE CASCADE,
    variety TEXT NOT NULL REFERENCES variety (code),
    PRIMARY KEY (lot, variety)
);

CREATE TABLE lot_crop_year (
    lot       TEXT NOT NULL REFERENCES malt_lot (code) ON DELETE CASCADE,
    crop_year INTEGER NOT NULL,
    PRIMARY KEY (lot, crop_year)
);

CREATE TABLE lot_parent (
    lot   TEXT NOT NULL REFERENCES malt_lot (code) ON DELETE CASCADE,
    piece TEXT NOT NULL REFERENCES piece (code),
    PRIMARY KEY (lot, piece)
);

CREATE INDEX lot_parent_by_piece ON lot_parent (piece, lot);
"""

_SPECS = """
CREATE TABLE specification (
    name     TEXT PRIMARY KEY,
    material TEXT NOT NULL,
    CHECK (material IN ('barley', 'malt'))
);

CREATE TABLE clause (
    specification TEXT NOT NULL REFERENCES specification (name) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    code          TEXT NOT NULL,
    basis         TEXT,
    minimum       REAL,
    maximum       REAL,
    PRIMARY KEY (specification, seq),
    CHECK (basis IS NULL OR basis IN ('as_is', 'dry')),
    CHECK (minimum IS NOT NULL OR maximum IS NOT NULL),
    CHECK (minimum IS NULL OR maximum IS NULL OR minimum <= maximum)
);

CREATE UNIQUE INDEX clause_once_per_analyte ON clause (specification, code);

CREATE TABLE specification_variety (
    specification TEXT NOT NULL REFERENCES specification (name) ON DELETE CASCADE,
    variety       TEXT NOT NULL REFERENCES variety (code),
    PRIMARY KEY (specification, variety)
);
"""

_SALES = """
CREATE TABLE contract (
    code            TEXT PRIMARY KEY,
    customer        TEXT NOT NULL REFERENCES party (code),
    specification   TEXT NOT NULL REFERENCES specification (name),
    tonnes          REAL NOT NULL,
    moisture        REAL NOT NULL,
    price_per_tonne TEXT NOT NULL,
    window_start    TEXT NOT NULL,
    window_end      TEXT NOT NULL,
    signed          TEXT NOT NULL,
    state           TEXT NOT NULL,
    variety         TEXT REFERENCES variety (code),
    CHECK (tonnes > 0.0),
    CHECK (moisture > 0.0 AND moisture < 12.0),
    CHECK (window_end >= window_start),
    CHECK (state IN ('draft', 'signed', 'closed', 'cancelled'))
);

CREATE INDEX contract_by_customer ON contract (customer, code);
CREATE INDEX contract_by_state ON contract (state, code);

CREATE TABLE call_off (
    code        TEXT PRIMARY KEY,
    contract    TEXT NOT NULL REFERENCES contract (code) ON DELETE CASCADE,
    tonnes      REAL NOT NULL,
    week_start  TEXT NOT NULL,
    week_end    TEXT NOT NULL,
    placed      TEXT NOT NULL,
    CHECK (tonnes > 0.0),
    CHECK (week_end >= week_start)
);

CREATE INDEX call_off_by_contract ON call_off (contract, week_start);

CREATE TABLE shipment (
    code       TEXT PRIMARY KEY,
    contract   TEXT NOT NULL REFERENCES contract (code),
    lot        TEXT NOT NULL REFERENCES malt_lot (code),
    tonnes     REAL NOT NULL,
    moisture   REAL NOT NULL,
    despatched TEXT NOT NULL,
    state      TEXT NOT NULL,
    call_off   TEXT REFERENCES call_off (code),
    haulier    TEXT REFERENCES party (code),
    vehicle    TEXT,
    CHECK (tonnes > 0.0),
    CHECK (moisture >= 0.0 AND moisture < 60.0),
    CHECK (state IN ('planned', 'loaded', 'despatched', 'cancelled'))
);

CREATE INDEX shipment_by_contract ON shipment (contract, despatched);
CREATE INDEX shipment_by_lot ON shipment (lot, code);
"""

_SOURCES = """
CREATE TABLE piece_source (
    piece  TEXT NOT NULL REFERENCES piece (code) ON DELETE CASCADE,
    ticket TEXT NOT NULL REFERENCES delivery (ticket),
    tonnes REAL NOT NULL,
    PRIMARY KEY (piece, ticket),
    CHECK (tonnes > 0.0)
);

CREATE INDEX piece_source_by_ticket ON piece_source (ticket, piece);
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
    Migration(9, "pieces, their movements, their readings and their weights", _PIECES),
    Migration(10, "malt bins, what went in and out, and the lots", _BINS),
    Migration(11, "specifications and their clauses", _SPECS),
    Migration(12, "contracts, call-offs and shipments", _SALES),
    Migration(13, "which lorry loads a piece was charged from", _SOURCES),
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
