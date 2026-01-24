"""Customer complaints in the book."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.model.complaint import Complaint
from culmbin.model.enums import ComplaintKind, ComplaintState
from culmbin.store.book import Book
from culmbin.store.complaints import (
    attach,
    close,
    count_by_kind,
    find_complaint,
    get_complaint,
    investigate,
    list_complaints,
    open_complaints,
    raise_complaint,
    untraceable,
)

RAISED = dt.date(2026, 1, 14)
CLOSED = dt.date(2026, 1, 28)


def complaint(code: str = "Q-1", **kwargs: object) -> Complaint:
    fields: dict[str, object] = {
        "customer": "BRWY",
        "kind": ComplaintKind.COLOUR,
        "raised": RAISED,
        "summary": "wort came out two EBC darker than the certificate",
    }
    fields.update(kwargs)
    return Complaint(code=code, **fields)  # type: ignore[arg-type]


def test_a_complaint_reads_back_the_way_it_went_in(stocked: Book) -> None:
    raise_complaint(stocked, complaint())
    assert get_complaint(stocked, "Q-1") == complaint()


def test_a_complaint_that_is_not_there_says_which_one(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="Q-9"):
        get_complaint(stocked, "Q-9")
    assert find_complaint(stocked, "Q-9") is None


def test_a_complaint_from_somebody_not_in_the_register_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        raise_complaint(stocked, complaint(customer="NOBODY"))


def test_a_new_complaint_is_on_the_open_list(stocked: Book) -> None:
    raise_complaint(stocked, complaint())
    assert [item.code for item in open_complaints(stocked)] == ["Q-1"]


def test_investigating_keeps_it_open(stocked: Book) -> None:
    raise_complaint(stocked, complaint())
    assert investigate(stocked, "Q-1").state is ComplaintState.INVESTIGATING
    assert len(open_complaints(stocked)) == 1


def test_closing_takes_it_off_the_open_list(stocked: Book) -> None:
    raise_complaint(stocked, complaint())
    close(stocked, "Q-1", ComplaintState.UPHELD, CLOSED, "kiln ran hot on the cure")
    assert open_complaints(stocked) == ()
    assert get_complaint(stocked, "Q-1").finding.startswith("kiln ran hot")


def test_closing_twice_is_refused(stocked: Book) -> None:
    raise_complaint(stocked, complaint())
    close(stocked, "Q-1", ComplaintState.REJECTED, CLOSED, "the retest agreed with us")
    with pytest.raises(StateError, match="was closed as rejected"):
        close(stocked, "Q-1", ComplaintState.UPHELD, CLOSED, "changed our minds")


def test_a_complaint_about_the_malt_with_no_shipment_is_untraceable(stocked: Book) -> None:
    """Counting complaints without counting these counts the easy ones."""
    raise_complaint(stocked, complaint())
    assert [item.code for item in untraceable(stocked)] == ["Q-1"]


def test_a_complaint_about_paperwork_is_not_untraceable(stocked: Book) -> None:
    raise_complaint(stocked, complaint(kind=ComplaintKind.PAPERWORK))
    assert untraceable(stocked) == ()


def test_attaching_a_shipment_makes_it_traceable(stocked: Book) -> None:
    stocked.execute(
        "INSERT INTO malt_bin (code, capacity_tonnes, state) VALUES ('B04', 220.0, 'sealed')"
    )
    stocked.execute(
        "INSERT INTO malt_lot (code, malt_bin, sealed, tonnes, moisture) "
        "VALUES ('L-1', 'B04', '2025-11-12', 200.0, 4.3)"
    )
    stocked.execute(
        "INSERT INTO contract (code, customer, specification, tonnes, moisture, "
        "price_per_tonne, window_start, window_end, signed, state) VALUES "
        "('C-1', 'BRWY', 'lager 2025', 2400.0, 4.5, '398.00', '2025-10-01', "
        "'2026-09-30', '2025-06-02', 'signed')"
    )
    stocked.execute(
        "INSERT INTO shipment (code, contract, lot, tonnes, moisture, despatched, state) "
        "VALUES ('S-1', 'C-1', 'L-1', 28.0, 4.2, '2025-11-20', 'despatched')"
    )
    raise_complaint(stocked, complaint())
    attach(stocked, "Q-1", "S-1")
    assert untraceable(stocked) == ()
    assert get_complaint(stocked, "Q-1").traceable


def test_a_shipment_cannot_be_moved_once_attached(stocked: Book) -> None:
    """A walk done against the wrong malt should leave a record that it was."""
    with pytest.raises(StateError, match="already against S-1"):
        complaint(shipment="S-1").attached_to("S-2")


def test_the_listing_narrows_five_ways(stocked: Book) -> None:
    raise_complaint(stocked, complaint("Q-1"))
    raise_complaint(stocked, complaint("Q-2", kind=ComplaintKind.LATE, raised=dt.date(2026, 2, 3)))
    assert [item.code for item in list_complaints(stocked)] == ["Q-1", "Q-2"]
    late = list_complaints(stocked, kind=ComplaintKind.LATE)
    assert [item.code for item in late] == ["Q-2"]
    assert len(list_complaints(stocked, customer="BRWY")) == 2
    assert len(list_complaints(stocked, since=dt.date(2026, 2, 1))) == 1
    assert len(list_complaints(stocked, until=dt.date(2026, 1, 31))) == 1


def test_the_counts_carry_the_kinds_with_none(stocked: Book) -> None:
    """A kind with none is a fact, and a kind missing is a question nobody asked."""
    raise_complaint(stocked, complaint())
    counts = count_by_kind(stocked)
    assert counts[ComplaintKind.COLOUR] == 1
    assert counts[ComplaintKind.EXTRACT] == 0
    assert set(counts) == set(ComplaintKind)


def test_the_counts_can_stop_at_a_day(stocked: Book) -> None:
    raise_complaint(stocked, complaint("Q-1"))
    counts = count_by_kind(stocked, since=dt.date(2026, 2, 1))
    assert sum(counts.values()) == 0


def test_an_empty_book_has_no_complaints(stocked: Book) -> None:
    assert list_complaints(stocked) == ()
    assert open_complaints(stocked) == ()
    assert untraceable(stocked) == ()
