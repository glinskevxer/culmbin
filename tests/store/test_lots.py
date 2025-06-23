"""Lots in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import MaltStyle, Material, PieceStage
from culmbin.model.lots import Bin
from culmbin.model.process import Piece
from culmbin.model.results import Result, analysis_of
from culmbin.store.analyses import save_analysis
from culmbin.store.bins import add_bin, issue, receive, seal
from culmbin.store.book import Book
from culmbin.store.lots import (
    certify,
    find_lot,
    get_lot,
    list_lots,
    lots_from_piece,
    seal_lot,
    uncertified,
)
from culmbin.store.pieces import add_piece

BINNED = dt.date(2025, 11, 12)
SEALED = dt.date(2025, 11, 13)


def a_piece(book: Book, code: str, variety: str = "LAUR", crop_year: int = 2025) -> str:
    add_piece(
        book,
        Piece(
            code=code,
            variety=variety,
            crop_year=crop_year,
            style=MaltStyle.PALE_ALE,
            charge_tonnes=45.0,
            charge_moisture=12.0,
            started=dt.date(2025, 11, 3),
            stage=PieceStage.KILNED,
            vessel=None,
        ),
    )
    return code


def one_variety(book: Book) -> str:
    a_piece(book, "2025-118")
    a_piece(book, "2025-119")
    add_bin(book, Bin("B04", 220.0))
    receive(book, "B04", "2025-118", 30.0, 4.4, BINNED)
    receive(book, "B04", "2025-119", 30.0, 4.2, BINNED)
    seal(book, "B04")
    return "B04"


def two_varieties(book: Book) -> str:
    a_piece(book, "2025-121", variety="LAUR")
    a_piece(book, "2025-120", variety="DIAB")
    add_bin(book, Bin("B05", 220.0))
    receive(book, "B05", "2025-121", 30.0, 4.4, BINNED)
    receive(book, "B05", "2025-120", 30.0, 4.2, BINNED)
    seal(book, "B05")
    return "B05"


def test_a_lot_takes_everything_off_the_bin(stocked: Book) -> None:
    one_variety(stocked)
    lot = seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    assert lot.tonnes == pytest.approx(60.0)
    assert lot.variety == "LAUR"
    assert lot.crop_years == frozenset({2025})
    assert lot.parents == ("2025-118", "2025-119")
    assert lot.style is MaltStyle.PALE_ALE


def test_a_lot_reads_back_the_way_it_was_sealed(stocked: Book) -> None:
    one_variety(stocked)
    sealed = seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    assert get_lot(stocked, "L-2025-0412") == sealed


def test_a_lot_out_of_a_mixed_bin_declares_nothing(stocked: Book) -> None:
    two_varieties(stocked)
    lot = seal_lot(stocked, "L-2025-0413", "B05", SEALED)
    assert not lot.declares_variety
    assert lot.varieties == frozenset({"LAUR", "DIAB"})


def test_a_lot_does_not_move_when_the_bin_does(stocked: Book) -> None:
    """The certificate says what it says, and the bin carries on emptying."""
    one_variety(stocked)
    lot = seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    issue(stocked, "B04", 25.0, dt.date(2025, 11, 20))
    assert get_lot(stocked, "L-2025-0412").tonnes == pytest.approx(lot.tonnes)


def test_a_lot_off_a_filling_bin_is_refused(stocked: Book) -> None:
    a_piece(stocked, "2025-118")
    add_bin(stocked, Bin("B04", 220.0))
    receive(stocked, "B04", "2025-118", 30.0, 4.4, BINNED)
    with pytest.raises(StateError, match="comes off a sealed bin"):
        seal_lot(stocked, "L-1", "B04", SEALED)


def test_a_lot_off_an_empty_bin_is_refused(stocked: Book) -> None:
    add_bin(stocked, Bin("B04", 220.0))
    with pytest.raises(StateError, match="comes off a sealed bin"):
        seal_lot(stocked, "L-1", "B04", SEALED)


def test_two_lots_with_one_code_are_refused(stocked: Book) -> None:
    one_variety(stocked)
    seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    with pytest.raises(ConflictError):
        seal_lot(stocked, "L-2025-0412", "B04", SEALED)


def test_a_lot_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="L-9"):
        get_lot(stocked, "L-9")
    assert find_lot(stocked, "L-9") is None


def test_a_lot_starts_uncertified(stocked: Book) -> None:
    one_variety(stocked)
    lot = seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    assert not lot.certified
    assert [item.code for item in uncertified(stocked)] == ["L-2025-0412"]


def test_certifying_puts_the_analysis_on(stocked: Book) -> None:
    one_variety(stocked)
    seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    save_analysis(
        stocked, analysis_of("M-1", Material.MALT, SEALED, [Result("malt_moisture", 4.3)])
    )
    lot = certify(stocked, "L-2025-0412", "M-1")
    assert lot.certified
    assert uncertified(stocked) == ()


def test_a_lot_cannot_be_certified_twice(stocked: Book) -> None:
    """A retest gets its own certificate rather than replacing the numbers sent."""
    one_variety(stocked)
    seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    for reference in ("M-1", "M-2"):
        save_analysis(
            stocked,
            analysis_of(reference, Material.MALT, SEALED, [Result("malt_moisture", 4.3)]),
        )
    certify(stocked, "L-2025-0412", "M-1")
    with pytest.raises(ConflictError, match="already certified"):
        certify(stocked, "L-2025-0412", "M-2")


def test_certifying_with_an_analysis_that_is_not_there_is_refused(stocked: Book) -> None:
    one_variety(stocked)
    seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    with pytest.raises(ConflictError, match="does not hold"):
        certify(stocked, "L-2025-0412", "M-NOTHING")


def test_the_listing_by_variety_leaves_out_a_mixed_lot(stocked: Book) -> None:
    """A mixed lot containing Laureate is not a Laureate lot."""
    one_variety(stocked)
    two_varieties(stocked)
    seal_lot(stocked, "L-CLEAN", "B04", SEALED)
    seal_lot(stocked, "L-MIXED", "B05", SEALED)
    assert [item.code for item in list_lots(stocked, variety="LAUR")] == ["L-CLEAN"]
    assert len(list_lots(stocked)) == 2


def test_the_listing_narrows_by_style_and_by_certificate(stocked: Book) -> None:
    one_variety(stocked)
    seal_lot(stocked, "L-1", "B04", SEALED)
    assert [item.code for item in list_lots(stocked, style=MaltStyle.PALE_ALE)] == ["L-1"]
    assert list_lots(stocked, style=MaltStyle.LAGER) == ()
    assert [item.code for item in list_lots(stocked, certified=False)] == ["L-1"]
    assert list_lots(stocked, certified=True) == ()


def test_a_piece_says_which_lots_it_ended_up_in(stocked: Book) -> None:
    one_variety(stocked)
    seal_lot(stocked, "L-2025-0412", "B04", SEALED)
    assert [item.code for item in lots_from_piece(stocked, "2025-118")] == ["L-2025-0412"]


def test_a_piece_that_went_nowhere_is_in_no_lot(stocked: Book) -> None:
    a_piece(stocked, "2025-130")
    assert lots_from_piece(stocked, "2025-130") == ()


def test_an_empty_book_has_no_lots(stocked: Book) -> None:
    assert list_lots(stocked) == ()
    assert uncertified(stocked) == ()
