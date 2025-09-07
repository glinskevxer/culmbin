"""The intake commands, worked as a whole lorry."""

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


def setup(invoke: Invoke) -> None:
    """A grower, a variety, a standard and a purchase."""
    invoke(
        "party",
        "add",
        "HOLB",
        "Holbeach Grange",
        "--role",
        "grower",
        "--holding",
        "12/345",
        on="2011-06-01",
    )
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


def tip(invoke: Invoke, ticket: str = "W-1") -> None:
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


def test_a_standard_goes_in_and_comes_back(invoke: Invoke) -> None:
    invoke("standard", "add", "malting 2025")
    result = invoke("standard", "list")
    assert "malting 2025" in result.output
    assert "1.35-1.85" in result.output


def test_the_standard_page_keeps_rejections_apart_from_deductions(invoke: Invoke) -> None:
    invoke("standard", "add", "malting 2025")
    result = invoke("standard", "show", "malting 2025")
    assert "rejects at" in result.output
    assert "deducts" in result.output


def test_copying_a_standard_starts_next_season(invoke: Invoke) -> None:
    invoke("standard", "add", "malting 2025")
    invoke("standard", "copy", "malting 2025", "malting 2026")
    assert "malting 2026" in invoke("standard", "list").output


def test_a_purchase_shows_what_is_left(invoke: Invoke) -> None:
    setup(invoke)
    result = invoke("purchase", "show", "P-1")
    assert "left      480.00" in result.output
    assert "111600.00" in result.output


def test_a_delivery_outside_the_window_is_refused(invoke: Invoke) -> None:
    setup(invoke)
    result = invoke(
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
        on="2025-12-04",
    )
    assert result.exit_code != 0


def test_a_lorry_goes_in_and_is_on_the_waiting_list(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    result = invoke("delivery", "waiting", on="2025-09-19")
    assert "W-1" in result.output
    assert "sample" in result.output


def test_a_sampled_lorry_is_waiting_for_a_grading(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    invoke("delivery", "sample", "W-1", "B-1", *GOOD, on="2025-09-19")
    result = invoke("delivery", "waiting", on="2025-09-19")
    assert "grading" in result.output


def test_a_clean_load_grades_and_settles(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    invoke("delivery", "sample", "W-1", "B-1", *GOOD, on="2025-09-19")
    graded = invoke("delivery", "grade", "W-1", on="2025-09-19")
    assert "accepted" in graded.output
    assert "28.180t settled" in graded.output
    settled = invoke("delivery", "settle", "W-1")
    assert "6551.85" in settled.output


def test_a_wet_load_carries_its_lines(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    wet = tuple(item if item != "moisture=12.5" else "moisture=15.0" for item in GOOD)
    invoke("delivery", "sample", "W-1", "B-1", *wet, on="2025-09-19")
    graded = invoke("delivery", "grade", "W-1", on="2025-09-19")
    assert "drying" in graded.output
    assert "moisture 15.0 to 12.5" in graded.output


def test_a_load_that_fails_the_screen_is_rejected(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    weak = tuple(item if item != "germ_capacity=99.0" else "germ_capacity=90.0" for item in GOOD)
    invoke("delivery", "sample", "W-1", "B-1", *weak, on="2025-09-19")
    graded = invoke("delivery", "grade", "W-1", on="2025-09-19")
    assert "REJECTED" in graded.output
    assert "germination" in graded.output


def test_a_rejected_load_has_nothing_to_settle(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    weak = tuple(item if item != "germ_capacity=99.0" else "germ_capacity=90.0" for item in GOOD)
    invoke("delivery", "sample", "W-1", "B-1", *weak, on="2025-09-19")
    invoke("delivery", "grade", "W-1", on="2025-09-19")
    result = invoke("delivery", "settle", "W-1")
    assert "nothing to settle" in result.output


def test_a_finding_rejects_a_load_the_numbers_passed(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    invoke("delivery", "sample", "W-1", "B-1", *GOOD, on="2025-09-19")
    graded = invoke("delivery", "grade", "W-1", "--finding", "insect", on="2025-09-19")
    assert "REJECTED" in graded.output
    assert "insect" in graded.output


def test_a_load_with_no_harvest_date_cannot_be_graded(invoke: Invoke) -> None:
    setup(invoke)
    invoke(
        "delivery",
        "add",
        "W-2",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    invoke("delivery", "sample", "W-2", "B-2", *GOOD, on="2025-09-19")
    result = invoke("delivery", "grade", "W-2", on="2025-09-19")
    assert result.exit_code != 0


def test_a_harvest_date_can_be_added_afterwards(invoke: Invoke) -> None:
    setup(invoke)
    invoke(
        "delivery",
        "add",
        "W-2",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    invoke("delivery", "harvest", "W-2", "2025-08-14")
    invoke("delivery", "sample", "W-2", "B-2", *GOOD, on="2025-09-19")
    assert invoke("delivery", "grade", "W-2", on="2025-09-19").exit_code == 0


def test_a_result_that_is_not_a_pair_is_refused(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    result = invoke("delivery", "sample", "W-1", "B-1", "--result", "moisture", on="2025-09-19")
    assert result.exit_code != 0


def test_a_malt_result_in_a_barley_sample_is_refused(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    result = invoke("delivery", "sample", "W-1", "B-1", "--result", "colour=3.4", on="2025-09-19")
    assert result.exit_code != 0


def test_a_graded_load_draws_the_purchase_down(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    invoke("delivery", "sample", "W-1", "B-1", *GOOD, on="2025-09-19")
    invoke("delivery", "grade", "W-1", on="2025-09-19")
    result = invoke("purchase", "show", "P-1")
    assert "settled   28.18" in result.output


def test_the_delivery_list_narrows_by_grower(invoke: Invoke) -> None:
    setup(invoke)
    tip(invoke)
    assert "W-1" in invoke("delivery", "list", "--party", "HOLB").output
    assert "W-1" not in invoke("delivery", "list", "--party", "WYKE").output


def test_extending_a_window_lets_a_late_load_in(invoke: Invoke) -> None:
    setup(invoke)
    invoke("purchase", "extend", "P-1", "2025-12-20")
    result = invoke(
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
        on="2025-12-04",
    )
    assert result.exit_code == 0
