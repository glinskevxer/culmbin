"""The floor: charging a piece, casting it, kilning it and stripping it.

Everything in this module reads several tables to answer one question, which
is why the checks live here rather than on any of the records.

The checks worth listing:

- A steep charge has to fit the steep. A box charge has to fit the *bed*,
  which is an area and a depth, so the depth is an argument and not a
  guess.
- A vessel holds one piece. The book does not enforce that, because two
  pieces in one box is a real thing when the plant is up against it and the
  maltster has decided to do it, and the package refuses by default and can
  be told otherwise.
- The recipes have to be for the style the piece is. A pale ale piece run on
  a lager curve makes something, and it does not make pale ale.
- A piece is cast when it has a steep-out weight and a steep-out moisture,
  because everything downstream is worked off the dry matter and there is no
  dry matter without both.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import MaltStyle, PieceStage, VesselKind
from culmbin.model.process import Piece
from culmbin.process.germination import (
    Schedule,
    accumulated,
    hours_to_cast,
    predicted_modification,
    progress,
    ready,
    stalled,
    turns_due,
)
from culmbin.process.losses import Balance
from culmbin.store.book import Book
from culmbin.store.pieces import (
    add_piece,
    get_piece,
    in_vessel,
    list_pieces,
    move_piece,
    readings,
    recipes_of,
    record_weighing,
    weighings,
)
from culmbin.store.recipes import get_curve, get_programme, get_schedule
from culmbin.store.varieties import get_variety
from culmbin.store.vessels import get_vessel


@dataclass(frozen=True, slots=True)
class FloorLine:
    """One piece on the floor sheet, with what it needs next."""

    piece: Piece
    degree_hours: float
    progress_percent: float
    turns_taken: int
    turns_wanted: int
    modification: float
    hours_to_cast: float
    stalled: bool

    @property
    def turns_owed(self) -> int:
        """Turns that have come due and have not been taken."""
        return max(0, self.turns_wanted - self.turns_taken)

    @property
    def ready(self) -> bool:
        """Whether the piece has earned its schedule."""
        return self.hours_to_cast <= 0.0


def _check_vessel(book: Book, code: str, kind: VesselKind, on: dt.date, share: bool) -> None:
    """Refuse a vessel that is the wrong kind, out of service, or occupied."""
    vessel = get_vessel(book, code)
    if vessel.kind is not kind:
        raise ConflictError(f"{code} is a {vessel.kind} and this needs a {kind}")
    if not vessel.in_service_on(on):
        raise ConflictError(f"{code} was not in service on {on}")
    if not share:
        sitting = in_vessel(book, code)
        if sitting is not None:
            raise ConflictError(f"{code} already has {sitting.code} in it")


def _check_recipes(book: Book, style: MaltStyle, programme: str, schedule: str, curve: str) -> None:
    """Refuse recipes that are for another style."""
    for name, found_style in (
        (programme, get_programme(book, programme).style),
        (schedule, get_schedule(book, schedule).style),
        (curve, get_curve(book, curve).style),
    ):
        if found_style is not style:
            raise ConflictError(f"{name} is a {found_style} recipe and this piece is {style}")


def charge(
    book: Book,
    piece: Piece,
    programme: str,
    schedule: str,
    curve: str,
    share: bool = False,
) -> Piece:
    """Put a charge of barley into a steep, with everything checked first."""
    if piece.stage is not PieceStage.STEEPING:
        raise StateError(f"{piece.code} is being charged and says it is {piece.stage}")
    assert piece.vessel is not None
    _check_vessel(book, piece.vessel, VesselKind.STEEP, piece.started, share)
    vessel = get_vessel(book, piece.vessel)
    if not vessel.holds(piece.charge_tonnes):
        raise ConflictError(
            f"{piece.charge_tonnes:.1f}t is over what {vessel.code} takes at {vessel.limit_t:.1f}t"
        )
    variety = get_variety(book, piece.variety)
    if not variety.on_the_list_on(piece.started):
        raise ConflictError(f"{variety.name} was not on the approved list on {piece.started}")
    _check_recipes(book, piece.style, programme, schedule, curve)
    with book.writing():
        return add_piece(book, piece, programme, schedule, curve)


def cast(
    book: Book,
    code: str,
    into: str,
    on: dt.date,
    steep_out_tonnes: float,
    steep_out_moisture: float,
    depth_cm: float,
    share: bool = False,
) -> Piece:
    """Cast a piece out of the steep and into a box or onto a floor."""
    piece = get_piece(book, code)
    if piece.stage is not PieceStage.STEEPING:
        raise StateError(f"{code} is {piece.stage} and cannot be cast")
    vessel = get_vessel(book, into)
    if vessel.kind not in (VesselKind.BOX, VesselKind.FLOOR):
        raise ConflictError(f"{into} is a {vessel.kind} and a piece is cast into a bed")
    if not vessel.in_service_on(on):
        raise ConflictError(f"{into} was not in service on {on}")
    if not share and in_vessel(book, into) is not None:
        raise ConflictError(f"{into} already has something in it")
    holds = vessel.tonnes_at_depth(depth_cm)
    if steep_out_tonnes > holds + 1e-9:
        raise ConflictError(
            f"{steep_out_tonnes:.1f}t is over the {holds:.1f}t {into} holds at {depth_cm:.0f}cm"
        )
    with book.writing():
        record_weighing(book, code, "steep_out", steep_out_tonnes, steep_out_moisture)
        return move_piece(book, code, PieceStage.GERMINATING, on, into)


def load_kiln(book: Book, code: str, kiln: str, on: dt.date, share: bool = False) -> Piece:
    """Move a piece off the floor and onto a kiln."""
    piece = get_piece(book, code)
    if piece.stage is not PieceStage.GERMINATING:
        raise StateError(f"{code} is {piece.stage} and cannot go on a kiln")
    _check_vessel(book, kiln, VesselKind.KILN, on, share)
    return move_piece(book, code, PieceStage.KILNING, on, kiln)


def strip_kiln(
    book: Book,
    code: str,
    on: dt.date,
    malt_tonnes: float,
    malt_moisture: float,
    culm_tonnes: float,
) -> Piece:
    """Take a piece off the kiln, weigh the malt and weigh the culm."""
    piece = get_piece(book, code)
    if piece.stage is not PieceStage.KILNING:
        raise StateError(f"{code} is {piece.stage} and is not on a kiln")
    with book.writing():
        record_weighing(book, code, "off_kiln", malt_tonnes, malt_moisture)
        record_weighing(book, code, "culm", culm_tonnes)
        return move_piece(book, code, PieceStage.KILNED, on)


def balance_of(book: Book, code: str) -> Balance:
    """The whole weight balance of a finished piece.

    Refuses a piece that has not been weighed at every point, because a
    balance with a missing weight is not a balance, it is three numbers.
    """
    piece = get_piece(book, code)
    weights = weighings(book, code)
    missing = [point for point in ("steep_out", "off_kiln", "culm") if point not in weights]
    if missing:
        raise StateError(f"{code} has not been weighed at {', '.join(missing)}")
    steep_out, steep_moisture = weights["steep_out"]
    malt, malt_moisture = weights["off_kiln"]
    culm, _ = weights["culm"]
    assert steep_moisture is not None
    assert malt_moisture is not None
    return Balance(
        charge_tonnes=piece.charge_tonnes,
        charge_moisture=piece.charge_moisture,
        steep_out_tonnes=steep_out,
        steep_out_moisture=steep_moisture,
        malt_tonnes=malt,
        malt_moisture=malt_moisture,
        culm_tonnes=culm,
    )


def schedule_of(book: Book, code: str) -> Schedule:
    """The germination schedule a piece is being run on."""
    _, schedule, _ = recipes_of(book, code)
    if schedule is None:
        raise NotFoundError(f"{code} is not on a germination schedule")
    return get_schedule(book, schedule)


def floor_line(book: Book, code: str, turns_taken: int = 0, at_celsius: float = 16.0) -> FloorLine:
    """One line of the floor sheet for one piece."""
    piece = get_piece(book, code)
    if piece.stage is not PieceStage.GERMINATING:
        raise StateError(f"{code} is {piece.stage} and is not on the floor")
    schedule = schedule_of(book, code)
    legs = readings(book, code, PieceStage.GERMINATING)
    return FloorLine(
        piece=piece,
        degree_hours=accumulated(schedule, legs),
        progress_percent=progress(schedule, legs),
        turns_taken=turns_taken,
        turns_wanted=turns_due(schedule, legs),
        modification=predicted_modification(schedule, legs),
        hours_to_cast=hours_to_cast(schedule, legs, at_celsius),
        stalled=stalled(schedule, legs),
    )


def floor_sheet(book: Book, at_celsius: float = 16.0) -> tuple[FloorLine, ...]:
    """Every piece on the floor, in code order, with what it needs next."""
    return tuple(
        floor_line(book, piece.code, at_celsius=at_celsius)
        for piece in list_pieces(book, stage=PieceStage.GERMINATING)
    )


def ready_to_cast(book: Book) -> tuple[Piece, ...]:
    """Every piece that has earned its schedule and is still on the floor."""
    out = []
    for piece in list_pieces(book, stage=PieceStage.GERMINATING):
        schedule = schedule_of(book, piece.code)
        if ready(schedule, readings(book, piece.code, PieceStage.GERMINATING)):
            out.append(piece)
    return tuple(out)
