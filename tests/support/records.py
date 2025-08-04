"""Records the tests build on.

`a_piece` writes a finished piece straight into the book, which is what
every test about bins, lots and traceability needs and none of them cares
how it got there.
"""

from __future__ import annotations

import datetime as dt

from culmbin.model.enums import MaltStyle, PieceStage
from culmbin.model.process import Piece
from culmbin.store.book import Book
from culmbin.store.pieces import add_piece

STARTED = dt.date(2025, 11, 3)


def a_piece(code: str = "2025-118", **kwargs: object) -> Piece:
    """A piece steeping in S1, with anything overridden."""
    fields: dict[str, object] = {
        "variety": "LAUR",
        "crop_year": 2025,
        "style": MaltStyle.PALE_ALE,
        "charge_tonnes": 45.0,
        "charge_moisture": 12.0,
        "started": STARTED,
        "stage": PieceStage.STEEPING,
        "vessel": "S1",
    }
    fields.update(kwargs)
    return Piece(code=code, **fields)  # type: ignore[arg-type]


def kilned(
    book: Book,
    code: str,
    variety: str = "LAUR",
    crop_year: int = 2025,
    style: MaltStyle = MaltStyle.PALE_ALE,
) -> str:
    """Write a finished piece into the book and give back its code."""
    add_piece(
        book,
        a_piece(
            code,
            variety=variety,
            crop_year=crop_year,
            style=style,
            stage=PieceStage.KILNED,
            vessel=None,
        ),
    )
    return code
