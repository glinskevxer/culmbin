"""The barley yard commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke

GOOD = (
    "--result",
    "moisture=12.5",
    "--result",
    "screenings=1.4",
    "--result",
    "germ_capacity=99.0",
    "--result",
    "germ_energy=98.0",
    "--result",
    "admixture=0.4",
    "--result",
    "nitrogen=1.62",
)


def yard(invoke: Invoke) -> None:
    """A grower, a purchase, a plant and a silo."""
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved", on="2018-12-01")
    invoke("standard", "add", "malting 2025")
    invoke(
        "purchase",
        "add",
        "P-1",
        "HOLB",
        "LAUR",
        "--tonnes",
        "480",
        "--price",
        "232.50",
        "--standard",
        "malting 2025",
        "--crop",
        "2025",
        "--from",
        "2025-09-01",
        "--to",
        "2025-11-30",
        on="2025-03-12",
    )
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", on="1998-04-01")
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
    invoke("silo", "add", "SL1", "--capacity", "400")


def lorry(invoke: Invoke, ticket: str) -> None:
    invoke(
        "delivery",
        "add",
        ticket,
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        "--harvested",
        "2025-08-14",
        on="2025-09-18",
    )
    invoke("delivery", "sample", ticket, f"B-{ticket}", *GOOD, on="2025-09-19")
    invoke("delivery", "grade", ticket, on="2025-09-19")


def test_a_silo_goes_in_and_is_on_the_page(invoke: Invoke) -> None:
    yard(invoke)
    result = invoke("silo", "list")
    assert result.exit_code == 0
    assert "SL1" in result.output


def test_a_tipped_load_shows_what_is_in_the_silo(invoke: Invoke) -> None:
    yard(invoke)
    lorry(invoke, "W-1")
    result = invoke("silo", "tip", "SL1", "W-1", on="2025-09-19")
    assert result.exit_code == 0
    assert "28.18t LAUR" in result.output


def test_a_rejected_load_cannot_be_tipped(invoke: Invoke) -> None:
    yard(invoke)
    invoke(
        "delivery",
        "add",
        "W-9",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        "--harvested",
        "2025-08-14",
        on="2025-09-18",
    )
    weak = tuple(item if item != "germ_capacity=99.0" else "germ_capacity=90.0" for item in GOOD)
    invoke("delivery", "sample", "W-9", "B-W-9", *weak, on="2025-09-19")
    invoke("delivery", "grade", "W-9", on="2025-09-19")
    assert invoke("silo", "tip", "SL1", "W-9", on="2025-09-19").exit_code != 0


def test_the_silo_page_shows_which_loads_are_in_it(invoke: Invoke) -> None:
    yard(invoke)
    lorry(invoke, "W-1")
    lorry(invoke, "W-2")
    invoke("silo", "tip", "SL1", "W-1", on="2025-09-19")
    invoke("silo", "tip", "SL1", "W-2", on="2025-09-19")
    result = invoke("silo", "show", "SL1")
    assert "W-1" in result.output
    assert "W-2" in result.output


def test_a_dry_run_says_what_a_charge_would_carry(invoke: Invoke) -> None:
    yard(invoke)
    lorry(invoke, "W-1")
    lorry(invoke, "W-2")
    invoke("silo", "tip", "SL1", "W-1", on="2025-09-19")
    invoke("silo", "tip", "SL1", "W-2", on="2025-09-19")
    result = invoke(
        "silo",
        "draw",
        "SL1",
        "2025-118",
        "--tonnes",
        "40",
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        "S1",
        "--programme",
        "p",
        "--schedule",
        "s",
        "--curve",
        "c",
        "--dry-run",
    )
    assert "W-1" in result.output
    assert "20.000t" in result.output
    assert "2025-118" not in invoke("piece", "list").output


def test_a_charge_out_of_a_silo_takes_its_moisture_from_it(invoke: Invoke) -> None:
    yard(invoke)
    lorry(invoke, "W-1")
    lorry(invoke, "W-2")
    invoke("silo", "tip", "SL1", "W-1", on="2025-09-19")
    invoke("silo", "tip", "SL1", "W-2", on="2025-09-19")
    result = invoke(
        "silo",
        "draw",
        "SL1",
        "2025-118",
        "--tonnes",
        "40",
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        "S1",
        "--programme",
        "p",
        "--schedule",
        "s",
        "--curve",
        "c",
        on="2025-11-03",
    )
    assert result.exit_code == 0
    assert "12.50%" in result.output
    assert "W-1" in invoke("piece", "show", "2025-118").output


def test_a_charge_of_the_wrong_variety_is_refused(invoke: Invoke) -> None:
    yard(invoke)
    invoke("variety", "add", "DIAB", "Diablo", "--approval", "approved", on="2019-12-01")
    lorry(invoke, "W-1")
    invoke("silo", "tip", "SL1", "W-1", on="2025-09-19")
    result = invoke(
        "silo",
        "draw",
        "SL1",
        "2025-118",
        "--tonnes",
        "20",
        "--variety",
        "DIAB",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        "S1",
        "--programme",
        "p",
        "--schedule",
        "s",
        "--curve",
        "c",
        on="2025-11-03",
    )
    assert result.exit_code != 0


def test_sweeping_an_empty_silo_clears_the_mark(invoke: Invoke) -> None:
    yard(invoke)
    result = invoke("silo", "sweep", "SL1")
    assert "mark cleared" in result.output


def test_the_yard_report_is_the_silo_list(invoke: Invoke) -> None:
    yard(invoke)
    assert "barley yard" in invoke("report", "yard").output
