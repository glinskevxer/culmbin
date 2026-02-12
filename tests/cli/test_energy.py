"""The gas meter commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke


def plant(invoke: Invoke) -> None:
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved", on="2018-12-01")
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", on="1998-04-01")
    invoke(
        "vessel",
        "add",
        "G1",
        "box 1",
        "--kind",
        "box",
        "--area",
        "170",
        "--depth",
        "90",
        on="1998-04-01",
    )
    invoke(
        "vessel",
        "add",
        "K1",
        "kiln 1",
        "--kind",
        "kiln",
        "--area",
        "140",
        "--depth",
        "100",
        on="1998-04-01",
    )
    invoke(
        "recipe", "programme", "p", "--style", "pale_ale", "--leg", "wet:8:14", "--target", "44.5"
    )
    invoke("recipe", "schedule", "s", "--style", "pale_ale", "--target", "1200")
    invoke(
        "recipe",
        "curve",
        "c",
        "--style",
        "pale_ale",
        "--step",
        "dry:10:60",
        "--step",
        "cure:4:85",
        "--target",
        "4.2",
    )


def stripped(invoke: Invoke, code: str = "2025-118") -> None:
    invoke(
        "piece",
        "charge",
        code,
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
    invoke(
        "piece",
        "cast",
        code,
        "--into",
        "G1",
        "--tonnes",
        "71.8",
        "--moisture",
        "44.8",
        "--depth",
        "85",
        on="2025-11-05",
    )
    invoke("piece", "kiln", code, "--into", "K1", on="2025-11-08")
    invoke(
        "piece",
        "strip",
        code,
        "--malt",
        "37.9",
        "--moisture",
        "4.4",
        "--culm",
        "1.9",
        on="2025-11-09",
    )


def test_a_meter_reading_says_both_figures(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    result = invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert result.exit_code == 0
    assert "efficiency" in result.output
    assert "kWh a tonne" in result.output


def test_a_reading_outside_the_band_says_to_look_at_the_meter(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    result = invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "1200", on="2025-11-09")
    assert "outside what a kiln can do" in result.output


def test_a_piece_that_was_never_stripped_cannot_be_metered(invoke: Invoke) -> None:
    plant(invoke)
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
    plant(invoke)
    stripped(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    result = invoke("gas", "show", "2025-118")
    assert "heat wanted" in result.output
    assert "gas burnt" in result.output


def test_a_stripped_piece_with_no_reading_is_waiting(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    assert "2025-118" in invoke("gas", "waiting").output


def test_a_metered_piece_is_not_waiting(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert "every stripped piece" in invoke("gas", "waiting").output


def test_a_suspect_run_is_listed(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "1200", on="2025-11-09")
    assert "2025-118" in invoke("gas", "suspect").output


def test_nothing_suspect_says_so(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    assert "inside the band" in invoke("gas", "suspect").output


def test_the_gas_page_prints(invoke: Invoke) -> None:
    plant(invoke)
    stripped(invoke)
    invoke("gas", "record", "2025-118", "--kiln", "K1", "--m3", "3160", on="2025-11-09")
    result = invoke("gas", "list", on="2025-11-30")
    assert "kiln gas 2025-11-01..2025-11-30" in result.output


def test_the_gas_report_is_the_same_page(invoke: Invoke) -> None:
    plant(invoke)
    assert "kiln gas" in invoke("report", "gas", on="2025-11-30").output
