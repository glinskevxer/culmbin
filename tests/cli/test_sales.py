"""The sales commands, worked as a whole load."""

from __future__ import annotations

from tests.cli.conftest import Invoke

MALT = (
    "--result",
    "malt_moisture=4.2",
    "--result",
    "extract_fine=81.4",
    "--result",
    "colour=3.4",
)


def selling(invoke: Invoke, colour: str = "3.4") -> None:
    """A customer, a specification, a signed contract and a certified lot."""
    invoke("party", "add", "BRWY", "Sheldrake Brewing", "--role", "customer", on="2016-02-01")
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved", on="2018-12-01")
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", on="1998-04-01")
    invoke("recipe", "programme", "p", "--style", "lager", "--leg", "wet:8:14", "--target", "44.5")
    invoke("recipe", "schedule", "s", "--style", "lager", "--target", "1200")
    invoke(
        "recipe",
        "curve",
        "c",
        "--style",
        "lager",
        "--step",
        "dry:10:60",
        "--step",
        "cure:4:85",
        "--target",
        "4.2",
    )
    invoke(
        "piece",
        "charge",
        "2025-118",
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "lager",
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
    invoke("bin", "add", "B04", "--capacity", "220")
    invoke("bin", "receive", "B04", "2025-118", "--tonnes", "60", "--moisture", "4.2")
    invoke("bin", "seal", "B04")
    invoke("lot", "seal", "L-1", "--bin", "B04", on="2025-11-13")
    results = tuple(item if item != "colour=3.4" else f"colour={colour}" for item in MALT)
    invoke("lot", "certify", "L-1", "M-1", *results, on="2025-11-13")
    invoke("spec", "add", "lager 2025", "--clause", "colour=2.5..4.5")
    invoke(
        "contract",
        "add",
        "C-1",
        "BRWY",
        "--spec",
        "lager 2025",
        "--tonnes",
        "2400",
        "--price",
        "398.00",
        "--from",
        "2025-10-01",
        "--to",
        "2026-09-30",
        on="2025-06-02",
    )
    invoke("contract", "sign", "C-1")


def test_a_contract_starts_in_draft_and_takes_nothing(invoke: Invoke) -> None:
    selling(invoke)
    invoke("contract", "close", "C-1")
    result = invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    assert result.exit_code != 0


def test_a_signed_contract_shows_all_three_tonnages(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke("contract", "show", "C-1")
    assert "signed     2400.0t" in result.output
    assert "delivered  0.0t" in result.output
    assert "committed  0.0t" in result.output


def test_a_clean_lot_is_allocated(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    assert result.exit_code == 0
    assert "32.00t left on L-1" in result.output


def test_a_lot_outside_the_specification_says_which_clause(invoke: Invoke) -> None:
    selling(invoke, colour="6.2")
    result = invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    assert result.exit_code != 0
    assert "colour" in str(result.exception)


def test_more_than_the_lot_has_is_refused(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "80", on="2025-11-20")
    assert result.exit_code != 0


def test_loading_says_what_the_contract_tonne_comes_to(invoke: Invoke) -> None:
    """Drier malt draws the contract down by more than it weighs."""
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("ship", "load", "S-1", "--tonnes", "28", "--moisture", "4.2", on="2025-11-20")
    assert "28.088 contract tonnes" in result.output


def test_a_despatched_load_is_on_the_contract_position(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    invoke("ship", "load", "S-1", "--tonnes", "28", "--moisture", "4.5", on="2025-11-20")
    invoke("ship", "despatch", "S-1")
    result = invoke("contract", "show", "C-1")
    assert "delivered  28.0t" in result.output


def test_a_planned_load_is_committed_and_not_delivered(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("contract", "show", "C-1")
    assert "delivered  0.0t" in result.output
    assert "committed  28.1t" in result.output


def test_cancelling_puts_the_malt_back(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("ship", "cancel", "S-1")
    assert "60.00t back on L-1" in result.output


def test_a_despatched_load_does_not_change_again(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    invoke("ship", "load", "S-1", "--tonnes", "28", "--moisture", "4.2", on="2025-11-20")
    invoke("ship", "despatch", "S-1")
    assert invoke("ship", "cancel", "S-1").exit_code != 0


def test_a_call_goes_against_a_contract(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke(
        "call",
        "add",
        "K-1",
        "C-1",
        "--tonnes",
        "200",
        "--from",
        "2026-04-06",
        "--to",
        "2026-04-10",
        on="2025-11-20",
    )
    assert result.exit_code == 0
    assert "K-1" in invoke("call", "list").output


def test_a_call_past_the_contract_tonnage_is_refused(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke(
        "call",
        "add",
        "K-1",
        "C-1",
        "--tonnes",
        "3000",
        "--from",
        "2026-04-06",
        "--to",
        "2026-04-10",
        on="2025-11-20",
    )
    assert result.exit_code != 0


def test_the_diary_shows_what_has_not_gone(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("ship", "diary", "--from", "2025-11-17", "--to", "2025-11-21")
    assert "S-1" in result.output
    assert "planned" in result.output


def test_the_diary_defaults_to_a_week_from_today(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("ship", "diary", on="2025-11-18")
    assert "S-1" in result.output


def test_a_shipment_shows_both_tonnages(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    result = invoke("ship", "show", "S-1")
    assert "weighbridge 28.00t" in result.output
    assert "contract   28.088t" in result.output


def test_the_shipment_list_narrows_by_lot(invoke: Invoke) -> None:
    selling(invoke)
    invoke("ship", "allocate", "S-1", "C-1", "L-1", "--tonnes", "28", on="2025-11-20")
    assert "S-1" in invoke("ship", "list", "--lot", "L-1").output
    assert "S-1" not in invoke("ship", "list", "--lot", "L-9").output


def test_the_contract_page_prints(invoke: Invoke) -> None:
    selling(invoke)
    assert "contract position" in invoke("contract", "list").output


def test_the_cover_page_prints(invoke: Invoke) -> None:
    selling(invoke)
    result = invoke("contract", "cover")
    assert result.exit_code == 0
    assert "free to sell" in result.output


def test_the_cover_report_is_the_same_page(invoke: Invoke) -> None:
    selling(invoke)
    assert "cover" in invoke("report", "cover").output
