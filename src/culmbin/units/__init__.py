"""Conversions. This layer imports nothing from the rest of the package.

Everything here is a function of its arguments. There is no state, no clock
and no book. If something in here needs to know what day it is or what a lot
weighs, it belongs a layer up.
"""

from __future__ import annotations

from culmbin.units.clock import (
    GROWTH_BASE_C,
    TEMPERATURE_CEILING_C,
    TEMPERATURE_FLOOR_C,
    Leg,
    check_temperature,
    degree_hours,
    elapsed_hours,
    format_duration,
    hours_at,
    mean_temperature,
    parse_duration,
)
from culmbin.units.mass import (
    MOISTURE_CEILING,
    at_moisture,
    blend_moisture,
    dry_fraction,
    dry_matter,
    to_as_is_basis,
    to_dry_basis,
    wet_weight,
)

__all__ = [
    "GROWTH_BASE_C",
    "MOISTURE_CEILING",
    "TEMPERATURE_CEILING_C",
    "TEMPERATURE_FLOOR_C",
    "Leg",
    "at_moisture",
    "blend_moisture",
    "check_temperature",
    "degree_hours",
    "dry_fraction",
    "dry_matter",
    "elapsed_hours",
    "format_duration",
    "hours_at",
    "mean_temperature",
    "parse_duration",
    "to_as_is_basis",
    "to_dry_basis",
    "wet_weight",
]
