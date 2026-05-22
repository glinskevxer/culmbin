"""The water meter commands."""

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


def cast(invoke: Invoke, code: str = "2025-118") -> None:
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


def test_a_reading_says_all_three_numbers(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    result = invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    assert result.exit_code == 0
    assert "the barley kept" in result.output
    assert "went to drain" in result.output


def test_a_heavy_steep_says_it_is_a_bill(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    result = invoke("water", "record", "2025-118", "--m3", "600", on="2025-11-05")
    assert "a bill rather than a fault" in result.output


def test_a_piece_that_was_never_cast_cannot_be_metered(invoke: Invoke) -> None:
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
    assert invoke("water", "record", "2025-118", "--m3", "150").exit_code != 0


def test_a_reading_shows_the_whole_balance(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("water", "show", "2025-118")
    assert "metered   150.0 m3" in result.output
    assert "to drain" in result.output


def test_a_cast_piece_with_no_reading_is_waiting(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    assert "2025-118" in invoke("water", "waiting").output


def test_a_metered_piece_is_not_waiting(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    assert "every cast piece" in invoke("water", "waiting").output


def test_the_water_page_prints(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("water", "list", on="2025-11-30")
    assert "steep water 2025-11-01..2025-11-30" in result.output
    assert "m3 a tonne" in result.output


def test_a_month_with_nothing_metered_says_so(invoke: Invoke) -> None:
    plant(invoke)
    assert "nobody metered a steep." in invoke("water", "list", on="2025-11-30").output


def test_the_month_page_carries_the_water(invoke: Invoke) -> None:
    plant(invoke)
    cast(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("report", "month", on="2025-11-30")
    assert "water metered" in result.output
    assert "water to drain" in result.output
