"""Malt bins in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.enums import BinState, MaltStyle, PieceStage
from culmbin.model.lots import Bin
from culmbin.model.process import Piece
from culmbin.store.bins import (
    add_bin,
    bins_holding,
    clean_out,
    contents_of,
    find_bin,
    get_bin,
    issue,
    list_bins,
    receipts_of,
    receive,
    seal,
)
from culmbin.store.book import Book
from culmbin.store.pieces import add_piece

BINNED = dt.date(2025, 11, 12)


def malt_bin(code: str = "B04", **kwargs: object) -> Bin:
    fields: dict[str, object] = {"capacity_tonnes": 220.0}
    fields.update(kwargs)
    return Bin(code=code, **fields)  # type: ignore[arg-type]


def a_piece(stocked: Book, code: str, variety: str = "LAUR", crop_year: int = 2025) -> str:
    add_piece(
        stocked,
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


def test_a_bin_reads_back_the_way_it_went_in(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    assert get_bin(stocked, "B04") == malt_bin()


def test_a_bin_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="B99"):
        get_bin(stocked, "B99")
    assert find_bin(stocked, "B99") is None


def test_an_empty_bin_holds_nothing(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    assert contents_of(stocked, "B04").empty


def test_contents_of_a_bin_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        contents_of(stocked, "B99")


def test_a_receipt_puts_malt_in_and_starts_it_filling(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 37.9, 4.4, BINNED)
    assert get_bin(stocked, "B04").state is BinState.FILLING
    held = contents_of(stocked, "B04")
    assert held.tonnes == pytest.approx(37.9)
    assert held.variety == "LAUR"


def test_two_receipts_of_one_variety_leave_the_bin_clean(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    a_piece(stocked, "2025-119")
    receive(stocked, "B04", "2025-118", 37.9, 4.4, BINNED)
    receive(stocked, "B04", "2025-119", 38.2, 4.2, BINNED)
    assert not get_bin(stocked, "B04").mixed
    assert contents_of(stocked, "B04").variety == "LAUR"


def test_a_second_variety_marks_the_bin_mixed(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118", variety="LAUR")
    a_piece(stocked, "2025-120", variety="DIAB")
    receive(stocked, "B04", "2025-118", 37.9, 4.4, BINNED)
    receive(stocked, "B04", "2025-120", 38.2, 4.2, BINNED)
    assert get_bin(stocked, "B04").mixed
    assert contents_of(stocked, "B04").variety is None


def test_the_moisture_averages_over_the_wet_weight(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    a_piece(stocked, "2025-119")
    receive(stocked, "B04", "2025-118", 10.0, 4.0, BINNED)
    receive(stocked, "B04", "2025-119", 30.0, 5.0, BINNED)
    assert contents_of(stocked, "B04").moisture == pytest.approx(4.75)


def test_a_receipt_over_the_capacity_is_refused(stocked: Book) -> None:
    add_bin(stocked, malt_bin(capacity_tonnes=50.0))
    a_piece(stocked, "2025-118")
    with pytest.raises(ConflictError, match="against a capacity"):
        receive(stocked, "B04", "2025-118", 60.0, 4.4, BINNED)


def test_a_receipt_of_nothing_is_refused(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    with pytest.raises(ConflictError, match="not a receipt"):
        receive(stocked, "B04", "2025-118", 0.0, 4.4, BINNED)


def test_a_sealed_bin_takes_nothing(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    a_piece(stocked, "2025-119")
    receive(stocked, "B04", "2025-118", 37.9, 4.4, BINNED)
    seal(stocked, "B04")
    with pytest.raises(StateError, match="takes nothing"):
        receive(stocked, "B04", "2025-119", 10.0, 4.4, BINNED)


def test_only_a_filling_bin_is_sealed(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    with pytest.raises(StateError, match="only a filling bin"):
        seal(stocked, "B04")


def test_a_bin_drawn_right_down_cannot_be_sealed_again(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    seal(stocked, "B04")
    issue(stocked, "B04", 20.0, BINNED)
    with pytest.raises(StateError, match="only a filling bin"):
        seal(stocked, "B04")


def test_an_issue_takes_malt_out(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 37.9, 4.4, BINNED)
    seal(stocked, "B04")
    issue(stocked, "B04", 12.0, BINNED, note="tanker to Sheldrake")
    assert contents_of(stocked, "B04").tonnes == pytest.approx(25.9)
    assert get_bin(stocked, "B04").state is BinState.DRAWING


def test_a_bin_drawn_to_nothing_goes_empty_and_keeps_its_mark(stocked: Book) -> None:
    """Empty is the level gauge, and the mark is the boot of the bin."""
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118", variety="LAUR")
    a_piece(stocked, "2025-120", variety="DIAB")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    receive(stocked, "B04", "2025-120", 20.0, 4.4, BINNED)
    seal(stocked, "B04")
    issue(stocked, "B04", 40.0, BINNED)
    assert get_bin(stocked, "B04").state is BinState.EMPTY
    assert stocked.scalar("SELECT mixed FROM malt_bin WHERE code = 'B04'") == 1


def test_cleaning_out_takes_the_mark_off(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118", variety="LAUR")
    a_piece(stocked, "2025-120", variety="DIAB")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    receive(stocked, "B04", "2025-120", 20.0, 4.4, BINNED)
    seal(stocked, "B04")
    issue(stocked, "B04", 40.0, BINNED)
    assert not clean_out(stocked, "B04").mixed


def test_a_bin_with_malt_in_it_cannot_be_cleaned_out(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    with pytest.raises(StateError, match="cannot be cleaned out"):
        clean_out(stocked, "B04")


def test_a_filling_bin_gives_nothing(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    with pytest.raises(StateError, match="gives nothing"):
        issue(stocked, "B04", 5.0, BINNED)


def test_drawing_more_than_is_there_is_refused(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    seal(stocked, "B04")
    with pytest.raises(ConflictError, match="was asked for"):
        issue(stocked, "B04", 30.0, BINNED)


def test_an_issue_of_nothing_is_refused(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    seal(stocked, "B04")
    with pytest.raises(ConflictError, match="not an issue"):
        issue(stocked, "B04", 0.0, BINNED)


def test_the_receipts_come_back_in_order(stocked: Book) -> None:
    add_bin(stocked, malt_bin())
    a_piece(stocked, "2025-118")
    a_piece(stocked, "2025-119")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    receive(stocked, "B04", "2025-119", 15.0, 4.2, BINNED)
    assert [row[0] for row in receipts_of(stocked, "B04")] == ["2025-118", "2025-119"]


def test_a_piece_split_across_bins_is_in_both(stocked: Book) -> None:
    add_bin(stocked, malt_bin("B04"))
    add_bin(stocked, malt_bin("B05"))
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    receive(stocked, "B05", "2025-118", 17.9, 4.4, BINNED)
    assert bins_holding(stocked, "2025-118") == ("B04", "B05")


def test_a_piece_that_has_gone_nowhere_is_in_nothing(stocked: Book) -> None:
    a_piece(stocked, "2025-118")
    assert bins_holding(stocked, "2025-118") == ()


def test_the_listing_narrows_by_state(stocked: Book) -> None:
    add_bin(stocked, malt_bin("B04"))
    add_bin(stocked, malt_bin("B05"))
    a_piece(stocked, "2025-118")
    receive(stocked, "B04", "2025-118", 20.0, 4.4, BINNED)
    assert [item.code for item in list_bins(stocked)] == ["B04", "B05"]
    filling = list_bins(stocked, BinState.FILLING)
    assert [item.code for item in filling] == ["B04"]
