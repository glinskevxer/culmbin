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
from culmbin.units.scales import (
    NITROGEN_TO_PROTEIN,
    blend_kolbach_index,
    ebc_from_lovibond,
    hot_water_extract,
    kolbach_index,
    lintner_from_wk,
    lovibond_from_ebc,
    nitrogen_from_protein,
    protein_from_nitrogen,
    weighted_mean,
    wk_from_lintner,
)
from culmbin.units.season import (
    CONTRACT_YEAR_START_MONTH,
    CROP_YEAR_START_MONTH,
    DORMANCY_WEEKS,
    Window,
    contract_year,
    contract_year_window,
    crop_year,
    crop_year_window,
    dormancy_clears,
    is_new_crop,
    month_window,
    parse_date,
)

__all__ = [
    "CONTRACT_YEAR_START_MONTH",
    "CROP_YEAR_START_MONTH",
    "DORMANCY_WEEKS",
    "GROWTH_BASE_C",
    "MOISTURE_CEILING",
    "NITROGEN_TO_PROTEIN",
    "TEMPERATURE_CEILING_C",
    "TEMPERATURE_FLOOR_C",
    "Leg",
    "Window",
    "at_moisture",
    "blend_kolbach_index",
    "blend_moisture",
    "check_temperature",
    "contract_year",
    "contract_year_window",
    "crop_year",
    "crop_year_window",
    "degree_hours",
    "dormancy_clears",
    "dry_fraction",
    "dry_matter",
    "ebc_from_lovibond",
    "elapsed_hours",
    "format_duration",
    "hot_water_extract",
    "hours_at",
    "is_new_crop",
    "kolbach_index",
    "lintner_from_wk",
    "lovibond_from_ebc",
    "mean_temperature",
    "month_window",
    "nitrogen_from_protein",
    "parse_date",
    "parse_duration",
    "protein_from_nitrogen",
    "to_as_is_basis",
    "to_dry_basis",
    "weighted_mean",
    "wet_weight",
    "wk_from_lintner",
]
