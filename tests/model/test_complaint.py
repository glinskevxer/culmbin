"""Customer complaints, and what came of them."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import StateError, ValidationError
from culmbin.model.complaint import ABOUT_THE_MALT, CLOSED_STATES, Complaint
from culmbin.model.enums import ComplaintKind, ComplaintState

RAISED = dt.date(2026, 1, 14)
CLOSED = dt.date(2026, 1, 28)


def complaint(code: str = "Q-2026-004", **kwargs: object) -> Complaint:
    fields: dict[str, object] = {
        "customer": "BRWY",
        "kind": ComplaintKind.COLOUR,
        "raised": RAISED,
        "summary": "wort came out two EBC darker than the certificate",
    }
    fields.update(kwargs)
    return Complaint(code=code, **fields)  # type: ignore[arg-type]


def test_a_complaint_prints_who_and_what() -> None:
    assert str(complaint()) == "Q-2026-004 BRWY colour (open)"
    assert "against S-1" in str(complaint(shipment="S-1"))


def test_a_complaint_needs_a_code_and_something_to_say() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        complaint(" ")
    with pytest.raises(ValidationError, match="says nothing"):
        complaint(summary="   ")


def test_a_new_complaint_is_open() -> None:
    assert complaint().open
    assert complaint().closed is None


def test_a_closed_complaint_needs_a_date() -> None:
    with pytest.raises(ValidationError, match="does not agree"):
        complaint(state=ComplaintState.UPHELD)


def test_an_open_complaint_must_not_have_one() -> None:
    with pytest.raises(ValidationError, match="does not agree"):
        complaint(closed=CLOSED)


def test_a_complaint_closed_before_it_was_raised_is_refused() -> None:
    with pytest.raises(ValidationError, match="closed before it was raised"):
        complaint(state=ComplaintState.UPHELD, closed=dt.date(2026, 1, 1))


def test_the_three_ways_of_closing_are_all_closed() -> None:
    assert {
        ComplaintState.UPHELD,
        ComplaintState.REJECTED,
        ComplaintState.WITHDRAWN,
    } == CLOSED_STATES


def test_a_complaint_about_the_malt_says_so() -> None:
    assert complaint().about_the_malt
    assert not complaint(kind=ComplaintKind.LATE).about_the_malt
    assert ComplaintKind.CONTAMINATION in ABOUT_THE_MALT


def test_a_complaint_with_no_shipment_cannot_be_walked_back() -> None:
    """A customer ringing about the malt sent in March has not given one."""
    assert not complaint().traceable
    assert complaint(shipment="S-1").traceable


def test_attaching_a_shipment_makes_it_traceable() -> None:
    assert complaint().attached_to("S-1").traceable


def test_a_shipment_cannot_be_moved_once_attached() -> None:
    """A walk done against the wrong malt should leave a record that it was."""
    with pytest.raises(StateError, match="already against S-1"):
        complaint(shipment="S-1").attached_to("S-2")


def test_closing_records_what_was_found() -> None:
    closed = complaint().closed_as(ComplaintState.UPHELD, CLOSED, "kiln ran hot on the cure")
    assert not closed.open
    assert closed.closed == CLOSED
    assert "kiln ran hot" in closed.finding


def test_closing_without_a_finding_is_refused() -> None:
    with pytest.raises(StateError, match="nothing says what was found"):
        complaint().closed_as(ComplaintState.UPHELD, CLOSED, "  ")


def test_a_closed_complaint_does_not_close_again() -> None:
    closed = complaint().closed_as(ComplaintState.REJECTED, CLOSED, "the retest agreed with us")
    with pytest.raises(StateError, match="was closed as rejected"):
        closed.closed_as(ComplaintState.UPHELD, CLOSED, "changed our minds")


def test_investigating_is_not_a_way_of_closing() -> None:
    with pytest.raises(StateError, match="not a way of closing"):
        complaint().closed_as(ComplaintState.INVESTIGATING, CLOSED, "still looking")


def test_an_open_complaint_counts_days_to_today() -> None:
    assert complaint().days_open(dt.date(2026, 1, 20)) == 6


def test_a_closed_complaint_counts_days_to_when_it_closed() -> None:
    closed = complaint().closed_as(ComplaintState.UPHELD, CLOSED, "kiln ran hot")
    assert closed.days_open(dt.date(2026, 3, 1)) == 14


def test_a_complaint_raised_today_is_no_days_old() -> None:
    assert complaint().days_open(RAISED) == 0


def test_a_date_before_it_was_raised_does_not_go_negative() -> None:
    assert complaint().days_open(dt.date(2026, 1, 1)) == 0
