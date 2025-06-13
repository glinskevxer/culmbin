"""Reading and writing the three recipes: programmes, schedules and curves.

They are three separate sets of functions doing the same shape of thing,
which is on purpose for now. A steep programme has legs that alternate, a
germination schedule has turning points on a degree hour clock, and a kiln
curve has steps in phase order, and the only thing the three have in common
is that they are a header and an ordered child table.

A recipe is written and not edited. Pieces are run against one by name, and a
programme whose second wet stand quietly grew by two hours is a programme
that no longer describes the pieces that were run on it. Next season's is a
new name.
"""

from __future__ import annotations

from culmbin.errors import NotFoundError
from culmbin.model.enums import KilnPhase, LegKind, MaltStyle
from culmbin.process.germination import Schedule
from culmbin.process.kiln import Curve, KilnStep
from culmbin.process.steep import Programme, SteepLeg
from culmbin.store.book import Book
from culmbin.store.rows import as_enum, as_number, as_text


def save_programme(book: Book, programme: Programme) -> Programme:
    """Write a steep programme and its legs."""
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO programme (name, style, target_moisture) VALUES (?, ?, ?)",
            (programme.name, programme.style, programme.target_moisture),
        )
        writing.executemany(
            "INSERT INTO programme_leg (programme, seq, kind, hours, celsius) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (programme.name, seq, leg.kind, leg.hours, leg.celsius)
                for seq, leg in enumerate(programme.legs, start=1)
            ],
        )
    return programme


def get_programme(book: Book, name: str) -> Programme:
    """One steep programme, or say which one was asked for."""
    row = book.first("SELECT name, style, target_moisture FROM programme WHERE name = ?", (name,))
    if row is None:
        raise NotFoundError(f"no steep programme called {name!r}")
    legs = book.query(
        "SELECT kind, hours, celsius FROM programme_leg WHERE programme = ? ORDER BY seq",
        (name,),
    )
    return Programme(
        name=as_text(row, "name"),
        style=as_enum(row, "style", MaltStyle),
        legs=tuple(
            SteepLeg(
                kind=as_enum(leg, "kind", LegKind),
                hours=as_number(leg, "hours"),
                celsius=as_number(leg, "celsius"),
            )
            for leg in legs
        ),
        target_moisture=as_number(row, "target_moisture"),
    )


def list_programmes(book: Book, style: MaltStyle | None = None) -> tuple[Programme, ...]:
    """Every steep programme, in name order."""
    if style is None:
        rows = book.query("SELECT name FROM programme ORDER BY name")
    else:
        rows = book.query("SELECT name FROM programme WHERE style = ? ORDER BY name", (style,))
    return tuple(get_programme(book, as_text(row, "name")) for row in rows)


def save_schedule(book: Book, schedule: Schedule) -> Schedule:
    """Write a germination schedule and its turning points."""
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO schedule (name, style, target_degree_hours, base_c) VALUES (?, ?, ?, ?)",
            (schedule.name, schedule.style, schedule.target_degree_hours, schedule.base_c),
        )
        writing.executemany(
            "INSERT INTO schedule_turn (schedule, seq, degree_hours) VALUES (?, ?, ?)",
            [(schedule.name, seq, point) for seq, point in enumerate(schedule.turns_at, start=1)],
        )
    return schedule


def get_schedule(book: Book, name: str) -> Schedule:
    """One germination schedule, or say which one was asked for."""
    row = book.first(
        "SELECT name, style, target_degree_hours, base_c FROM schedule WHERE name = ?", (name,)
    )
    if row is None:
        raise NotFoundError(f"no germination schedule called {name!r}")
    turns = book.query(
        "SELECT degree_hours FROM schedule_turn WHERE schedule = ? ORDER BY seq", (name,)
    )
    return Schedule(
        name=as_text(row, "name"),
        style=as_enum(row, "style", MaltStyle),
        target_degree_hours=as_number(row, "target_degree_hours"),
        turns_at=tuple(as_number(turn, "degree_hours") for turn in turns),
        base_c=as_number(row, "base_c"),
    )


def list_schedules(book: Book, style: MaltStyle | None = None) -> tuple[Schedule, ...]:
    """Every germination schedule, in name order."""
    if style is None:
        rows = book.query("SELECT name FROM schedule ORDER BY name")
    else:
        rows = book.query("SELECT name FROM schedule WHERE style = ? ORDER BY name", (style,))
    return tuple(get_schedule(book, as_text(row, "name")) for row in rows)


def save_curve(book: Book, curve: Curve) -> Curve:
    """Write a kiln curve and its steps."""
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO curve (name, style, target_moisture) VALUES (?, ?, ?)",
            (curve.name, curve.style, curve.target_moisture),
        )
        writing.executemany(
            "INSERT INTO curve_step (curve, seq, phase, hours, air_celsius) VALUES (?, ?, ?, ?, ?)",
            [
                (curve.name, seq, step.phase, step.hours, step.air_celsius)
                for seq, step in enumerate(curve.steps, start=1)
            ],
        )
    return curve


def get_curve(book: Book, name: str) -> Curve:
    """One kiln curve, or say which one was asked for."""
    row = book.first("SELECT name, style, target_moisture FROM curve WHERE name = ?", (name,))
    if row is None:
        raise NotFoundError(f"no kiln curve called {name!r}")
    steps = book.query(
        "SELECT phase, hours, air_celsius FROM curve_step WHERE curve = ? ORDER BY seq", (name,)
    )
    return Curve(
        name=as_text(row, "name"),
        style=as_enum(row, "style", MaltStyle),
        steps=tuple(
            KilnStep(
                phase=as_enum(step, "phase", KilnPhase),
                hours=as_number(step, "hours"),
                air_celsius=as_number(step, "air_celsius"),
            )
            for step in steps
        ),
        target_moisture=as_number(row, "target_moisture"),
    )


def list_curves(book: Book, style: MaltStyle | None = None) -> tuple[Curve, ...]:
    """Every kiln curve, in name order."""
    if style is None:
        rows = book.query("SELECT name FROM curve ORDER BY name")
    else:
        rows = book.query("SELECT name FROM curve WHERE style = ? ORDER BY name", (style,))
    return tuple(get_curve(book, as_text(row, "name")) for row in rows)


def recipes_for(book: Book, style: MaltStyle) -> tuple[int, int, int]:
    """How many of each recipe there are for a style.

    The floor planner needs all three to run a piece, so a style with two
    programmes and no curve is a gap somebody should know about before a
    piece is cast rather than eighteen hours later.
    """
    return (
        len(list_programmes(book, style)),
        len(list_schedules(book, style)),
        len(list_curves(book, style)),
    )
