"""Specifications: what a customer signed for, and whether a lot meets it.

A specification is a list of clauses. A clause is one analyte, the basis it
is written on, and a floor, a ceiling or both. That is all a clause is, and
resisting the temptation to make it more is most of the value here.

Two things are worth saying about the assessment.

A clause the analysis has no result for is `UNTESTED`, which is not a pass.
A specification with an untested clause has not been met, it has been
partly looked at, and the two are different in a way that matters when the
lorry is on the weighbridge.

A clause names its own basis and the analysis converts to it. So a customer
who writes extract as it lies and a customer who writes it on dry matter can
both be assessed against the same analysis, and neither of them has to know
what the other one asked for.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from culmbin.errors import BasisError, ValidationError
from culmbin.model.analytes import analyte
from culmbin.model.enums import Basis, Conformance, Material
from culmbin.model.results import Analysis


@dataclass(frozen=True, slots=True)
class Clause:
    """One line of a specification.

    At least one of `minimum` and `maximum` has to be there. A clause with
    neither is a request to measure something, which is a different thing
    and is not written here.
    """

    code: str
    basis: Basis | None = None
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        item = analyte(self.code)
        if self.minimum is None and self.maximum is None:
            raise ValidationError(f"a clause on {item.label} has no floor and no ceiling")
        both = self.minimum is not None and self.maximum is not None
        if both and self.minimum > self.maximum:  # type: ignore[operator]
            raise ValidationError(
                f"{item.label} floor {self.minimum} is above ceiling {self.maximum}"
            )
        if item.basis is None and self.basis is not None:
            raise BasisError(f"{item.label} has no basis, so a clause cannot name one")
        if item.basis is not None and self.basis is None:
            raise BasisError(f"{item.label} is on a basis and this clause names none")

    @property
    def label(self) -> str:
        """What the specification sheet calls it."""
        return analyte(self.code).label

    @property
    def unit(self) -> str:
        """What it is measured in."""
        return analyte(self.code).unit

    def holds(self, value: float) -> bool:
        """Whether a value on this clause's basis satisfies it.

        Both bounds are inclusive. A specification that says maximum 4.5
        percent moisture is met by malt at exactly 4.5, and every customer
        in the trade reads it that way.
        """
        if self.minimum is not None and value < self.minimum:
            return False
        return not (self.maximum is not None and value > self.maximum)

    def __str__(self) -> str:
        if self.minimum is not None and self.maximum is not None:
            body = f"{self.minimum:g} to {self.maximum:g}"
        elif self.minimum is not None:
            body = f"min {self.minimum:g}"
        else:
            body = f"max {self.maximum:g}"
        tail = f" {self.unit}".rstrip()
        return f"{self.label} {body}{tail}"


@dataclass(frozen=True, slots=True)
class ClauseOutcome:
    """What one clause came to when it was assessed."""

    clause: Clause
    conformance: Conformance
    value: float | None

    @property
    def failed(self) -> bool:
        """Whether this clause was assessed and not met."""
        return self.conformance is Conformance.FAIL


@dataclass(frozen=True, slots=True)
class Assessment:
    """What a whole specification came to.

    The outcomes are in the order the clauses are written in, because a
    specification sheet is read in that order and a report that reorders it
    is a report somebody has to check against the original.
    """

    outcomes: tuple[ClauseOutcome, ...]

    def __iter__(self) -> Iterator[ClauseOutcome]:
        return iter(self.outcomes)

    def __len__(self) -> int:
        return len(self.outcomes)

    @property
    def failures(self) -> tuple[ClauseOutcome, ...]:
        """Every clause that was assessed and not met."""
        return tuple(outcome for outcome in self.outcomes if outcome.failed)

    @property
    def untested(self) -> tuple[ClauseOutcome, ...]:
        """Every clause nothing was measured for."""
        return tuple(
            outcome for outcome in self.outcomes if outcome.conformance is Conformance.UNTESTED
        )

    @property
    def conformance(self) -> Conformance:
        """The whole specification, in one word.

        A failure anywhere is a failure. Otherwise an untested clause makes
        the whole thing untested, because a specification is not met until
        every clause in it has been looked at.
        """
        if self.failures:
            return Conformance.FAIL
        if self.untested:
            return Conformance.UNTESTED
        return Conformance.PASS

    @property
    def met(self) -> bool:
        """Whether every clause was assessed and met."""
        return self.conformance is Conformance.PASS


@dataclass(frozen=True, slots=True)
class Specification:
    """A named set of clauses, for one material.

    Specifications are versioned by name rather than by number, because that
    is how the customers refer to them on the telephone: not the third
    version, but the one for the 2025 season.
    """

    name: str
    material: Material
    clauses: tuple[Clause, ...] = field(default_factory=tuple)
    varieties: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("a specification needs a name")
        if not self.clauses:
            raise ValidationError(f"specification {self.name} has no clauses")
        seen: set[str] = set()
        for clause in self.clauses:
            item = analyte(clause.code)
            if item.material is not self.material:
                raise ValidationError(
                    f"{item.label} is a {item.material} clause in a {self.material} specification"
                )
            if clause.code in seen:
                raise ValidationError(f"{item.label} is in {self.name} twice")
            seen.add(clause.code)

    def __iter__(self) -> Iterator[Clause]:
        return iter(self.clauses)

    def __len__(self) -> int:
        return len(self.clauses)

    @property
    def codes(self) -> frozenset[str]:
        """Every analyte this specification has something to say about."""
        return frozenset(clause.code for clause in self.clauses)

    def assess(self, analysis: Analysis) -> Assessment:
        """Work every clause against an analysis.

        The analysis has to be of the same material. Assessing a malt
        specification against a barley analysis would report every clause as
        untested, which reads like a lab backlog rather than like a mistake.
        """
        if analysis.material is not self.material:
            raise ValidationError(
                f"{self.name} is a {self.material} specification "
                f"and this is a {analysis.material} analysis"
            )
        outcomes = []
        for clause in self.clauses:
            if clause.code not in analysis:
                outcomes.append(ClauseOutcome(clause, Conformance.UNTESTED, None))
                continue
            value = analysis.value_on(clause.code, clause.basis)
            held = Conformance.PASS if clause.holds(value) else Conformance.FAIL
            outcomes.append(ClauseOutcome(clause, held, value))
        return Assessment(tuple(outcomes))


def specification(
    name: str,
    material: Material,
    clauses: Sequence[Clause],
    varieties: Sequence[str] = (),
) -> Specification:
    """Build one from sequences, which is what a caller reading a book has."""
    return Specification(name, material, tuple(clauses), frozenset(varieties))
