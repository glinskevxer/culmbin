"""The gas meter commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke
from tests.cli.setup import a_stripped_piece, the_plant


def test_a_meter_reading_says_both_figures(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    result = invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert result.exit_code == 0
    assert "efficiency" in result.output
    assert "kWh a tonne" in result.output


def test_a_reading_outside_the_band_says_to_look_at_the_meter(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    result = invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "1200", on="2025-11-09")
    assert "outside what a kiln can do" in result.output


def test_a_piece_that_was_never_stripped_cannot_be_metered(invoke: Invoke) -> None:
    the_plant(invoke)
    invoke(
        "piece",
        "charge",
        "2025-118",
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        "S1",
        "--tonnes",
        "45",
        "--moisture",
        "12",
        "--programme",
        "p",
        "--schedule",
        "s",
        "--curve",
        "c",
        on="2025-11-03",
    )
    result = invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160")
    assert result.exit_code != 0


def test_a_run_shows_the_whole_energy_balance(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    result = invoke("gas", "show", "2025-118")
    assert "heat wanted" in result.output
    assert "gas burnt" in result.output


def test_a_stripped_piece_with_no_reading_is_waiting(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    assert "2025-118" in invoke("gas", "waiting").output


def test_a_metered_piece_is_not_waiting(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert "every stripped piece" in invoke("gas", "waiting").output


def test_a_suspect_run_is_listed(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "1200", on="2025-11-09")
    assert "2025-118" in invoke("gas", "suspect").output


def test_nothing_suspect_says_so(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert "inside the band" in invoke("gas", "suspect").output


def test_the_gas_page_prints(invoke: Invoke) -> None:
    the_plant(invoke)
    a_stripped_piece(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    result = invoke("gas", "list", on="2025-11-30")
    assert "kiln gas 2025-11-01..2025-11-30" in result.output


def test_the_gas_report_is_the_same_page(invoke: Invoke) -> None:
    the_plant(invoke)
    assert "kiln gas" in invoke("report", "gas", on="2025-11-30").output
