"""The analyte table, and which of them can be restated on the other basis.

An analysis is a set of results and a result is a number, a unit and a basis.
Most of the trouble in a malting lab comes from the third one. Extract on dry
matter and extract as it lies are four percent apart, which is the difference
between meeting a specification and not.

Two things in here do the work.

The table says what each analyte is: what it is measured in, what basis the
lab reports it on, and how many places the certificate prints. Everything
else in the package reads the table rather than carrying its own opinion.

The convertible flag says whether restating it on the other basis means
anything at all. Extract does, because it is a percentage of a weight and
you can choose the weight. Colour does not, because it is an absorbance and
there is no weight in it. Asking for colour on dry matter is not a
conversion, it is a category mistake, and it raises.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from culmbin.errors import BasisError, NotFoundError, ValidationError
from culmbin.model.enums import Basis, Material
from culmbin.units.mass import to_as_is_basis, to_dry_basis


@dataclass(frozen=True, slots=True)
class Analyte:
    """One thing the lab measures.

    `basis` is the basis the lab reports it on by default, and it is `None`
    for anything that has no basis at all. Moisture is the obvious case: it
    is not on a basis, it *is* the basis.
    """

    code: str
    label: str
    material: Material
    unit: str
    basis: Basis | None
    places: int
    convertible: bool

    def __post_init__(self) -> None:
        if self.convertible and self.basis is None:
            raise ValidationError(f"{self.code} has no basis, so it cannot be converted")
        if self.places < 0:
            raise ValidationError(f"{self.code} cannot report to {self.places} places")


def _analyte(
    code: str,
    label: str,
    material: Material,
    unit: str,
    basis: Basis | None,
    places: int,
    convertible: bool,
) -> Analyte:
    return Analyte(code, label, material, unit, basis, places, convertible)


_TABLE: tuple[Analyte, ...] = (
    _analyte("moisture", "moisture", Material.BARLEY, "%", None, 1, False),
    _analyte("nitrogen", "total nitrogen", Material.BARLEY, "%", Basis.DRY, 2, True),
    _analyte("screenings", "screenings under 2.2mm", Material.BARLEY, "%", None, 1, False),
    _analyte("retention", "retention over 2.5mm", Material.BARLEY, "%", None, 1, False),
    _analyte("germ_capacity", "germinative capacity", Material.BARLEY, "%", None, 1, False),
    _analyte("germ_energy", "germinative energy", Material.BARLEY, "%", None, 1, False),
    _analyte("water_sensitivity", "water sensitivity", Material.BARLEY, "%", None, 1, False),
    _analyte("admixture", "admixture", Material.BARLEY, "%", None, 2, False),
    _analyte("tgw", "thousand grain weight", Material.BARLEY, "g", Basis.DRY, 1, False),
    _analyte("malt_moisture", "moisture", Material.MALT, "%", None, 2, False),
    _analyte("extract_fine", "fine grind extract", Material.MALT, "%", Basis.DRY, 1, True),
    _analyte("extract_coarse", "coarse grind extract", Material.MALT, "%", Basis.DRY, 1, True),
    _analyte("colour", "colour", Material.MALT, "EBC", None, 1, False),
    _analyte("total_protein", "total protein", Material.MALT, "%", Basis.DRY, 2, True),
    _analyte("soluble_protein", "soluble protein", Material.MALT, "%", Basis.DRY, 2, True),
    _analyte("kolbach", "Kolbach index", Material.MALT, "%", None, 1, False),
    _analyte("diastatic_power", "diastatic power", Material.MALT, "WK", Basis.DRY, 0, False),
    _analyte("friability", "friability", Material.MALT, "%", None, 1, False),
    _analyte("beta_glucan", "beta glucan", Material.MALT, "mg/l", None, 0, False),
    _analyte("viscosity", "wort viscosity", Material.MALT, "mPa.s", None, 3, False),
    _analyte("fan", "free amino nitrogen", Material.MALT, "mg/l", None, 0, False),
    _analyte("homogeneity", "homogeneity", Material.MALT, "%", None, 1, False),
)

ANALYTES: Mapping[str, Analyte] = {analyte.code: analyte for analyte in _TABLE}
"""Every analyte, by code. Nothing else in the package writes this list down."""

MOISTURE_OF: Mapping[Material, str] = {
    Material.BARLEY: "moisture",
    Material.MALT: "malt_moisture",
}
"""Which analyte carries the moisture a conversion needs, per material.

There are two of them because barley moisture and malt moisture are measured
by different methods to different precisions, and a certificate that reports
one under the other's name is wrong even when the number is right.
"""


def analyte(code: str) -> Analyte:
    """Look one up, or say what was asked for."""
    try:
        return ANALYTES[code]
    except KeyError:
        raise NotFoundError(f"no analyte called {code!r}") from None


def analytes_for(material: Material) -> tuple[Analyte, ...]:
    """Every analyte measured on one material, in table order."""
    return tuple(item for item in _TABLE if item.material is material)


def convert(code: str, value: float, from_basis: Basis, to_basis: Basis, moisture: float) -> float:
    """Restate a result on the other basis, using the moisture it was measured with.

    The moisture must come from the same analysis as the value. Using
    today's moisture on a result from three weeks ago converts it with the
    wrong number and produces something that looks right, which is why this
    takes it as an argument rather than looking it up.
    """
    item = analyte(code)
    if not item.convertible:
        raise BasisError(f"{item.label} is not a percentage of a weight, so it has no basis")
    if from_basis is to_basis:
        return value
    if to_basis is Basis.DRY:
        return to_dry_basis(value, moisture)
    return to_as_is_basis(value, moisture)


def report(code: str, value: float) -> str:
    """Print a result the way the certificate prints it."""
    item = analyte(code)
    return f"{value:.{item.places}f}"
