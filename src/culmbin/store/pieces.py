"""Reading and writing pieces, and everything hung off one.

A piece is a header that changes and three child tables that only ever grow.

The header carries where the piece is now, because that is what every screen
in the building asks first. The movements carry how it got there, which is
what the traceability walk needs and what nobody asks until they need it
very much indeed.

The readings are the temperature legs, and they are stamped with the stage
they belong to rather than with a clock. That is deliberate: the germination
clock counts degree hours in the box, and a leg recorded while the piece was
in the steep is not part of it. Filtering by stage is how the two are kept
apart, and it is why the stage is on the reading rather than being worked out
from a date.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.store.book import Book
from culmbin.store.query import narrowing, optional
from culmbin.store.rows import (
    as_count,
    as_date,
    as_enum,
    as_number,
    as_optional_number,
    as_optional_text,
    as_text,
    date_text,
)
from culmbin.units.clock import Leg

_COLUMNS = "code, variety, crop_year, style, charge_tonnes, charge_moisture, started, stage, vessel"

WEIGHING_POINTS = ("steep_out", "off_kiln", "culm")


def _piece(row: sqlite3.Row) -> Piece:
    """Turn a row into a piece."""
    return Piece(
        code=as_text(row, "code"),
        variety=as_text(row, "variety"),
        crop_year=as_count(row, "crop_year"),
        style=as_enum(row, "style", MaltStyle),
        charge_tonnes=as_number(row, "charge_tonnes"),
        charge_moisture=as_number(row, "charge_moisture"),
        started=as_date(row, "started"),
        stage=as_enum(row, "stage", PieceStage),
        vessel=as_optional_text(row, "vessel"),
    )


def add_piece(
    book: Book,
    piece: Piece,
    programme: str | None = None,
    schedule: str | None = None,
    curve: str | None = None,
) -> Piece:
    """Charge a piece into a steep, with the recipes it is to be run on."""
    with book.writing() as writing:
        writing.execute(
            f"INSERT INTO piece ({_COLUMNS}, programme, schedule, curve) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                piece.code,
                piece.variety,
                piece.crop_year,
                piece.style,
                piece.charge_tonnes,
                piece.charge_moisture,
                date_text(piece.started),
                piece.stage,
                piece.vessel,
                programme,
                schedule,
                curve,
            ),
        )
        writing.execute(
            "INSERT INTO movement (piece, seq, stage, vessel, on_day) VALUES (?, 1, ?, ?, ?)",
            (piece.code, piece.stage, piece.vessel, date_text(piece.started)),
        )
    return piece


def get_piece(book: Book, code: str) -> Piece:
    """One piece, or say which one was asked for."""
    row = book.first(f"SELECT {_COLUMNS} FROM piece WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no piece called {code!r}")
    return _piece(row)


def find_piece(book: Book, code: str) -> Piece | None:
    """One piece, or nothing."""
    return optional(lambda: get_piece(book, code))


def recipes_of(book: Book, code: str) -> tuple[str | None, str | None, str | None]:
    """The programme, schedule and curve a piece is being run on."""
    row = book.first("SELECT programme, schedule, curve FROM piece WHERE code = ?", (code,))
    if row is None:
        raise NotFoundError(f"no piece called {code!r}")
    return (
        as_optional_text(row, "programme"),
        as_optional_text(row, "schedule"),
        as_optional_text(row, "curve"),
    )


def move_piece(
    book: Book,
    code: str,
    stage: PieceStage,
    on: dt.date,
    vessel: str | None = None,
    note: str = "",
) -> Piece:
    """Move a piece to its next stage and write the movement down."""
    piece = get_piece(book, code)
    moved = piece.moved_to(stage, vessel)
    with book.writing() as writing:
        writing.execute(
            "UPDATE piece SET stage = ?, vessel = ? WHERE code = ?", (stage, vessel, code)
        )
        writing.execute(
            "INSERT INTO movement (piece, seq, stage, vessel, on_day, note) "
            "VALUES (?, (SELECT count(*) + 1 FROM movement WHERE piece = ?), ?, ?, ?, ?)",
            (code, code, stage, vessel, date_text(on), note),
        )
    return moved


def write_off_piece(book: Book, code: str, on: dt.date, note: str) -> Piece:
    """Write a piece off from wherever it had got to."""
    if not note.strip():
        raise StateError(f"{code} is being written off and nothing says why")
    piece = get_piece(book, code)
    off = piece.written_off()
    with book.writing() as writing:
        writing.execute(
            "UPDATE piece SET stage = ?, vessel = NULL WHERE code = ?",
            (PieceStage.WRITTEN_OFF, code),
        )
        writing.execute(
            "INSERT INTO movement (piece, seq, stage, vessel, on_day, note) "
            "VALUES (?, (SELECT count(*) + 1 FROM movement WHERE piece = ?), ?, NULL, ?, ?)",
            (code, code, PieceStage.WRITTEN_OFF, date_text(on), note),
        )
    return off


def movements(book: Book, code: str) -> tuple[tuple[PieceStage, str | None, dt.date, str], ...]:
    """Every movement of a piece, in the order they happened."""
    rows = book.query(
        "SELECT stage, vessel, on_day, note FROM movement WHERE piece = ? ORDER BY seq", (code,)
    )
    if not rows:
        raise NotFoundError(f"no piece called {code!r}")
    return tuple(
        (
            as_enum(row, "stage", PieceStage),
            as_optional_text(row, "vessel"),
            as_date(row, "on_day"),
            as_text(row, "note"),
        )
        for row in rows
    )


def add_reading(book: Book, code: str, stage: PieceStage, leg: Leg) -> None:
    """Add one temperature leg against a piece at a stage."""
    if stage not in (PieceStage.STEEPING, PieceStage.GERMINATING, PieceStage.KILNING):
        raise ConflictError(f"{stage} is not a stage anything is measured over")
    if find_piece(book, code) is None:
        raise NotFoundError(f"no piece called {code!r}")
    book.execute(
        "INSERT INTO reading (piece, seq, stage, hours, celsius) "
        "VALUES (?, (SELECT count(*) + 1 FROM reading WHERE piece = ?), ?, ?, ?)",
        (code, code, stage, leg.hours, leg.celsius),
    )


def readings(book: Book, code: str, stage: PieceStage | None = None) -> tuple[Leg, ...]:
    """Every leg recorded against a piece, in order, optionally at one stage.

    Filtering by stage is how the germination clock stays out of the steep.
    A caller that wants the box hours asks for the box hours.
    """
    if stage is None:
        rows = book.query(
            "SELECT hours, celsius FROM reading WHERE piece = ? ORDER BY seq", (code,)
        )
    else:
        rows = book.query(
            "SELECT hours, celsius FROM reading WHERE piece = ? AND stage = ? ORDER BY seq",
            (code, stage),
        )
    return tuple(
        Leg(hours=as_number(row, "hours"), celsius=as_number(row, "celsius")) for row in rows
    )


def record_weighing(
    book: Book, code: str, point: str, tonnes: float, moisture: float | None = None
) -> None:
    """Record one of the three weights a piece is measured at.

    The culm has no moisture because nobody measures it: it goes on the
    weighbridge on its way to the feed merchant and that is the last anybody
    thinks about it.
    """
    if point not in WEIGHING_POINTS:
        raise ConflictError(f"{point!r} is not a point a piece is weighed at")
    if find_piece(book, code) is None:
        raise NotFoundError(f"no piece called {code!r}")
    book.execute(
        "INSERT INTO weighing (piece, point, tonnes, moisture) VALUES (?, ?, ?, ?)",
        (code, point, tonnes, moisture),
    )


def weighings(book: Book, code: str) -> dict[str, tuple[float, float | None]]:
    """Every weight recorded against a piece, by point."""
    rows = book.query("SELECT point, tonnes, moisture FROM weighing WHERE piece = ?", (code,))
    return {
        as_text(row, "point"): (as_number(row, "tonnes"), as_optional_number(row, "moisture"))
        for row in rows
    }


def record_source(book: Book, code: str, ticket: str, tonnes: float) -> None:
    """Say which lorry load part of a piece's charge came out of.

    A steep charge is drawn out of a silo and a silo holds several loads, so
    a piece has several sources and each one carries a tonnage. Without this
    the traceability walk stops at the steep, which is the wrong end of it:
    the question is always which grower's barley is in the customer's beer.
    """
    if tonnes <= 0.0:
        raise ConflictError(f"a source of {tonnes} tonnes is not a source")
    if find_piece(book, code) is None:
        raise NotFoundError(f"no piece called {code!r}")
    book.execute(
        "INSERT INTO piece_source (piece, ticket, tonnes) VALUES (?, ?, ?)",
        (code, ticket, tonnes),
    )


def sources_of(book: Book, code: str) -> tuple[tuple[str, float], ...]:
    """Every lorry load a piece was charged from, in ticket order."""
    rows = book.query(
        "SELECT ticket, tonnes FROM piece_source WHERE piece = ? ORDER BY ticket", (code,)
    )
    return tuple((as_text(row, "ticket"), as_number(row, "tonnes")) for row in rows)


def pieces_from_ticket(book: Book, ticket: str) -> tuple[str, ...]:
    """Every piece a lorry load went into, in code order."""
    rows = book.query("SELECT piece FROM piece_source WHERE ticket = ? ORDER BY piece", (ticket,))
    return tuple(as_text(row, "piece") for row in rows)


def list_pieces(
    book: Book,
    stage: PieceStage | None = None,
    variety: str | None = None,
    crop_year: int | None = None,
) -> tuple[Piece, ...]:
    """Every piece, in code order, narrowed the three ways the floor asks."""
    narrow = narrowing().maybe("stage = ?", stage).maybe("variety = ?", variety)
    narrow.maybe("crop_year = ?", crop_year)
    rows = book.query(f"SELECT {_COLUMNS} FROM piece{narrow.where} ORDER BY code", narrow.values)
    return tuple(_piece(row) for row in rows)


def in_vessel(book: Book, vessel: str) -> Piece | None:
    """Whatever is in a vessel, or nothing.

    Only one piece is ever in a vessel, which the floor planner relies on and
    the book does not enforce, so this returns the first in code order rather
    than pretending the question cannot have two answers.
    """
    row = book.first(f"SELECT {_COLUMNS} FROM piece WHERE vessel = ? ORDER BY code", (vessel,))
    return None if row is None else _piece(row)
