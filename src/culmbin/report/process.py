"""The pages about one piece: where it has been and what it weighed.

`piece_page` is the whole life of a piece on one sheet, and it is what
somebody prints when a lot is queried. It carries the movements in order,
because a piece that spent an extra day on the floor because the kiln was
full explains a great deal about the analysis.

`balance_page` is the number the plant manager watches. Malting loss is the
one figure that compares one month with another, and yield is the one
everybody quotes, so they are next to each other with a line saying why they
disagree.
"""

from __future__ import annotations

from culmbin.errors import StateError
from culmbin.model.enums import PieceStage
from culmbin.process.floor import balance_of
from culmbin.process.losses import CULM_FRACTION_OF_LOSS
from culmbin.report.layout import Align, Column, heading, page, pairs, table_block
from culmbin.store.bins import bins_holding
from culmbin.store.book import Book
from culmbin.store.lots import lots_from_piece
from culmbin.store.pieces import (
    get_piece,
    list_pieces,
    movements,
    readings,
    recipes_of,
    sources_of,
    weighings,
)
from culmbin.units.clock import degree_hours, elapsed_hours


def piece_page(book: Book, code: str) -> str:
    """The whole life of one piece."""
    piece = get_piece(book, code)
    programme, schedule, curve = recipes_of(book, code)
    weights = weighings(book, code)
    facts = [
        ("piece", piece.code),
        ("variety", piece.variety),
        ("crop", str(piece.crop_year)),
        ("style", str(piece.style)),
        ("charged", f"{piece.charge_tonnes:.2f}t at {piece.charge_moisture:.1f}%"),
        ("dry matter", f"{piece.charge_dry_tonnes:.2f}t"),
        ("started", piece.started.isoformat()),
        ("stage", str(piece.stage)),
    ]
    if piece.vessel:
        facts.append(("vessel", piece.vessel))
    for label, name in (("programme", programme), ("schedule", schedule), ("curve", curve)):
        if name is not None:
            facts.append((label, name))
    weight_rows = [
        [point, f"{tonnes:.2f}", "" if moisture is None else f"{moisture:.2f}"]
        for point, (tonnes, moisture) in sorted(weights.items())
    ]
    clock_rows = []
    for stage in (PieceStage.STEEPING, PieceStage.GERMINATING, PieceStage.KILNING):
        legs = readings(book, code, stage)
        if legs:
            clock_rows.append(
                [
                    str(stage),
                    f"{elapsed_hours(legs):.1f}",
                    f"{degree_hours(legs):.0f}",
                    str(len(legs)),
                ]
            )
    return page(
        [
            heading(f"piece {code}"),
            pairs(facts),
            table_block(
                "movements",
                [Column("stage"), Column("vessel"), Column("on"), Column("note")],
                [
                    [str(stage), vessel or "", day.isoformat(), note]
                    for stage, vessel, day, note in movements(book, code)
                ],
            ),
            table_block(
                "weights",
                [Column("point"), Column("tonnes", Align.RIGHT), Column("moisture", Align.RIGHT)],
                weight_rows,
            ),
            table_block(
                "clock",
                [
                    Column("stage"),
                    Column("hours", Align.RIGHT),
                    Column("degree h", Align.RIGHT),
                    Column("legs", Align.RIGHT),
                ],
                clock_rows,
            ),
            table_block(
                "from tickets",
                [Column("ticket"), Column("tonnes", Align.RIGHT)],
                [[ticket, f"{tonnes:.2f}"] for ticket, tonnes in sources_of(book, code)],
            ),
            table_block(
                "went into",
                [Column("bin"), Column("lot")],
                [
                    [malt_bin, ", ".join(lot.code for lot in lots_from_piece(book, code))]
                    for malt_bin in bins_holding(book, code)
                ],
            ),
        ]
    )


def balance_page(book: Book, codes: tuple[str, ...] = ()) -> str:
    """Malting loss and yield for every finished piece.

    The two columns disagree on purpose and the note underneath says why: a
    wet autumn improves everybody's yield without anything being done
    better, and malting loss is the one to compare.
    """
    wanted = (
        codes
        or tuple(piece.code for piece in list_pieces(book, stage=PieceStage.BINNED))
        or tuple(piece.code for piece in list_pieces(book, stage=PieceStage.KILNED))
    )
    rows = []
    for code in wanted:
        try:
            balance = balance_of(book, code)
        except StateError:
            continue
        rows.append(
            [
                code,
                f"{balance.charge_tonnes:.2f}",
                f"{balance.malt_tonnes:.2f}",
                f"{balance.malting_loss:.2f}",
                f"{balance.yield_percent:.2f}",
                f"{balance.culm_share_of_loss:.2f}",
                f"{balance.steep_discrepancy:+.2f}",
            ]
        )
    return page(
        [
            heading("malting loss and yield"),
            table_block(
                "finished pieces",
                [
                    Column("piece"),
                    Column("barley", Align.RIGHT),
                    Column("malt", Align.RIGHT),
                    Column("loss %", Align.RIGHT),
                    Column("yield %", Align.RIGHT),
                    Column("culm share", Align.RIGHT),
                    Column("steep %", Align.RIGHT),
                ],
                rows,
            ),
            [
                "loss is dry matter and yield is not, so yield also carries both moistures.",
                f"culm share is expected around {CULM_FRACTION_OF_LOSS:.2f} of the loss.",
            ]
            if rows
            else ["no piece has been weighed at every point."],
        ]
    )
