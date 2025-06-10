"""Malting loss, culm, and the yield figure the trade actually quotes.

Two numbers here look like the same number and are not.

**Malting loss** is dry matter. It is the barley dry matter that went into
the steep minus the malt dry matter that came off the kiln, as a percentage
of the first. It is a real physical loss: the embryo respires some of the
starch away and the rootlets take the rest, and the rootlets are screened off
into the culm bin. Eight to ten percent is a normal malting loss and nothing
a maltster does makes it zero.

**Yield** is what the office quotes: malt tonnes out over barley tonnes in,
both as they lie. It carries the malting loss and it also carries both
moistures, because the barley came in at twelve percent and the malt goes
out at four and a half. So two malthouses with identical malting loss report
different yields if their barley arrives at different moistures, and a wet
autumn improves everybody's yield without anything having been done better.

Anybody comparing this month's yield with last month's is comparing three
things at once. `malting_loss` is the one to compare, and it is why the dry
matter is worked at every stage rather than the weight.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.errors import ValidationError
from culmbin.units.mass import dry_matter, wet_weight

TYPICAL_MALTING_LOSS = 8.5
"""What this plant runs at on a spring barley pale ale piece.

Used for planning, when the piece has not come off the kiln yet and the
sales desk wants to know roughly what it will make.
"""

CULM_FRACTION_OF_LOSS = 0.55
"""How much of the malting loss ends up in the culm bin rather than in the air.

The rest went out of the chimney as carbon dioxide and water. This is the
split that lets the culm tonnage be checked against the loss, and a culm
weight a long way off it means the deculming screen is passing rootlets into
the malt or taking corns into the culm.
"""


@dataclass(frozen=True, slots=True)
class Balance:
    """The weights of one piece, all the way through.

    Everything here is measured except the dry matters, which are worked.
    The point of the record is that the four measured weights over-determine
    the piece, so they can be checked against each other.
    """

    charge_tonnes: float
    charge_moisture: float
    steep_out_tonnes: float
    steep_out_moisture: float
    malt_tonnes: float
    malt_moisture: float
    culm_tonnes: float

    def __post_init__(self) -> None:
        for name, weight in (
            ("charge", self.charge_tonnes),
            ("steep out", self.steep_out_tonnes),
            ("malt", self.malt_tonnes),
        ):
            if weight <= 0.0:
                raise ValidationError(f"the {name} weight is {weight} tonnes")
        if self.culm_tonnes < 0.0:
            raise ValidationError(f"the culm weight is {self.culm_tonnes} tonnes")
        if self.steep_out_moisture <= self.charge_moisture:
            raise ValidationError(
                f"steep out at {self.steep_out_moisture} is no wetter "
                f"than barley at {self.charge_moisture}"
            )
        if self.malt_moisture >= self.steep_out_moisture:
            raise ValidationError(
                f"malt at {self.malt_moisture} is no drier "
                f"than steep out at {self.steep_out_moisture}"
            )
        if self.charge_dry_tonnes < self.malt_dry_tonnes:
            raise ValidationError(
                "this piece came off the kiln with more barley in it than went in"
            )

    @property
    def charge_dry_tonnes(self) -> float:
        """The barley dry matter that went into the steep."""
        return dry_matter(self.charge_tonnes, self.charge_moisture)

    @property
    def steep_out_dry_tonnes(self) -> float:
        """The dry matter at steep out, which should be the charge and is not quite."""
        return dry_matter(self.steep_out_tonnes, self.steep_out_moisture)

    @property
    def malt_dry_tonnes(self) -> float:
        """The malt dry matter that came off the kiln."""
        return dry_matter(self.malt_tonnes, self.malt_moisture)

    @property
    def malting_loss(self) -> float:
        """Dry matter lost between the steep and the kiln, as a percentage."""
        return malting_loss(self.charge_dry_tonnes, self.malt_dry_tonnes)

    @property
    def yield_percent(self) -> float:
        """Malt tonnes out over barley tonnes in, both as they lie."""
        return self.malt_tonnes / self.charge_tonnes * 100.0

    @property
    def steep_discrepancy(self) -> float:
        """Dry matter apparently gained or lost in the steep, as a percentage.

        It should be nearly nothing. Steeping does lose a little to leaching
        and to the sprouts that start in the vessel, so a fraction of a
        percent is normal and two percent is a weighbridge or a moisture.
        """
        return (self.steep_out_dry_tonnes - self.charge_dry_tonnes) / self.charge_dry_tonnes * 100.0

    @property
    def culm_share_of_loss(self) -> float:
        """The culm as a share of the dry matter lost, as a fraction of one.

        Compare it with `CULM_FRACTION_OF_LOSS`. A long way off means the
        deculming screen is set wrong in one direction or the other.
        """
        lost = self.charge_dry_tonnes - self.malt_dry_tonnes
        if lost <= 0.0:
            raise ValidationError("this piece lost nothing, so the culm is not a share of anything")
        return self.culm_tonnes / lost


def malting_loss(barley_dry_tonnes: float, malt_dry_tonnes: float) -> float:
    """Dry matter lost between the steep and the kiln, as a percentage."""
    if barley_dry_tonnes <= 0.0:
        raise ValidationError(f"a piece charged with {barley_dry_tonnes} dry tonnes is not a piece")
    if malt_dry_tonnes < 0.0:
        raise ValidationError(f"a piece cannot make {malt_dry_tonnes} dry tonnes of malt")
    return (barley_dry_tonnes - malt_dry_tonnes) / barley_dry_tonnes * 100.0


def steep_out_tonnes(charge_tonnes: float, charge_moisture: float, steep_out: float) -> float:
    """What a charge weighs when it comes out of the steep.

    The dry matter is unchanged, so all this is the water going in.
    """
    return wet_weight(dry_matter(charge_tonnes, charge_moisture), steep_out)


def expected_malt_tonnes(
    charge_tonnes: float,
    charge_moisture: float,
    malt_moisture: float,
    loss_percent: float = TYPICAL_MALTING_LOSS,
) -> float:
    """What a charge is expected to make, for the sales desk.

    Takes the malting loss as a percentage rather than assuming it, because
    a distilling piece run long loses more than a lager piece run short and
    the difference is a lorry load a month.
    """
    if not 0.0 <= loss_percent < 100.0:
        raise ValidationError(f"a malting loss of {loss_percent} percent is not one")
    barley_dry = dry_matter(charge_tonnes, charge_moisture)
    malt_dry = barley_dry * (1.0 - loss_percent / 100.0)
    return wet_weight(malt_dry, malt_moisture)


def expected_culm_tonnes(
    charge_tonnes: float,
    charge_moisture: float,
    loss_percent: float = TYPICAL_MALTING_LOSS,
    culm_share: float = CULM_FRACTION_OF_LOSS,
) -> float:
    """What the culm bin is expected to take off one piece."""
    if not 0.0 <= culm_share <= 1.0:
        raise ValidationError(f"a culm share of {culm_share} is not a share")
    barley_dry = dry_matter(charge_tonnes, charge_moisture)
    return barley_dry * loss_percent / 100.0 * culm_share


def yield_percent(charge_tonnes: float, malt_tonnes: float) -> float:
    """The figure the office quotes, which carries both moistures with it."""
    if charge_tonnes <= 0.0:
        raise ValidationError(f"a charge of {charge_tonnes} tonnes is not a charge")
    return malt_tonnes / charge_tonnes * 100.0
