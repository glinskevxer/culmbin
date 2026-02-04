"""What a kiln run costs in gas, and why comparing two of them is hard.

Gas is the second biggest cost in the building after barley, and the number
everybody quotes is specific energy: megajoules per tonne of malt. It is a
useful number and it is not a measure of how well the kiln is running,
because most of it is decided before the piece gets on the kiln.

A piece cast at 46 percent carries about four percent more water than one
cast at 44, and every kilogramme of that water has to be boiled off. So the
same kiln, on the same curve, burning gas at the same efficiency, reports a
worse specific energy on a wetter cast. A kiln that looks to have got worse
in October has very often just been given wetter pieces.

What can be compared is **efficiency**: the energy the water actually needed
against the energy the meter says was burnt. That number does not care how
wet the piece was, and it is the one that moves when a fan belt slips or the
heat recovery fouls up.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.units.mass import dry_matter

LATENT_HEAT_MJ_PER_KG = 2.26
"""Megajoules to turn a kilogramme of water at boiling into steam.

The real figure at kiln temperatures is a little lower, and using the round
one keeps every efficiency figure in the building on the same basis, which
matters more than the second decimal place.
"""

SENSIBLE_HEAT_MJ_PER_KG = 0.30
"""Megajoules to get a kilogramme of water and its grain up to temperature.

Lumped together on purpose. Splitting it into the grain, the water and the
air needs three specific heats and a bed temperature nobody measures.
"""

GAS_MJ_PER_M3 = 39.0
"""Calorific value of the gas on this site, off the supplier's statement."""

MJ_PER_KWH = 3.6

TYPICAL_EFFICIENCY = 0.62
"""What this plant's kilns run at with the heat recovery working.

Below about 0.5 something is wrong. Above 0.8 the meter is wrong.
"""

KILOGRAMMES_PER_TONNE = 1000.0


def water_removed(green_tonnes: float, green_moisture: float, off_moisture: float) -> float:
    """Kilogrammes of water a kiln run has to take out.

    Worked through the dry matter, because the dry matter is the thing that
    does not change on a kiln and the two weights do.
    """
    if off_moisture > green_moisture:
        raise ValidationError(
            f"malt cannot come off at {off_moisture} wetter than the {green_moisture} it went on"
        )
    dry = dry_matter(green_tonnes, green_moisture)
    off_tonnes = dry / (1.0 - off_moisture / 100.0)
    return (green_tonnes - off_tonnes) * KILOGRAMMES_PER_TONNE


def heat_wanted(water_kg: float) -> float:
    """Megajoules the water actually needs, latent and sensible together."""
    if water_kg < 0.0:
        raise ValidationError(f"a run cannot remove {water_kg} kilogrammes of water")
    return water_kg * (LATENT_HEAT_MJ_PER_KG + SENSIBLE_HEAT_MJ_PER_KG)


def gas_for(heat_mj: float, efficiency: float = TYPICAL_EFFICIENCY) -> float:
    """Cubic metres of gas a run is expected to burn."""
    if not 0.0 < efficiency <= 1.0:
        raise ValidationError(f"an efficiency of {efficiency} is not one")
    return heat_mj / efficiency / GAS_MJ_PER_M3


def heat_from(gas_m3: float) -> float:
    """Megajoules a meter reading is worth."""
    if gas_m3 < 0.0:
        raise ValidationError(f"a meter cannot read {gas_m3} cubic metres")
    return gas_m3 * GAS_MJ_PER_M3


@dataclass(frozen=True, slots=True)
class KilnEnergy:
    """One kiln run, as the gas meter and the weighbridge saw it."""

    piece: str
    green_tonnes: float
    green_moisture: float
    malt_tonnes: float
    malt_moisture: float
    gas_m3: float

    def __post_init__(self) -> None:
        if self.green_tonnes <= 0.0 or self.malt_tonnes <= 0.0:
            raise ValidationError(f"{self.piece} has a weight of nothing on it")
        if self.gas_m3 < 0.0:
            raise ValidationError(f"{self.piece} has a meter reading of {self.gas_m3}")
        if self.malt_moisture > self.green_moisture:
            raise ValidationError(f"{self.piece} came off the kiln wetter than it went on")

    @property
    def water_kg(self) -> float:
        """The water this run took out."""
        return water_removed(self.green_tonnes, self.green_moisture, self.malt_moisture)

    @property
    def heat_wanted_mj(self) -> float:
        """The energy the water needed."""
        return heat_wanted(self.water_kg)

    @property
    def heat_burnt_mj(self) -> float:
        """The energy the meter says was burnt."""
        return heat_from(self.gas_m3)

    @property
    def efficiency(self) -> float:
        """What the water needed over what was burnt.

        This is the number worth comparing between runs, because it does not
        carry the cast moisture with it.
        """
        if self.heat_burnt_mj <= 0.0:
            raise ValidationError(f"{self.piece} burnt nothing, so it has no efficiency")
        return self.heat_wanted_mj / self.heat_burnt_mj

    @property
    def specific_energy_mj_per_tonne(self) -> float:
        """Megajoules per tonne of malt, which is the figure everybody quotes.

        And the figure that gets worse on a wetter cast without anything
        having got worse.
        """
        return self.heat_burnt_mj / self.malt_tonnes

    @property
    def specific_energy_kwh_per_tonne(self) -> float:
        """The same figure in the unit the electricity bill uses."""
        return self.specific_energy_mj_per_tonne / MJ_PER_KWH

    @property
    def suspect(self) -> bool:
        """Whether the efficiency is outside what a kiln can actually do.

        Below half, something is wrong with the kiln. Above four fifths,
        something is wrong with the meter. Either way somebody should look
        before the figure goes on a monthly report.
        """
        return not 0.5 <= self.efficiency <= 0.8


def compare(first: KilnEnergy, second: KilnEnergy) -> str:
    """A sentence saying which of two runs was actually run better.

    Written as a sentence because the answer is nearly always the opposite
    of what the specific energy figures suggest, and a number on its own
    invites the wrong reading.
    """
    if first.efficiency == second.efficiency:
        return f"{first.piece} and {second.piece} ran at the same efficiency"
    better, worse = (first, second) if first.efficiency > second.efficiency else (second, first)
    if better.specific_energy_mj_per_tonne > worse.specific_energy_mj_per_tonne:
        return (
            f"{better.piece} ran better than {worse.piece} despite using more gas a tonne, "
            f"because it was cast at {better.green_moisture:.1f} against "
            f"{worse.green_moisture:.1f}"
        )
    return f"{better.piece} ran better than {worse.piece} and used less gas a tonne"
