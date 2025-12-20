"""The certificate of analysis, which is the only thing the customer reads.

It is a page of numbers with units and bases on them, and its whole job is
to be unambiguous six months later when somebody rings up about a brew that
went wrong. So:

- every result carries its unit and, where it has one, its basis
- the moisture is at the top, because it is what the rest are relative to
- a clause the laboratory did not run is printed as not tested, never left
  off, because a certificate with a line missing reads like a certificate
  that passed
- a lot out of a mixed bin prints its varieties, plural, and does not print
  a variety line at all
- an analysis the laboratory has replaced is marked at the top and not
  quietly reprinted, because a withdrawn certificate that looks like a
  current one is the worst thing this module could produce

The certificate is generated from the lot's own analysis and, if the caller
gives one, assessed against a specification. Assessing is optional because
the same lot is certified once and sold against two customers' clauses.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import StateError
from culmbin.model.analytes import analyte, report
from culmbin.model.enums import Basis, Conformance
from culmbin.model.lots import MaltLot
from culmbin.model.results import Analysis
from culmbin.model.spec import Assessment, Specification
from culmbin.report.layout import Align, Column, block, heading, page, pairs, table
from culmbin.store.analyses import current, get_analysis, is_superseded
from culmbin.store.book import Book
from culmbin.store.lots import get_lot
from culmbin.store.specs import get_specification

BASIS_WORDS = {Basis.DRY: "dry", Basis.AS_IS: "as is"}
CONFORMANCE_WORDS = {
    Conformance.PASS: "meets",
    Conformance.FAIL: "OUT",
    Conformance.UNTESTED: "not tested",
}


@dataclass(frozen=True, slots=True)
class Certificate:
    """Everything a certificate prints, before it is laid out."""

    lot: MaltLot
    analysis: Analysis
    specification: Specification | None = None
    assessment: Assessment | None = None
    withdrawn_for: str | None = None

    @property
    def withdrawn(self) -> bool:
        """Whether the laboratory has replaced this analysis with a retest."""
        return self.withdrawn_for is not None

    @property
    def conformance(self) -> Conformance | None:
        """What the assessment came to, or nothing if there was none."""
        return None if self.assessment is None else self.assessment.conformance

    @property
    def in_specification(self) -> bool:
        """Whether this lot met every clause it was assessed against."""
        return self.assessment is not None and self.assessment.met


def build(book: Book, lot: str, specification: str | None = None) -> Certificate:
    """Gather everything a certificate needs out of the book."""
    held = get_lot(book, lot)
    if held.analysis is None:
        raise StateError(f"{lot} has no analysis, so there is no certificate to write")
    analysis = get_analysis(book, held.analysis)
    replaced = current(book, held.analysis) if is_superseded(book, held.analysis) else None
    if specification is None:
        return Certificate(lot=held, analysis=analysis, withdrawn_for=replaced)
    spec = get_specification(book, specification)
    return Certificate(
        lot=held,
        analysis=analysis,
        specification=spec,
        assessment=spec.assess(analysis),
        withdrawn_for=replaced,
    )


def _result_rows(certificate: Certificate) -> list[list[str]]:
    """Every measured result, moisture first, with its unit and basis."""
    moisture = certificate.analysis["malt_moisture"]
    ordered = [moisture, *(r for r in certificate.analysis if r.code != moisture.code)]
    rows = []
    for result in ordered:
        item = analyte(result.code)
        rows.append(
            [
                item.label,
                report(result.code, result.value),
                item.unit,
                "" if result.basis is None else BASIS_WORDS[result.basis],
            ]
        )
    return rows


def _clause_rows(certificate: Certificate) -> list[list[str]]:
    """Every clause of the specification, including the ones nobody ran."""
    if certificate.assessment is None:
        return []
    rows = []
    for outcome in certificate.assessment:
        value = "" if outcome.value is None else report(outcome.clause.code, outcome.value)
        rows.append(
            [
                outcome.clause.label,
                str(outcome.clause),
                value,
                CONFORMANCE_WORDS[outcome.conformance],
            ]
        )
    return rows


def render(certificate: Certificate, on: dt.date) -> str:
    """Lay a certificate out as a page."""
    lot = certificate.lot
    facts = [
        ("lot", lot.code),
        ("sealed", lot.sealed.isoformat()),
        ("tonnes", f"{lot.tonnes:.2f}"),
        ("analysis", certificate.analysis.reference),
        ("sampled", certificate.analysis.taken.isoformat()),
    ]
    if lot.variety is not None:
        facts.append(("variety", lot.variety))
    else:
        facts.append(("varieties", ", ".join(sorted(lot.varieties))))
    if lot.crop_years:
        facts.append(("crop", ", ".join(str(year) for year in sorted(lot.crop_years))))
    if lot.style is not None:
        facts.append(("style", str(lot.style)))
    facts.append(("issued", on.isoformat()))

    sections = [
        heading(f"certificate of analysis {lot.code}"),
        [f"WITHDRAWN: this analysis was replaced by {certificate.withdrawn_for}."]
        if certificate.withdrawn
        else [],
        pairs(facts),
        block(
            "analysis",
            table(
                [
                    Column("determination"),
                    Column("result", Align.RIGHT),
                    Column("unit"),
                    Column("basis"),
                ],
                _result_rows(certificate),
            ),
        ),
    ]
    if certificate.specification is not None and certificate.assessment is not None:
        sections.append(
            block(
                f"against {certificate.specification.name}",
                table(
                    [
                        Column("clause"),
                        Column("requirement"),
                        Column("result", Align.RIGHT),
                        Column("outcome"),
                    ],
                    _clause_rows(certificate),
                ),
            )
        )
        verdict = CONFORMANCE_WORDS[certificate.assessment.conformance]
        sections.append([f"this lot {verdict} {certificate.specification.name}"])
    return page(sections)


def write(book: Book, lot: str, on: dt.date, specification: str | None = None) -> str:
    """Build and lay out a certificate in one call."""
    return render(build(book, lot, specification), on)
