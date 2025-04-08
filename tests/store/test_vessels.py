"""The vessel register in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import VesselKind
from culmbin.model.plant import Vessel
from culmbin.store.book import Book
from culmbin.store.vessels import (
    add_vessel,
    find_vessel,
    get_vessel,
    list_vessels,
    retire_vessel,
    update_vessel,
)

COMMISSIONED = dt.date(1998, 4, 1)


def steep(code: str = "S1") -> Vessel:
    return Vessel(code, f"steep {code}", VesselKind.STEEP, COMMISSIONED, charge_limit_t=45.0)


def box(code: str = "G1") -> Vessel:
    return Vessel(
        code,
        f"box {code}",
        VesselKind.BOX,
        COMMISSIONED,
        floor_area_m2=120.0,
        depth_limit_cm=90.0,
    )


def test_a_steep_reads_back_the_way_it_went_in(book: Book) -> None:
    add_vessel(book, steep())
    assert get_vessel(book, "S1") == steep()


def test_a_box_reads_back_with_its_area_and_depth(book: Book) -> None:
    add_vessel(book, box())
    read = get_vessel(book, "G1")
    assert read == box()
    assert read.charge_limit_t is None
    assert read.limit_t > 0.0


def test_a_vessel_that_is_not_there_says_which_one(book: Book) -> None:
    with pytest.raises(NotFoundError, match="S9"):
        get_vessel(book, "S9")


def test_finding_treats_absence_as_an_answer(book: Book) -> None:
    assert find_vessel(book, "S1") is None


def test_adding_the_same_code_twice_is_refused(book: Book) -> None:
    add_vessel(book, steep())
    with pytest.raises(ConflictError):
        add_vessel(book, steep())


def test_updating_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        update_vessel(book, steep())


def test_the_plant_comes_back_in_code_order(book: Book) -> None:
    add_vessel(book, steep("S2"))
    add_vessel(book, box("G1"))
    add_vessel(book, steep("S1"))
    assert [vessel.code for vessel in list_vessels(book)] == ["G1", "S1", "S2"]


def test_the_plant_filters_by_kind(book: Book) -> None:
    add_vessel(book, steep("S1"))
    add_vessel(book, box("G1"))
    codes = [vessel.code for vessel in list_vessels(book, VesselKind.BOX)]
    assert codes == ["G1"]


def test_retiring_takes_it_out_of_service(book: Book) -> None:
    add_vessel(book, steep())
    retire_vessel(book, "S1", dt.date(2024, 6, 1))
    vessel = get_vessel(book, "S1")
    assert not vessel.in_service_on(dt.date(2024, 6, 1))
    assert vessel.in_service_on(dt.date(2024, 5, 31))


def test_retiring_twice_is_refused(book: Book) -> None:
    add_vessel(book, steep())
    retire_vessel(book, "S1", dt.date(2024, 6, 1))
    with pytest.raises(ConflictError, match="already retired"):
        retire_vessel(book, "S1", dt.date(2024, 7, 1))


def test_retiring_something_that_is_not_there_is_refused(book: Book) -> None:
    with pytest.raises(NotFoundError):
        retire_vessel(book, "S1", dt.date(2024, 6, 1))


def test_a_plant_read_back_answers_the_same_questions(book: Book) -> None:
    """The record's arithmetic survives the round trip through the book."""
    add_vessel(book, box("G1"))
    read = list_vessels(book)["G1"]
    assert read.tonnes_at_depth(60.0) == box().tonnes_at_depth(60.0)
