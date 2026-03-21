"""The month end walk, and what does not add up."""

from __future__ import annotations

import datetime as dt

import pytest

from culmbin.process.floor import cast, charge, load_kiln, strip_kiln
from culmbin.process.reconcile import (
    LOSS_CEILING,
    LOSS_FLOOR,
    Reconciliation,
    drawn_against_charged,
    reconcile,
)
from culmbin.store.book import Book
from culmbin.store.pieces import record_source
from culmbin.units.season import Window
from tests.support.records import a_piece

MONTH = Window(dt.date(2025, 11, 1), dt.date(2025, 11, 30))
CAST = dt.date(2025, 11, 5)
KILNED = dt.date(2025, 11, 9)
PROGRAMME = "pale ale two stand"
SCHEDULE = "pale ale four day"
CURVE = "pale ale 18 hour"


def a_month(plant: Book, code: str = "2025-118", malt: float = 37.9) -> None:
    charge(plant, a_piece(code), PROGRAMME, SCHEDULE, CURVE)
    cast(plant, code, "G1", CAST, 71.8, 44.8, depth_cm=85.0)
    load_kiln(plant, code, "K1", dt.date(2025, 11, 8))
    strip_kiln(plant, code, KILNED, malt, 4.4, 1.9)


def figures(**kwargs: float) -> Reconciliation:
    fields: dict[str, object] = {
        "window": MONTH,
        "graded_tonnes": 100.0,
        "tipped_tonnes": 100.0,
        "charged_tonnes": 45.0,
        "charged_dry": 39.6,
        "malt_tonnes": 37.9,
        "malt_dry": 36.24,
        "culm_tonnes": 1.9,
    }
    fields.update(kwargs)
    return Reconciliation(**fields)  # type: ignore[arg-type]


def test_a_month_with_nothing_in_it_reconciles_to_nothing(plant: Book) -> None:
    walk = reconcile(plant, MONTH)
    assert walk.charged_tonnes == pytest.approx(0.0)
    assert walk.malting_loss == pytest.approx(0.0)
    assert walk.yield_percent == pytest.approx(0.0)
    assert walk.loss_is_credible


def test_a_finished_piece_shows_up_in_the_walk(plant: Book) -> None:
    a_month(plant)
    walk = reconcile(plant, MONTH)
    assert walk.charged_tonnes == pytest.approx(45.0)
    assert walk.malt_tonnes == pytest.approx(37.9)
    assert walk.culm_tonnes == pytest.approx(1.9)


def test_a_normal_month_has_a_credible_malting_loss(plant: Book) -> None:
    a_month(plant)
    walk = reconcile(plant, MONTH)
    assert LOSS_FLOOR <= walk.malting_loss <= LOSS_CEILING
    assert walk.loss_is_credible
    assert "nothing in the month needs explaining" in walk.notes()


def test_a_loss_outside_the_band_points_at_a_weighbridge(plant: Book) -> None:
    """Outside it, something is wrong with a weighbridge and not the malting."""
    a_month(plant, malt=30.0)
    walk = reconcile(plant, MONTH)
    assert not walk.loss_is_credible
    assert any("look at a weighbridge" in note for note in walk.notes())


def test_a_piece_outside_the_window_is_left_out(plant: Book) -> None:
    charge(
        plant,
        a_piece("2025-200", started=dt.date(2025, 12, 3)),
        PROGRAMME,
        SCHEDULE,
        CURVE,
    )
    assert reconcile(plant, MONTH).charged_tonnes == pytest.approx(0.0)


def test_barley_graded_and_not_tipped_is_the_pit() -> None:
    walk = figures(tipped_tonnes=80.0)
    assert walk.pit_gap == pytest.approx(20.0)
    assert any("barley in the pit" in note for note in walk.notes())


def test_a_month_with_everything_tipped_has_no_pit_gap() -> None:
    assert figures().pit_gap == pytest.approx(0.0)


def test_the_yield_is_malt_out_over_barley_in() -> None:
    assert figures().yield_percent == pytest.approx(37.9 / 45.0 * 100.0)


def test_the_loss_is_worked_on_dry_matter() -> None:
    """It is the only quantity that survives the whole building."""
    assert figures().malting_loss == pytest.approx((39.6 - 36.24) / 39.6 * 100.0)


def test_the_culm_share_is_of_what_was_lost() -> None:
    assert figures().culm_share == pytest.approx(1.9 / (39.6 - 36.24))


def test_a_month_that_lost_nothing_has_no_culm_share() -> None:
    assert figures(malt_dry=39.6).culm_share == pytest.approx(0.0)


def test_a_piece_charged_without_going_through_the_yard_shows_a_gap(plant: Book) -> None:
    """It is legal and it is worth knowing about."""
    charge(plant, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    assert drawn_against_charged(plant, MONTH) == pytest.approx(45.0)


def test_a_piece_with_its_sources_recorded_closes_the_gap(plant: Book) -> None:
    charge(plant, a_piece("2025-118"), PROGRAMME, SCHEDULE, CURVE)
    plant.execute(
        "INSERT INTO party (code, name, role, opened) "
        "VALUES ('HOLB', 'Holbeach', 'grower', '2011-06-01')"
    )
    plant.execute(
        "INSERT INTO purchase (code, party, variety, crop_year, tonnes, window_start, "
        "window_end, standard, price_per_tonne, signed) VALUES "
        "('P-1', 'HOLB', 'LAUR', 2025, 480.0, '2025-09-01', '2025-11-30', "
        "'malting 2025', '232.50', '2025-03-12')"
    )
    plant.execute(
        "INSERT INTO delivery (ticket, purchase, party, arrived, gross_kg, tare_kg) "
        "VALUES ('W-1', 'P-1', 'HOLB', '2025-09-18', 43820.0, 15640.0)"
    )
    record_source(plant, "2025-118", "W-1", 45.0)
    assert drawn_against_charged(plant, MONTH) == pytest.approx(0.0)
