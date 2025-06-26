"""A blend plan, and what it is predicted to assay.

A plan is lots and tonnages. Predicting what it makes is four passes over
those, one for each of the rules in `blend.rules`, and the only difficulty
is remembering which pass a result belongs in.

Two things this refuses to do.

It will not predict a blend containing a lot with no analysis. A lot with no
certificate contributes an unknown to every number, and a prediction that
quietly leaves it out is a prediction of a different blend.

It will not draw more out of a lot than the lot has. That is not an
arithmetic rule, it is what stops a plan being written that the yard cannot
carry out.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from culmbin.blend.rules import DERIVED_FROM, BlendRule, blendable, rule_for
from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import Basis, Material
from culmbin.model.lots import MaltLot
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.model.spec import Assessment, Specification
from culmbin.units.mass import blend_moisture, dry_matter
from culmbin.units.scales import kolbach_index, weighted_mean


@dataclass(frozen=True, slots=True)
class Part:
    """One lot and how much of it the plan draws."""

    lot: MaltLot
    tonnes: float
    analysis: Analysis

    def __post_init__(self) -> None:
        if self.tonnes <= 0.0:
            raise ValidationError(f"{self.lot.code} contributes {self.tonnes} tonnes")
        if self.tonnes > self.lot.tonnes + 1e-9:
            raise ValidationError(
                f"{self.lot.code} holds {self.lot.tonnes:.1f}t "
                f"and the plan draws {self.tonnes:.1f}t"
            )
        if self.analysis.material is not Material.MALT:
            raise ValidationError(f"{self.analysis.reference} is not a malt analysis")

    @property
    def dry_tonnes(self) -> float:
        """The dry matter this part contributes, at its own analysis moisture."""
        return dry_matter(self.tonnes, self.analysis.moisture)


@dataclass(frozen=True, slots=True)
class Plan:
    """A named blend of several lots."""

    code: str
    parts: tuple[Part, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a blend plan needs a code")
        if not self.parts:
            raise ValidationError(f"{self.code} has no parts")
        codes = [part.lot.code for part in self.parts]
        if len(codes) != len(set(codes)):
            raise ValidationError(f"{self.code} draws from one lot twice")

    @property
    def tonnes(self) -> float:
        """What the blend weighs."""
        return sum(part.tonnes for part in self.parts)

    @property
    def dry_tonnes(self) -> float:
        """The dry matter in the blend."""
        return sum(part.dry_tonnes for part in self.parts)

    @property
    def varieties(self) -> frozenset[str]:
        """Every variety in the blend."""
        return frozenset().union(*(part.lot.varieties for part in self.parts))

    @property
    def variety(self) -> str | None:
        """The variety the blend can be sold as, or nothing."""
        varieties = self.varieties
        return next(iter(varieties)) if len(varieties) == 1 else None

    @property
    def crop_years(self) -> frozenset[int]:
        """Every crop year in the blend."""
        return frozenset().union(*(part.lot.crop_years for part in self.parts))

    def share_of(self, lot: str) -> float:
        """What fraction of the blend one lot is, by weight as it lies."""
        for part in self.parts:
            if part.lot.code == lot:
                return part.tonnes / self.tonnes
        raise StateError(f"{lot} is not in {self.code}")


def common_codes(plan: Plan) -> frozenset[str]:
    """Every analyte every part of the plan has a result for.

    A result one lot is missing cannot be blended, because the blend would
    be a mean over some of the malt rather than over all of it. It comes
    back as untested against a specification, which is the right answer.
    """
    codes = blendable()
    for part in plan.parts:
        codes &= part.analysis.codes
    return codes


def missing_codes(plan: Plan, wanted: frozenset[str]) -> frozenset[str]:
    """Every analyte the plan cannot predict out of a set that was wanted."""
    return wanted - common_codes(plan)


def _blend_one(plan: Plan, code: str) -> float:
    """The blended value of one analyte, on whichever rule it follows."""
    rule = rule_for(code)
    if rule is BlendRule.MOISTURE:
        return blend_moisture([(part.tonnes, part.analysis.moisture) for part in plan.parts])
    if rule is BlendRule.DRY_WEIGHT:
        return weighted_mean(
            [
                (part.dry_tonnes, part.analysis.value_on(code, _basis_of(code)))
                for part in plan.parts
            ]
        )
    if rule is BlendRule.AS_IS_WEIGHT:
        return weighted_mean(
            [(part.tonnes, part.analysis.value_on(code, _basis_of(code))) for part in plan.parts]
        )
    numerator, denominator = DERIVED_FROM[code]
    return kolbach_index(_blend_one(plan, numerator), _blend_one(plan, denominator))


def _basis_of(code: str) -> Basis | None:
    """The basis a blended result is worked on, which is the one it is reported on."""
    from culmbin.model.analytes import analyte

    return analyte(code).basis


def predict(plan: Plan, reference: str, on: dt.date) -> Analysis:
    """What the blend is predicted to assay.

    Everything every part has a result for, blended on its own rule. A
    derived result is only predicted when both of the things it is derived
    from can be.
    """
    for part in plan.parts:
        if not part.lot.certified:
            raise StateError(f"{part.lot.code} has no analysis, so this blend cannot be predicted")
    codes = common_codes(plan)
    results = []
    for code in sorted(codes):
        rule = rule_for(code)
        if rule is BlendRule.DERIVED and not set(DERIVED_FROM[code]) <= codes:
            continue
        results.append(Result(code, _blend_one(plan, code), _basis_of(code)))
    return analysis_of(reference, Material.MALT, on, results)


def assess(plan: Plan, spec: Specification, reference: str, on: dt.date) -> Assessment:
    """Whether the blend is predicted to meet a specification."""
    return spec.assess(predict(plan, reference, on))


def plan_of(code: str, parts: Sequence[Part]) -> Plan:
    """Build a plan from a sequence."""
    return Plan(code, tuple(parts))
