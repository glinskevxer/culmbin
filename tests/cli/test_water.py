"""The water meter commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke
from tests.cli.setup import a_cast_piece, the_plant


def test_a_reading_says_all_three_numbers(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    result = invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    assert result.exit_code == 0
    assert "the barley kept" in result.output
    assert "went to drain" in result.output


def test_a_heavy_steep_says_it_is_a_bill(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    result = invoke("water", "record", "2025-118", "--m3", "600", on="2025-11-05")
    assert "a bill rather than a fault" in result.output


def test_a_piece_that_was_never_cast_cannot_be_metered(invoke: Invoke) -> None:
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
    assert invoke("water", "record", "2025-118", "--m3", "150").exit_code != 0


def test_a_reading_shows_the_whole_balance(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("water", "show", "2025-118")
    assert "metered   150.0 m3" in result.output
    assert "to drain" in result.output


def test_a_cast_piece_with_no_reading_is_waiting(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    assert "2025-118" in invoke("water", "waiting").output


def test_a_metered_piece_is_not_waiting(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    assert "every cast piece" in invoke("water", "waiting").output


def test_the_water_page_prints(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("water", "list", on="2025-11-30")
    assert "steep water 2025-11-01..2025-11-30" in result.output
    assert "m3 a tonne" in result.output


def test_a_month_with_nothing_metered_says_so(invoke: Invoke) -> None:
    the_plant(invoke)
    assert "nobody metered a steep." in invoke("water", "list", on="2025-11-30").output


def test_the_month_page_carries_the_water(invoke: Invoke) -> None:
    the_plant(invoke)
    a_cast_piece(invoke)
    invoke("water", "record", "2025-118", "--m3", "150", on="2025-11-05")
    result = invoke("report", "month", on="2025-11-30")
    assert "water metered" in result.output
    assert "water to drain" in result.output
