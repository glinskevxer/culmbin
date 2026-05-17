"""Steep water: what went in, what the barley kept, and what went to drain.

Water is metered on the way in and charged for twice: once by the water
company and again, more heavily, by whoever takes the effluent. So the
number that matters is not how much was used, it is how much went to drain,
and those are two very different figures.

The arithmetic is a mass balance and it has exactly one interesting term.
**The barley keeps the water it took up**, and that is a real quantity: a
forty five tonne charge going from twelve percent to forty five percent
keeps about twenty six cubic metres. Everything else that went in came out,
and it came out dirty.

The specific figures the trade quotes are cubic metres per tonne of malt.
Three to five is a plant with air rests and recycling. Seven and up is a
plant running wet stands long and dumping between them, and the difference
is the effluent bill rather than the malt.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.units.mass import dry_matter

CUBIC_METRES_PER_TONNE_OF_WATER = 1.0
"""A tonne of water is a cubic metre, near enough for a steep.

At steeping temperatures it is a shade over, and nothing in this building
measures water to a tenth of a percent.
"""

TYPICAL_LOW = 3.0
TYPICAL_HIGH = 5.0
"""What a plant with air rests and recycling uses, per tonne of malt."""


def water_taken_up(charge_tonnes: float, charge_moisture: float, steep_out: float) -> float:
    """Cubic metres of water the barley kept, out of what was put over it.

    Worked through the dry matter, because the dry matter is the thing that
    does not change in a steep and both weights do.
    """
    if steep_out <= charge_moisture:
        raise ValidationError(
            f"steep out at {steep_out} is no wetter than barley at {charge_moisture}"
        )
    dry = dry_matter(charge_tonnes, charge_moisture)
    out_tonnes = dry / (1.0 - steep_out / 100.0)
    return (out_tonnes - charge_tonnes) * CUBIC_METRES_PER_TONNE_OF_WATER


@dataclass(frozen=True, slots=True)
class WaterUse:
    """One piece's steep water, as the meter and the weighbridge saw it."""

    piece: str
    charge_tonnes: float
    charge_moisture: float
    steep_out_moisture: float
    metered_m3: float
    malt_tonnes: float

    def __post_init__(self) -> None:
        if self.charge_tonnes <= 0.0 or self.malt_tonnes <= 0.0:
            raise ValidationError(f"{self.piece} has a weight of nothing on it")
        if self.metered_m3 < 0.0:
            raise ValidationError(f"{self.piece} has a meter reading of {self.metered_m3}")
        if self.metered_m3 + 1e-6 < self.taken_up_m3:
            raise ValidationError(
                f"{self.piece} kept {self.taken_up_m3:.1f}m3 out of {self.metered_m3:.1f}m3, "
                f"which is more than went over it"
            )

    @property
    def taken_up_m3(self) -> float:
        """What the barley kept."""
        return water_taken_up(self.charge_tonnes, self.charge_moisture, self.steep_out_moisture)

    @property
    def to_drain_m3(self) -> float:
        """What went out dirty, which is the figure the effluent bill is on."""
        return self.metered_m3 - self.taken_up_m3

    @property
    def specific_m3_per_tonne(self) -> float:
        """Cubic metres metered per tonne of malt, which is what the trade quotes."""
        return self.metered_m3 / self.malt_tonnes

    @property
    def drain_share(self) -> float:
        """What share of the metered water went to drain, as a fraction of one."""
        if self.metered_m3 <= 0.0:
            return 0.0
        return self.to_drain_m3 / self.metered_m3

    @property
    def heavy(self) -> bool:
        """Whether this piece used more than a plant with air rests should.

        Over the band is not a fault. It is a bill, and it is worth knowing
        which pieces are on it.
        """
        return self.specific_m3_per_tonne > TYPICAL_HIGH

    def __str__(self) -> str:
        return (
            f"{self.piece} {self.metered_m3:.1f}m3, {self.to_drain_m3:.1f}m3 to drain, "
            f"{self.specific_m3_per_tonne:.2f} a tonne"
        )


def expected_m3(malt_tonnes: float, per_tonne: float = TYPICAL_LOW) -> float:
    """What a piece is expected to use, for a plan or a budget."""
    if malt_tonnes <= 0.0:
        raise ValidationError(f"a piece making {malt_tonnes} tonnes is not a piece")
    if per_tonne <= 0.0:
        raise ValidationError(f"{per_tonne} cubic metres a tonne is not a rate")
    return malt_tonnes * per_tonne
