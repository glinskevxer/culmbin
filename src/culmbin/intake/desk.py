"""The intake desk: everything that happens to a lorry, in order.

The functions below are the only ones anything outside `intake` calls. They
are what turn four registers, a standard, an analysis and a weighbridge
ticket into a settled tonnage, and they are where the checks that need more
than one of those live.

The checks are worth listing, because none of them belongs to any single
record and every one of them has been got wrong somewhere.

- A lorry is against a purchase, and the purchase names a grower. A load
  delivered by somebody else is a load against the wrong contract.
- A delivery outside the window is not a delivery against that contract. It
  can still be taken in, but somebody has to extend the window first, and
  that is a decision rather than a keystroke.
- The variety has to be on the approved list *on the day the lorry tipped*.
  A variety withdrawn in June does not serve a contract in September, and
  the load is worth barley money instead.
- A load cannot be graded until we know when it was cut, because that is
  what decides whether the new crop rejections apply.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import ConflictError, StateError
from culmbin.intake.grading import Grading, grade
from culmbin.intake.settlement import Settlement, settle_or_none
from culmbin.model.enums import Material, RejectionReason
from culmbin.model.intake import Delivery
from culmbin.model.results import Analysis
from culmbin.store.analyses import get_analysis, save_analysis
from culmbin.store.book import Book
from culmbin.store.deliveries import add_delivery, attach_sample, get_delivery, list_deliveries
from culmbin.store.gradings import find_grading, get_grading, save_grading
from culmbin.store.parties import get_party
from culmbin.store.purchases import get_purchase
from culmbin.store.standards import get_standard
from culmbin.store.varieties import get_variety
from culmbin.units.season import Window


@dataclass(frozen=True, slots=True)
class IntakeSummary:
    """What came in over a stretch of days."""

    window: Window
    loads: int
    rejected: int
    net_tonnes: float
    settled_tonnes: float

    @property
    def shrinkage_tonnes(self) -> float:
        """The difference between what arrived and what is paid for."""
        return self.net_tonnes - self.settled_tonnes

    @property
    def rejection_rate(self) -> float:
        """Rejected loads as a percentage of everything that was graded."""
        return 0.0 if self.loads == 0 else self.rejected / self.loads * 100.0


def weigh_in(book: Book, delivery: Delivery) -> Delivery:
    """Take a lorry in against a purchase, with everything checked first."""
    purchase = get_purchase(book, delivery.purchase)
    if delivery.party != purchase.party:
        raise ConflictError(
            f"{purchase.code} is with {purchase.party} "
            f"and ticket {delivery.ticket} says {delivery.party}"
        )
    party = get_party(book, delivery.party)
    if not party.trading_on(delivery.arrived):
        raise ConflictError(f"{party} was not trading on {delivery.arrived}")
    if not purchase.takes_delivery_on(delivery.arrived):
        raise ConflictError(
            f"{purchase.code} runs {purchase.window} "
            f"and ticket {delivery.ticket} arrived {delivery.arrived}"
        )
    variety = get_variety(book, purchase.variety)
    if not variety.on_the_list_on(delivery.arrived):
        raise ConflictError(f"{variety.name} was not on the approved list on {delivery.arrived}")
    return add_delivery(book, delivery)


def take_sample(book: Book, ticket: str, analysis: Analysis, note: str = "") -> Delivery:
    """Put a barley analysis against a load, in one transaction."""
    if analysis.material is not Material.BARLEY:
        raise ConflictError(f"{analysis.reference} is a {analysis.material} analysis")
    with book.writing():
        save_analysis(book, analysis, note)
        return attach_sample(book, ticket, analysis.reference)


def grade_load(
    book: Book,
    ticket: str,
    on: dt.date,
    findings: frozenset[RejectionReason] = frozenset(),
) -> Grading:
    """Screen and grade a sampled load, and write the answer down."""
    delivery = get_delivery(book, ticket)
    if not delivery.sampled:
        raise StateError(f"ticket {ticket} has not been sampled")
    if not delivery.dated:
        raise StateError(
            f"ticket {ticket} has no harvest date, so nothing can say whether it is new crop"
        )
    if find_grading(book, ticket) is not None:
        raise ConflictError(f"ticket {ticket} has already been graded")
    assert delivery.sample is not None
    assert delivery.harvested is not None
    purchase = get_purchase(book, delivery.purchase)
    standard = get_standard(book, purchase.standard)
    analysis = get_analysis(book, delivery.sample)
    grading = grade(
        ticket=ticket,
        standard=standard,
        net_tonnes=delivery.net_tonnes,
        analysis=analysis,
        harvested=delivery.harvested,
        arrived=delivery.arrived,
        findings=findings,
    )
    return save_grading(book, grading, on)


def settle_load(book: Book, ticket: str) -> Settlement | None:
    """What a graded load is worth, or nothing if it was rejected."""
    delivery = get_delivery(book, ticket)
    grading = get_grading(book, ticket)
    purchase = get_purchase(book, delivery.purchase)
    return settle_or_none(grading, purchase)


def statement_for(book: Book, party: str, window: Window) -> tuple[Settlement, ...]:
    """Every settled load for one grower over a stretch of days.

    Rejected loads are not on it at all, and loads that have not been graded
    yet are not on it either. Both of those are queues somewhere else.
    """
    settlements = []
    for delivery in list_deliveries(book, party=party, since=window.start, until=window.end):
        if find_grading(book, delivery.ticket) is None:
            continue
        settlement = settle_load(book, delivery.ticket)
        if settlement is not None:
            settlements.append(settlement)
    return tuple(settlements)


def summarise(book: Book, window: Window) -> IntakeSummary:
    """What came in over a stretch of days, counted off the gradings."""
    loads = 0
    rejected = 0
    net = 0.0
    settled = 0.0
    for delivery in list_deliveries(book, since=window.start, until=window.end):
        grading = find_grading(book, delivery.ticket)
        if grading is None:
            continue
        loads += 1
        net += grading.net_tonnes
        settled += grading.settled_tonnes
        if grading.rejected:
            rejected += 1
    return IntakeSummary(
        window=window,
        loads=loads,
        rejected=rejected,
        net_tonnes=net,
        settled_tonnes=settled,
    )
