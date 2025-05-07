"""Gradings in the book."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError
from culmbin.intake.grading import Adjustment, Grading
from culmbin.model.enums import IntakeOutcome, Material, RejectionReason
from culmbin.model.intake import Delivery
from culmbin.model.results import Result, analysis_of
from culmbin.store.analyses import save_analysis
from culmbin.store.book import Book
from culmbin.store.deliveries import add_delivery, attach_sample
from culmbin.store.gradings import (
    deduction_total,
    find_grading,
    get_grading,
    graded_on,
    list_gradings,
    regrade,
    rejected_count,
    save_grading,
    ungraded,
    void_grading,
)

ARRIVED = dt.date(2025, 9, 18)
GRADED = dt.date(2025, 9, 19)


def tip(book: Book, ticket: str = "W-24188", sampled: bool = True) -> str:
    """Put a lorry through the weighbridge and, by default, sample it."""
    add_delivery(
        book,
        Delivery(
            ticket=ticket,
            purchase="P-2025-014",
            party="HOLB",
            arrived=ARRIVED,
            gross_kg=43_820.0,
            tare_kg=15_640.0,
        ),
    )
    if sampled:
        reference = f"B-{ticket}"
        save_analysis(
            book, analysis_of(reference, Material.BARLEY, ARRIVED, [Result("moisture", 12.4)])
        )
        attach_sample(book, ticket, reference)
    return ticket


def accepted(ticket: str = "W-24188", **kwargs: object) -> Grading:
    fields: dict[str, object] = {
        "standard": "malting 2025",
        "outcome": IntakeOutcome.ACCEPTED,
        "net_tonnes": 28.18,
        "settled_tonnes": 28.18,
    }
    fields.update(kwargs)
    return Grading(ticket=ticket, **fields)  # type: ignore[arg-type]


def deducted(ticket: str = "W-24188") -> Grading:
    return Grading(
        ticket=ticket,
        standard="malting 2025",
        outcome=IntakeOutcome.ACCEPTED_ON_DEDUCTION,
        net_tonnes=28.18,
        settled_tonnes=27.5,
        adjustments=(
            Adjustment(kind="screenings", note="screenings 3.4 over 2.0", tonnes=0.394),
            Adjustment(kind="drying", note="drying 2.5 points", per_tonne=Decimal("6.00")),
        ),
    )


def rejected(ticket: str = "W-24188") -> Grading:
    return Grading(
        ticket=ticket,
        standard="malting 2025",
        outcome=IntakeOutcome.REJECTED,
        net_tonnes=28.18,
        settled_tonnes=0.0,
        rejections=(RejectionReason.GERMINATION, RejectionReason.MOISTURE),
    )


def test_a_grading_reads_back_the_way_it_went_in(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, accepted(), GRADED)
    assert get_grading(stocked, "W-24188") == accepted()


def test_the_adjustments_come_back_in_the_order_they_were_worked(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, deducted(), GRADED)
    read = get_grading(stocked, "W-24188")
    assert [line.kind for line in read.adjustments] == ["screenings", "drying"]
    assert read.adjustments[1].per_tonne == Decimal("6.00")


def test_the_rejections_come_back_in_the_order_of_the_enumeration(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, rejected(), GRADED)
    assert get_grading(stocked, "W-24188").rejections == (
        RejectionReason.GERMINATION,
        RejectionReason.MOISTURE,
    )


def test_a_rejected_grading_reads_back_as_rejected(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, rejected(), GRADED)
    read = get_grading(stocked, "W-24188")
    assert read.rejected
    assert read.settled_tonnes == 0.0
    assert read.adjustments == ()


def test_the_day_it_was_graded_is_kept_separately(stocked: Book) -> None:
    """A load tipped on Friday afternoon is graded on Monday."""
    tip(stocked)
    save_grading(stocked, accepted(), GRADED)
    assert graded_on(stocked, "W-24188") == GRADED
    assert graded_on(stocked, "W-24188") != ARRIVED


def test_a_grading_that_is_not_there_says_which_ticket(stocked: Book) -> None:
    with pytest.raises(NotFoundError, match="has not been graded"):
        get_grading(stocked, "W-99999")
    with pytest.raises(NotFoundError):
        graded_on(stocked, "W-99999")


def test_finding_treats_absence_as_an_answer(stocked: Book) -> None:
    assert find_grading(stocked, "W-99999") is None


def test_grading_a_load_twice_is_refused(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, accepted(), GRADED)
    with pytest.raises(ConflictError):
        save_grading(stocked, deducted(), GRADED)


def test_grading_a_load_that_is_not_there_is_refused(stocked: Book) -> None:
    with pytest.raises(ConflictError, match="does not hold"):
        save_grading(stocked, accepted("W-99999"), GRADED)


def test_voiding_puts_the_load_back_where_it_was(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, deducted(), GRADED)
    void_grading(stocked, "W-24188")
    assert find_grading(stocked, "W-24188") is None
    assert ungraded(stocked) == ("W-24188",)


def test_voiding_takes_the_lines_and_the_reasons_with_it(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, rejected(), GRADED)
    void_grading(stocked, "W-24188")
    assert stocked.scalar("SELECT count(*) FROM rejection") == 0
    assert stocked.scalar("SELECT count(*) FROM adjustment") == 0


def test_voiding_something_that_is_not_graded_is_refused(stocked: Book) -> None:
    with pytest.raises(NotFoundError):
        void_grading(stocked, "W-99999")


def test_regrading_replaces_one_with_another(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, rejected(), GRADED)
    regrade(stocked, accepted(), dt.date(2025, 9, 22))
    read = get_grading(stocked, "W-24188")
    assert read.outcome is IntakeOutcome.ACCEPTED
    assert read.rejections == ()
    assert graded_on(stocked, "W-24188") == dt.date(2025, 9, 22)


def test_a_failed_regrade_leaves_the_first_one_standing(stocked: Book) -> None:
    """Both halves are one transaction, so a load is never left with no grading."""
    tip(stocked)
    save_grading(stocked, rejected(), GRADED)
    on_a_standard_nobody_wrote_down = accepted(standard="malting 2024")
    with pytest.raises(ConflictError):
        regrade(stocked, on_a_standard_nobody_wrote_down, GRADED)
    assert get_grading(stocked, "W-24188").rejected


def test_a_sampled_ungraded_load_is_on_the_list(stocked: Book) -> None:
    tip(stocked, "W-1")
    assert ungraded(stocked) == ("W-1",)


def test_an_unsampled_load_is_not_on_the_ungraded_list(stocked: Book) -> None:
    """It is a different queue: nobody has taken a sample off it yet."""
    tip(stocked, "W-1", sampled=False)
    assert ungraded(stocked) == ()


def test_the_ungraded_list_can_stop_at_a_day(stocked: Book) -> None:
    tip(stocked, "W-1")
    assert ungraded(stocked, until=dt.date(2025, 9, 1)) == ()
    assert ungraded(stocked, until=dt.date(2025, 9, 30)) == ("W-1",)


def test_the_listing_narrows_by_outcome_and_by_day(stocked: Book) -> None:
    tip(stocked, "W-1")
    tip(stocked, "W-2")
    save_grading(stocked, accepted("W-1"), dt.date(2025, 9, 19))
    save_grading(stocked, rejected("W-2"), dt.date(2025, 9, 25))
    assert [item.ticket for item in list_gradings(stocked)] == ["W-1", "W-2"]
    only = list_gradings(stocked, outcome=IntakeOutcome.REJECTED)
    assert [item.ticket for item in only] == ["W-2"]
    narrowed = list_gradings(stocked, since=dt.date(2025, 9, 22))
    assert [item.ticket for item in narrowed] == ["W-2"]


def test_the_rejected_count_is_what_went_back(stocked: Book) -> None:
    tip(stocked, "W-1")
    tip(stocked, "W-2")
    save_grading(stocked, accepted("W-1"), dt.date(2025, 9, 19))
    save_grading(stocked, rejected("W-2"), dt.date(2025, 9, 25))
    assert rejected_count(stocked) == 1
    assert rejected_count(stocked, since=dt.date(2025, 9, 26)) == 0


def test_the_deduction_total_adds_the_price_lines(stocked: Book) -> None:
    tip(stocked)
    save_grading(stocked, deducted(), GRADED)
    assert deduction_total(stocked, "W-24188") == Decimal("6.00")


def test_an_empty_book_has_nothing_graded(stocked: Book) -> None:
    assert list_gradings(stocked) == ()
    assert rejected_count(stocked) == 0
