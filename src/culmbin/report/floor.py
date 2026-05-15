"""The floor pages: what is in the plant and what it needs next.

`shift_sheet` is the one that gets printed. It is read by somebody standing
up, so the order is what stops trains first: anything stalled, then turns
that are owed, then everything else with its clock.

`plant_page` is the other question, which is what is in each vessel and what
is free, and it is asked when the intake office wants to know whether there
is anywhere to put a steep tomorrow.
"""

from __future__ import annotations

from culmbin.model.enums import PieceStage, VesselKind
from culmbin.process.floor import FloorLine, floor_sheet
from culmbin.report.layout import Align, Column, heading, note, page, pairs, table_block
from culmbin.store.book import Book
from culmbin.store.pieces import in_vessel, list_pieces
from culmbin.store.vessels import list_vessels
from culmbin.units.clock import format_duration


def _line_row(line: FloorLine) -> list[str]:
    """One piece, as the shift sheet prints it."""
    return [
        line.piece.code,
        line.piece.vessel or "",
        line.piece.variety,
        f"{line.degree_hours:.0f}",
        f"{line.progress_percent:.0f}%",
        f"{line.modification:.0f}",
        str(line.turns_owed) if line.turns_owed else "",
        "ready" if line.ready else format_duration(line.hours_to_cast),
    ]


def shift_sheet(book: Book, at_celsius: float = 16.0) -> str:
    """Every piece on the floor, worst first.

    A stalled bed is at the top because it is not growing slowly, it is
    stopped, and somebody should be standing in front of it rather than
    reading about it tomorrow.
    """
    lines = floor_sheet(book, at_celsius=at_celsius)
    stalled = [line for line in lines if line.stalled]
    owed = [line for line in lines if line.turns_owed and not line.stalled]
    ready = [line for line in lines if line.ready and not line.stalled and not line.turns_owed]
    quiet = [
        line for line in lines if line not in stalled and line not in owed and line not in ready
    ]
    columns = [
        Column("piece"),
        Column("vessel"),
        Column("variety"),
        Column("degree h", Align.RIGHT),
        Column("done", Align.RIGHT),
        Column("mod", Align.RIGHT),
        Column("turns", Align.RIGHT),
        Column("to cast", Align.RIGHT),
    ]
    return page(
        [
            heading("germination floor"),
            pairs(
                [
                    ("pieces on the floor", str(len(lines))),
                    ("box temperature", f"{at_celsius:.1f}C"),
                ]
            ),
            table_block("stalled", columns, [_line_row(line) for line in stalled]),
            table_block("turns owed", columns, [_line_row(line) for line in owed]),
            table_block("ready to cast", columns, [_line_row(line) for line in ready]),
            table_block("running", columns, [_line_row(line) for line in quiet]),
            note(
                "nothing is on the floor.",
                when=not lines,
            ),
        ]
    )


def plant_page(book: Book) -> str:
    """What is in every vessel, and what is free.

    The free list is the useful half. It is what the intake office reads
    before promising a grower a delivery slot.
    """
    rows = []
    free = []
    for vessel in list_vessels(book):
        sitting = in_vessel(book, vessel.code)
        row = [
            vessel.code,
            str(vessel.kind),
            f"{vessel.limit_t:.1f}",
            "" if sitting is None else sitting.code,
            "" if sitting is None else str(sitting.stage),
        ]
        rows.append(row)
        if sitting is None:
            free.append([vessel.code, str(vessel.kind), f"{vessel.limit_t:.1f}"])
    counts = [
        (str(kind), str(len(list_vessels(book, kind).vessels)))
        for kind in VesselKind
        if list_vessels(book, kind).vessels
    ]
    return page(
        [
            heading("plant"),
            pairs(counts),
            table_block(
                "in use",
                [
                    Column("vessel"),
                    Column("kind"),
                    Column("holds", Align.RIGHT),
                    Column("piece"),
                    Column("stage"),
                ],
                [row for row in rows if row[3]],
            ),
            table_block(
                "free",
                [Column("vessel"), Column("kind"), Column("holds", Align.RIGHT)],
                free,
            ),
        ]
    )


def in_process_page(book: Book) -> str:
    """Every piece anywhere in the plant, by stage.

    The floor sheet is about the boxes. This is the one the planner reads,
    because a steep that finishes tonight needs a box tomorrow and a box
    that casts tomorrow needs a kiln.
    """
    blocks: list[list[str]] = []
    for stage in (PieceStage.STEEPING, PieceStage.GERMINATING, PieceStage.KILNING):
        rows = [
            [
                piece.code,
                piece.vessel or "",
                piece.variety,
                str(piece.style),
                f"{piece.charge_tonnes:.1f}",
                piece.started.isoformat(),
            ]
            for piece in list_pieces(book, stage=stage)
        ]
        blocks.append(
            table_block(
                str(stage),
                [
                    Column("piece"),
                    Column("vessel"),
                    Column("variety"),
                    Column("style"),
                    Column("charge", Align.RIGHT),
                    Column("started"),
                ],
                rows,
            )
        )
    body = [block for block in blocks if block]
    if not body:
        body = [["nothing is in the plant."]]
    return page([heading("in process"), *body])
