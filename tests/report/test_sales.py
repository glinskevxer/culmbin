"""The sales pages."""

from __future__ import annotations

import datetime as dt

from culmbin.model.sales import Call
from culmbin.report.sales import call_page, contract_page, diary_page
from culmbin.sales.desk import allocate, despatch, load
from culmbin.store.book import Book
from culmbin.store.contracts import add_call
from culmbin.units.season import Window

ON = dt.date(2025, 11, 20)
WEEK = Window(dt.date(2025, 11, 17), dt.date(2025, 11, 21))


def test_a_signed_contract_is_on_the_page(desk: Book) -> None:
    text = contract_page(desk)
    assert "C-2025-031" in text
    assert "BRWY" in text
    assert "2400" in text


def test_the_page_carries_three_different_tonnages(desk: Book) -> None:
    """Reporting only what has gone is how a desk sells the same malt twice."""
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    text = contract_page(desk)
    assert "gone" in text
    assert "committed" in text
    assert "left" in text


def test_a_despatched_load_moves_the_delivered_column(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 28.0, 4.5, ON)
    despatch(desk, "S-1")
    assert "28.0" in contract_page(desk)


def test_the_page_narrows_to_one_customer(desk: Book) -> None:
    text = contract_page(desk, customer="BRWY")
    assert "BRWY contract position" in text
    assert "C-2025-031" in text


def test_a_customer_with_nothing_signed_has_an_empty_page(desk: Book) -> None:
    assert "there are no signed contracts." in contract_page(desk, customer="NOBODY")


def test_the_call_page_is_empty_until_something_is_called(desk: Book) -> None:
    assert "nothing has been called off." in call_page(desk, WEEK)


def test_a_call_is_on_the_call_page(desk: Book) -> None:
    add_call(desk, Call("K-1", "C-2025-031", 200.0, WEEK, dt.date(2025, 6, 2)))
    text = call_page(desk, WEEK)
    assert "C-2025-031" in text
    assert "200" in text
    assert "2200" in text


def test_the_diary_is_empty_until_something_is_planned(desk: Book) -> None:
    assert "the diary is empty." in diary_page(desk, WEEK.start, WEEK.end)


def test_a_planned_load_is_in_the_diary(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    text = diary_page(desk, WEEK.start, WEEK.end)
    assert "S-1" in text
    assert "planned" in text
    assert "loads   1" in text


def test_a_despatched_load_is_off_the_diary(desk: Book) -> None:
    """What has gone is on the contract position and is nobody's problem here."""
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    load(desk, "S-1", 28.0, 4.2, ON)
    despatch(desk, "S-1")
    assert "the diary is empty." in diary_page(desk, WEEK.start, WEEK.end)


def test_every_page_ends_in_a_newline_and_has_no_trailing_space(desk: Book) -> None:
    allocate(desk, "S-1", "C-2025-031", "L-CLEAN", 28.0, ON)
    for text in (
        contract_page(desk),
        call_page(desk, WEEK),
        diary_page(desk, WEEK.start, WEEK.end),
    ):
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())
