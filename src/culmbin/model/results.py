"""A result, and the set of results that makes an analysis.

The important thing in this module is that an analysis carries its own
moisture and does the converting itself. Every earlier attempt at this in a
malting office ends up with a spreadsheet where somebody has typed the
current bin moisture into a conversion of a result taken five weeks ago, and
the answer is wrong by about half a percent of extract, which is about what
the argument with the customer is worth.

So: you do not convert a result. You ask an analysis for a value on a basis,
and it uses the moisture that was measured alongside it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from culmbin.errors import BasisError, NotFoundError, ValidationError
from culmbin.model.analytes import MOISTURE_OF, analyte, convert
from culmbin.model.enums import Basis, Material


@dataclass(frozen=True, slots=True)
class Result:
    """One measured number, its basis, and what it was measured on.

    `basis` is `None` for anything the table says has no basis. It is not
    optional for anything else, and a result that disagrees with the table
    about that is refused here rather than at the certificate.
    """

    code: str
    value: float
    basis: Basis | None = None

    def __post_init__(self) -> None:
        item = analyte(self.code)
        if item.basis is None and self.basis is not None:
            raise BasisError(f"{item.label} has no basis, so {self.basis} is not one of its")
        if item.basis is not None and self.basis is None:
            raise BasisError(f"{item.label} is reported on a basis and this result names none")
        if self.value < 0.0:
            raise ValidationError(f"{item.label} of {self.value} is negative")

    @property
    def label(self) -> str:
        """What the certificate calls it."""
        return analyte(self.code).label

    @property
    def unit(self) -> str:
        """What it is measured in."""
        return analyte(self.code).unit


@dataclass(frozen=True, slots=True)
class Analysis:
    """A set of results taken off one thing on one day.

    An analysis of malt must carry a malt moisture and an analysis of barley
    must carry a barley moisture, because without one nothing else in the set
    can be restated and half the specification clauses cannot be assessed.
    """

    reference: str
    material: Material
    taken: dt.date
    results: tuple[Result, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValidationError("an analysis needs a reference")
        seen: set[str] = set()
        for result in self.results:
            item = analyte(result.code)
            if item.material is not self.material:
                raise ValidationError(
                    f"{item.label} is a {item.material} result "
                    f"and this is a {self.material} analysis"
                )
            if result.code in seen:
                raise ValidationError(f"{item.label} is in this analysis twice")
            seen.add(result.code)
        if MOISTURE_OF[self.material] not in seen:
            raise ValidationError(
                f"a {self.material} analysis without a moisture cannot be converted or assessed"
            )

    @property
    def moisture(self) -> float:
        """The moisture this analysis was taken at."""
        return self[MOISTURE_OF[self.material]].value

    @property
    def codes(self) -> frozenset[str]:
        """Every analyte this analysis has a result for."""
        return frozenset(result.code for result in self.results)

    def __iter__(self) -> Iterator[Result]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    def __contains__(self, code: object) -> bool:
        return isinstance(code, str) and code in self.codes

    def __getitem__(self, code: str) -> Result:
        for result in self.results:
            if result.code == code:
                return result
        raise NotFoundError(f"this analysis has no {code!r} result")

    def get(self, code: str) -> Result | None:
        """The result, or nothing, for callers that treat absence as an answer."""
        try:
            return self[code]
        except NotFoundError:
            return None

    def value_on(self, code: str, basis: Basis | None) -> float:
        """The value of a result on the basis asked for.

        The conversion uses this analysis's own moisture, which is the whole
        point of asking the analysis rather than converting the result. Ask
        for a basis on something that has none, or none on something that
        has one, and it raises rather than guessing.
        """
        result = self[code]
        if result.basis is None or basis is None:
            if result.basis is not basis:
                raise BasisError(f"{result.label} cannot be reported on {basis}")
            return result.value
        return convert(code, result.value, result.basis, basis, self.moisture)

    def with_result(self, result: Result) -> Analysis:
        """A copy of this analysis with one more result in it.

        Analyses are frozen because a certificate that quietly changed after
        it was sent is the worst kind of record. Adding a result makes a new
        one, and the caller decides what to do with the old.
        """
        return Analysis(self.reference, self.material, self.taken, (*self.results, result))

    def as_mapping(self) -> Mapping[str, float]:
        """Every result as its code and its value, on whatever basis it holds."""
        return {result.code: result.value for result in self.results}


def analysis_of(
    reference: str,
    material: Material,
    taken: dt.date,
    results: Sequence[Result],
) -> Analysis:
    """Build an analysis from a sequence, which is what every caller has."""
    return Analysis(reference, material, taken, tuple(results))
