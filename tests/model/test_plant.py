"""Vessels and the plant they make up.

The distinction these tests are mostly about is that a steep is a volume and
a box is an area, and that the package refuses to answer a question that only
makes sense for the other one.
"""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.errors import NotFoundError, ValidationError
from culmbin.model.enums import VesselKind
from culmbin.model.plant import BED_DENSITY_T_PER_M3, Vessel, plant_of

COMMISSIONED = dt.date(1998, 4, 1)


def steep(code: str = "S1", **kwargs: object) -> Vessel:
    fields: dict[str, object] = {
        "name": f"steep {code}",
        "kind": VesselKind.STEEP,
        "commissioned": COMMISSIONED,
        "charge_limit_t": 45.0,
    }
    fields.update(kwargs)
    return Vessel(code=code, **fields)  # type: ignore[arg-type]


def box(code: str = "G1", **kwargs: object) -> Vessel:
    fields: dict[str, object] = {
        "name": f"box {code}",
        "kind": VesselKind.BOX,
        "commissioned": COMMISSIONED,
        "floor_area_m2": 120.0,
        "depth_limit_cm": 90.0,
    }
    fields.update(kwargs)
    return Vessel(code=code, **fields)  # type: ignore[arg-type]


def test_a_steep_is_sized_by_volume() -> None:
    assert not steep().sized_by_area
    assert steep().limit_t == pytest.approx(45.0)


def test_a_box_is_sized_by_area() -> None:
    assert box().sized_by_area


def test_a_bed_holds_area_times_depth_times_density() -> None:
    """120 square metres at 90cm is 108 cubic metres, which is 59.4 tonnes."""
    assert box().tonnes_at_depth(90.0) == pytest.approx(120.0 * 0.9 * BED_DENSITY_T_PER_M3)


def test_a_shallower_bed_holds_less() -> None:
    assert box().tonnes_at_depth(60.0) < box().tonnes_at_depth(90.0)


def test_a_box_limit_is_its_deepest_bed() -> None:
    assert box().limit_t == pytest.approx(box().tonnes_at_depth(90.0))


def test_a_bed_deeper_than_the_vessel_runs_is_refused() -> None:
    with pytest.raises(ValidationError, match="deeper than"):
        box().tonnes_at_depth(120.0)


def test_a_bed_of_no_depth_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a bed"):
        box().tonnes_at_depth(0.0)


def test_asking_a_steep_about_its_bed_is_refused() -> None:
    with pytest.raises(ValidationError, match="has no bed"):
        steep().tonnes_at_depth(60.0)


def test_a_steep_with_a_bed_depth_is_refused() -> None:
    with pytest.raises(ValidationError, match="no bed depth"):
        Vessel(
            code="S1",
            name="steep 1",
            kind=VesselKind.STEEP,
            commissioned=COMMISSIONED,
            charge_limit_t=45.0,
            depth_limit_cm=90.0,
        )


def test_a_box_with_a_charge_limit_is_refused() -> None:
    with pytest.raises(ValidationError, match="no charge limit"):
        Vessel(
            code="G1",
            name="box 1",
            kind=VesselKind.BOX,
            commissioned=COMMISSIONED,
            floor_area_m2=120.0,
            depth_limit_cm=90.0,
            charge_limit_t=59.0,
        )


def test_a_box_without_an_area_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs an area and a depth"):
        Vessel(code="G1", name="box 1", kind=VesselKind.BOX, commissioned=COMMISSIONED)


def test_a_steep_without_a_charge_limit_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs a charge limit"):
        Vessel(code="S1", name="steep 1", kind=VesselKind.STEEP, commissioned=COMMISSIONED)


def test_a_vessel_of_no_size_is_refused() -> None:
    with pytest.raises(ValidationError, match="charge limit of nothing"):
        steep(charge_limit_t=0.0)
    with pytest.raises(ValidationError, match="area or depth of nothing"):
        box(floor_area_m2=0.0)


def test_a_vessel_needs_a_code() -> None:
    with pytest.raises(ValidationError, match="needs a code"):
        steep(" ")


def test_a_charge_that_fits_fits() -> None:
    assert steep().holds(44.0)
    assert steep().holds(45.0)
    assert not steep().holds(46.0)


def test_a_charge_of_nothing_is_not_a_charge() -> None:
    with pytest.raises(ValidationError, match="not a charge"):
        steep().holds(0.0)


def test_a_vessel_is_out_of_service_before_it_is_commissioned() -> None:
    assert not steep().in_service_on(dt.date(1998, 3, 31))
    assert steep().in_service_on(COMMISSIONED)


def test_a_retired_vessel_is_out_of_service_from_the_day_it_went() -> None:
    retired = steep(retired=dt.date(2024, 6, 1))
    assert retired.in_service_on(dt.date(2024, 5, 31))
    assert not retired.in_service_on(dt.date(2024, 6, 1))


def test_a_vessel_retired_before_it_was_commissioned_is_refused() -> None:
    with pytest.raises(ValidationError, match="retired before"):
        steep(retired=dt.date(1997, 1, 1))


def test_a_plant_looks_a_vessel_up() -> None:
    plant = plant_of([steep("S1"), steep("S2"), box("G1")])
    assert plant["S2"].name == "steep S2"
    assert len(plant) == 3


def test_a_vessel_that_is_not_there_says_what_was_asked_for() -> None:
    with pytest.raises(NotFoundError, match="S9"):
        plant_of([steep("S1")])["S9"]


def test_two_vessels_with_one_code_are_refused() -> None:
    with pytest.raises(ValidationError, match="share the code S1"):
        plant_of([steep("S1"), box("S1")])


def test_a_plant_lists_by_kind_in_the_order_it_was_given() -> None:
    plant = plant_of([steep("S1"), box("G1"), steep("S2")])
    assert [vessel.code for vessel in plant.of_kind(VesselKind.STEEP)] == ["S1", "S2"]
    assert [vessel.code for vessel in plant.of_kind(VesselKind.FLOOR)] == []


def test_a_plant_lists_what_was_in_service_on_a_day() -> None:
    plant = plant_of([steep("S1"), steep("S2", retired=dt.date(2024, 6, 1))])
    codes = [vessel.code for vessel in plant.in_service_on(dt.date(2024, 7, 1))]
    assert codes == ["S1"]


def test_a_plant_iterates_in_order() -> None:
    plant = plant_of([steep("S1"), box("G1")])
    assert [vessel.code for vessel in plant] == ["S1", "G1"]
