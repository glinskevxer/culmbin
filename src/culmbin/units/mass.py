"""Weight and moisture.

Everything in a malthouse is weighed wet and paid for dry, so these six
functions turn up in nearly every calculation the package does. They are
deliberately dull and deliberately strict: a moisture outside what grain can
physically hold is a mistake somewhere upstream, and continuing with it
produces a number that looks plausible and is wrong.

Weights are tonnes throughout unless the caller says otherwise. Moistures and
every other percentage are whole percent, so 12.5 not 0.125.
"""

from __future__ import annotations

from collections.abc import Sequence

from culmbin.errors import ValidationError

MOISTURE_CEILING = 60.0
"""Above this nothing in the building is grain any more, it is porridge.

Steep-out barley sits around 45 percent, which is the wettest thing the
package ever sees, so the ceiling has plenty of room over the real range and
still catches a fraction that was passed as a percentage.
"""


def _check_moisture(moisture_pct: float, field: str = "moisture") -> float:
    """Return the moisture, or raise if it is not one."""
    if moisture_pct < 0.0:
        raise ValidationError(f"{field} {moisture_pct:.2f} is below zero")
    if moisture_pct >= MOISTURE_CEILING:
        raise ValidationError(
            f"{field} {moisture_pct:.2f} is at or above the {MOISTURE_CEILING:.0f} ceiling"
        )
    return moisture_pct


def _check_weight(weight: float, field: str = "weight") -> float:
    """Return the weight, or raise if it is negative."""
    if weight < 0.0:
        raise ValidationError(f"{field} {weight:.3f} is negative")
    return weight


def dry_fraction(moisture_pct: float) -> float:
    """The proportion of a weight that is dry matter, as a fraction of one.

    Twelve percent moisture is 0.88 dry matter. This is the multiplier every
    other function here is built out of.
    """
    return (100.0 - _check_moisture(moisture_pct)) / 100.0


def dry_matter(weight: float, moisture_pct: float) -> float:
    """The dry tonnes in a wet weight."""
    return _check_weight(weight) * dry_fraction(moisture_pct)


def wet_weight(dry_weight: float, moisture_pct: float) -> float:
    """The wet tonnes that carry a given dry weight at a given moisture."""
    return _check_weight(dry_weight, "dry weight") / dry_fraction(moisture_pct)


def at_moisture(weight: float, from_pct: float, to_pct: float) -> float:
    """Restate a weight as the weight it would be at another moisture.

    This is the moisture tonne, and it is how a contract is drawn down. A
    contract written at 4.5 percent that is shipped at 4.2 percent ships
    fewer physical tonnes than it credits, and both numbers are correct.
    """
    return wet_weight(dry_matter(weight, from_pct), to_pct)


def to_dry_basis(value_pct: float, moisture_pct: float) -> float:
    """Restate a percentage measured as it lies onto dry matter.

    Extract, protein and beta-glucan are all reported both ways, and a
    specification names which one it means. The conversion needs the moisture
    from the same analysis, not the moisture the lot has today.
    """
    if value_pct < 0.0:
        raise ValidationError(f"value {value_pct:.2f} is negative")
    return value_pct / dry_fraction(moisture_pct)


def to_as_is_basis(value_dry_pct: float, moisture_pct: float) -> float:
    """Restate a dry matter percentage onto the weight as it lies."""
    if value_dry_pct < 0.0:
        raise ValidationError(f"value {value_dry_pct:.2f} is negative")
    return value_dry_pct * dry_fraction(moisture_pct)


def blend_moisture(parts: Sequence[tuple[float, float]]) -> float:
    """The moisture of a pile made by tipping several weights together.

    Each part is a wet weight and its moisture. Water averages over the wet
    weight because that is what water is a fraction of, which makes this the
    one blend in the package that is not worked on dry matter.
    """
    if not parts:
        raise ValidationError("a blend needs at least one part")
    total = 0.0
    water = 0.0
    for weight, moisture in parts:
        _check_weight(weight)
        _check_moisture(moisture)
        total += weight
        water += weight * moisture / 100.0
    if total == 0.0:
        raise ValidationError("a blend of nothing has no moisture")
    return water / total * 100.0
