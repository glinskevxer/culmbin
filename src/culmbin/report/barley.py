"""How the barley is grading, by grower and by month.

The page is a comparison and it is laid out as one. Every column is a mean
over accepted loads only, because a rejected load has no settled weight and
including it would drag a grower's nitrogen down with a load nobody paid for.

The rejection rate is the column to read first, and it is the last column on
purpose: a grower whose nitrogen is a shade high and who has never had a load
turned away is a better grower than one with tidy numbers and three
rejections, and putting the rate first invites the opposite conclusion.

Everything is weighted by settled tonnes rather than by load, because a
twenty eight tonne lorry and a fourteen tonne one are not the same evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.model.enums import Basis
from culmbin.report.layout import Align, Column, heading, page, table_block
from culmbin.store.analyses import get_analysis
from culmbin.store.book import Book
from culmbin.store.deliveries import list_deliveries
from culmbin.store.gradings import find_grading
from culmbin.store.parties import list_parties
from culmbin.units.season import Window

TRENDED = ("moisture", "nitrogen", "screenings", "germ_capacity")


@dataclass(frozen=True, slots=True)
class Trend:
    """How one grower's barley graded over a stretch of days."""

    party: str
    loads: int
    rejected: int
    settled_tonnes: float
    means: dict[str, float]

    @property
    def rejection_rate(self) -> float:
        """Rejected loads as a percentage of everything graded."""
        return 0.0 if self.loads == 0 else self.rejected / self.loads * 100.0


def trend_for(book: Book, party: str, window: Window) -> Trend:
    """One grower's barley over a stretch of days, weighted by settled tonnes."""
    loads = 0
    rejected = 0
    settled = 0.0
    totals = dict.fromkeys(TRENDED, 0.0)
    for delivery in list_deliveries(book, party=party, since=window.start, until=window.end):
        grading = find_grading(book, delivery.ticket)
        if grading is None:
            continue
        loads += 1
        if grading.rejected:
            rejected += 1
            continue
        settled += grading.settled_tonnes
        if delivery.sample is None:
            continue
        analysis = get_analysis(book, delivery.sample)
        for code in TRENDED:
            if code in analysis:
                basis = Basis.DRY if code == "nitrogen" else None
                totals[code] += analysis.value_on(code, basis) * grading.settled_tonnes
    means = {code: (0.0 if settled <= 0.0 else total / settled) for code, total in totals.items()}
    return Trend(party=party, loads=loads, rejected=rejected, settled_tonnes=settled, means=means)


def barley_page(book: Book, window: Window) -> str:
    """Every grower who delivered over a stretch of days, worst rate last."""
    rows = []
    for party in list_parties(book):
        trend = trend_for(book, party.code, window)
        if trend.loads == 0:
            continue
        rows.append(
            [
                party.code,
                party.name,
                str(trend.loads),
                f"{trend.settled_tonnes:.2f}",
                f"{trend.means['moisture']:.1f}",
                f"{trend.means['nitrogen']:.2f}",
                f"{trend.means['screenings']:.1f}",
                f"{trend.means['germ_capacity']:.1f}",
                f"{trend.rejection_rate:.0f}%",
            ]
        )
    return page(
        [
            heading(f"barley grading {window}"),
            table_block(
                "by grower",
                [
                    Column("code"),
                    Column("grower"),
                    Column("loads", Align.RIGHT),
                    Column("settled", Align.RIGHT),
                    Column("moisture", Align.RIGHT),
                    Column("nitrogen", Align.RIGHT),
                    Column("screenings", Align.RIGHT),
                    Column("germination", Align.RIGHT),
                    Column("rejected", Align.RIGHT),
                ],
                rows,
            ),
            [] if rows else ["nobody delivered anything."],
            [
                "every mean is over accepted loads and weighted by settled tonnes.",
                "a rejected load has no settled weight, so it is counted and not averaged.",
            ]
            if rows
            else [],
        ]
    )
