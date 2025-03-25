"""The vessels and the bins: the fixed things a piece of malt sits in.

A vessel is sized two different ways depending on what it is. A steep is a
volume, so its limit is a tonnage and that is the end of it. A germination
box or a floor is an area, so its limit is a bed depth, and the tonnage it
takes depends on how deep the maltster is prepared to run it. Kilns are
areas too, and a kiln loaded deeper than its air can lift dries unevenly,
which is the same failure as a box but shows up three days later.

So the tonnage limit of a box is not a property of the box. It is a property
of the box and the depth, and the package makes you say the depth.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import VesselKind

BED_DENSITY_T_PER_M3 = 0.55
"""Tonnes of green malt per cubic metre of bed, at the depth this plant runs.

Green malt is bulkier than barley because the grain has swollen and the
rootlets hold it apart. The number is the plant's own, measured off the
weighbridge against the box depth gauge, and it drifts a little through the
season without anybody thinking it worth changing.
"""

AREA_KINDS = frozenset({VesselKind.BOX, VesselKind.FLOOR, VesselKind.KILN})
"""The vessels whose size is an area and a depth rather than a volume."""


@dataclass(frozen=True, slots=True)
class Vessel:
    """One steep, box, floor or kiln.

    `floor_area_m2` and `depth_limit_cm` are set for the area kinds and
    `charge_limit_t` for the steeps. Getting that the wrong way round is
    refused here, because a steep with a bed depth is a mistake that would
    otherwise sit in the book looking plausible.
    """

    code: str
    name: str
    kind: VesselKind
    commissioned: dt.date
    charge_limit_t: float | None = None
    floor_area_m2: float | None = None
    depth_limit_cm: float | None = None
    retired: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a vessel needs a code")
        if self.kind in AREA_KINDS:
            if self.floor_area_m2 is None or self.depth_limit_cm is None:
                raise ValidationError(f"{self.code} is a {self.kind} and needs an area and a depth")
            if self.charge_limit_t is not None:
                raise ValidationError(f"{self.code} is sized by depth, so it has no charge limit")
            if self.floor_area_m2 <= 0.0 or self.depth_limit_cm <= 0.0:
                raise ValidationError(f"{self.code} has an area or depth of nothing")
        else:
            if self.charge_limit_t is None:
                raise ValidationError(f"{self.code} is a {self.kind} and needs a charge limit")
            if self.floor_area_m2 is not None or self.depth_limit_cm is not None:
                raise ValidationError(f"{self.code} is sized by volume, so it has no bed depth")
            if self.charge_limit_t <= 0.0:
                raise ValidationError(f"{self.code} has a charge limit of nothing")
        if self.retired is not None and self.retired < self.commissioned:
            raise ValidationError(f"{self.code} was retired before it was commissioned")

    @property
    def sized_by_area(self) -> bool:
        """Whether this vessel's limit is a depth rather than a tonnage."""
        return self.kind in AREA_KINDS

    def in_service_on(self, day: dt.date) -> bool:
        """Whether the vessel was available on a given day."""
        if day < self.commissioned:
            return False
        return self.retired is None or day < self.retired

    def tonnes_at_depth(self, depth_cm: float) -> float:
        """What this vessel holds at a given bed depth.

        Only the area kinds have an answer. Asking a steep is refused rather
        than answered with its charge limit, because a caller that asks has
        confused the two and would take the answer.
        """
        if not self.sized_by_area:
            raise ValidationError(f"{self.code} is a {self.kind} and has no bed")
        if depth_cm <= 0.0:
            raise ValidationError(f"a bed {depth_cm}cm deep is not a bed")
        assert self.floor_area_m2 is not None
        assert self.depth_limit_cm is not None
        if depth_cm > self.depth_limit_cm:
            raise ValidationError(
                f"{depth_cm:.0f}cm is deeper than {self.code} runs at {self.depth_limit_cm:.0f}cm"
            )
        return self.floor_area_m2 * depth_cm / 100.0 * BED_DENSITY_T_PER_M3

    @property
    def limit_t(self) -> float:
        """The most this vessel takes, at its own deepest bed.

        For a steep that is the charge limit. For a box it is what the bed
        holds at the depth limit, which is the number the planner uses and
        nobody should be working out by hand twice.
        """
        if self.sized_by_area:
            assert self.depth_limit_cm is not None
            return self.tonnes_at_depth(self.depth_limit_cm)
        assert self.charge_limit_t is not None
        return self.charge_limit_t

    def holds(self, tonnes: float) -> bool:
        """Whether a charge fits."""
        if tonnes <= 0.0:
            raise ValidationError(f"a charge of {tonnes} tonnes is not a charge")
        return tonnes <= self.limit_t + 1e-9


@dataclass(frozen=True, slots=True)
class Plant:
    """Every vessel in the building, looked up by code or by kind."""

    vessels: tuple[Vessel, ...]

    def __post_init__(self) -> None:
        codes = [vessel.code for vessel in self.vessels]
        duplicates = {code for code in codes if codes.count(code) > 1}
        if duplicates:
            raise ValidationError(f"two vessels share the code {sorted(duplicates)[0]}")

    def __iter__(self) -> Iterator[Vessel]:
        return iter(self.vessels)

    def __len__(self) -> int:
        return len(self.vessels)

    def __getitem__(self, code: str) -> Vessel:
        for vessel in self.vessels:
            if vessel.code == code:
                return vessel
        raise NotFoundError(f"no vessel called {code!r}")

    def of_kind(self, kind: VesselKind) -> tuple[Vessel, ...]:
        """Every vessel of one kind, in the order they were given."""
        return tuple(vessel for vessel in self.vessels if vessel.kind is kind)

    def in_service_on(self, day: dt.date) -> tuple[Vessel, ...]:
        """Every vessel available on a day."""
        return tuple(vessel for vessel in self.vessels if vessel.in_service_on(day))


def plant_of(vessels: Sequence[Vessel]) -> Plant:
    """Build a plant from a sequence, which is what a caller reading a book has."""
    return Plant(tuple(vessels))
