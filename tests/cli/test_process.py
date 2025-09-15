"""The plant commands, worked as a whole piece."""

from __future__ import annotations

from tests.cli.conftest import Invoke


def recipes(invoke: Invoke) -> None:
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
        "recipe",
        "programme",
        "pale two stand",
        "--style",
        "pale_ale",
        "--leg",
        "wet:8:14",
        "--leg",
        "air:16:16",
        "--leg",
        "wet:6:14",
        "--target",
        "44.5",
    )
    invoke(
        "recipe",
        "schedule",
        "pale four day",
        "--style",
        "pale_ale",
        "--target",
        "1200",
        "--turn",
        "200",
        "--turn",
        "500",
        "--turn",
        "800",
    )
    invoke(
        "recipe",
        "curve",
        "pale 18 hour",
        "--style",
        "pale_ale",
        "--step",
        "dry:10:60",
        "--step",
        "break:4:70",
        "--step",
        "cure:4:85",
        "--target",
        "4.2",
    )


def charged(invoke: Invoke, code: str = "2025-118") -> None:
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
        "pale two stand",
        "--schedule",
        "pale four day",
        "--curve",
        "pale 18 hour",
        on="2025-11-03",
    )


def test_a_programme_says_what_it_expects(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke(
        "recipe",
        "programme",
        "lager long",
        "--style",
        "lager",
        "--leg",
        "wet:30:12",
        "--target",
        "42",
    )
    assert result.exit_code == 0
    assert "expecting" in result.output


def test_two_wet_stands_together_are_refused(invoke: Invoke) -> None:
    result = invoke(
        "recipe",
        "programme",
        "bad",
        "--style",
        "lager",
        "--leg",
        "wet:8:14",
        "--leg",
        "wet:6:14",
        "--target",
        "42",
    )
    assert result.exit_code != 0


def test_a_leg_that_is_not_one_is_refused(invoke: Invoke) -> None:
    result = invoke(
        "recipe", "programme", "bad", "--style", "lager", "--leg", "warm:8:14", "--target", "42"
    )
    assert result.exit_code != 0


def test_a_schedule_says_how_long_it_takes(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke("recipe", "show", "schedule", "pale four day")
    assert "turn 1 at 200" in result.output


def test_a_curve_says_what_colour_it_expects(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke(
        "recipe",
        "curve",
        "lager 16",
        "--style",
        "lager",
        "--step",
        "dry:12:55",
        "--step",
        "cure:5:80",
        "--target",
        "4.5",
    )
    assert "EBC" in result.output


def test_a_curve_that_turns_the_kiln_down_is_refused(invoke: Invoke) -> None:
    result = invoke(
        "recipe",
        "curve",
        "bad",
        "--style",
        "lager",
        "--step",
        "dry:10:70",
        "--step",
        "cure:4:60",
        "--target",
        "4.5",
    )
    assert result.exit_code != 0


def test_the_recipe_list_has_all_three_kinds(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke("recipe", "list")
    assert "programme" in result.output
    assert "schedule" in result.output
    assert "curve" in result.output


def test_a_programme_shows_its_legs_in_order(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke("recipe", "show", "programme", "pale two stand")
    assert "1. wet 8h at 14C" in result.output
    assert "2. air 16h at 16C" in result.output


def test_a_charge_says_its_dry_matter(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    result = invoke("piece", "list")
    assert "2025-118" in result.output
    assert "steeping" in result.output


def test_a_charge_over_what_the_steep_takes_is_refused(invoke: Invoke) -> None:
    recipes(invoke)
    result = invoke(
        "piece",
        "charge",
        "2025-999",
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        "S1",
        "--tonnes",
        "60",
        "--moisture",
        "12",
        "--programme",
        "pale two stand",
        "--schedule",
        "pale four day",
        "--curve",
        "pale 18 hour",
        on="2025-11-03",
    )
    assert result.exit_code != 0


def test_a_recipe_for_another_style_is_refused(invoke: Invoke) -> None:
    recipes(invoke)
    invoke(
        "recipe",
        "programme",
        "lager long",
        "--style",
        "lager",
        "--leg",
        "wet:30:12",
        "--target",
        "42",
    )
    result = invoke(
        "piece",
        "charge",
        "2025-999",
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
        "lager long",
        "--schedule",
        "pale four day",
        "--curve",
        "pale 18 hour",
        on="2025-11-03",
    )
    assert result.exit_code != 0


def test_a_piece_goes_all_the_way_through(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    invoke(
        "piece", "reading", "2025-118", "--stage", "steeping", "--hours", "48", "--celsius", "14"
    )
    assert (
        invoke(
            "piece",
            "cast",
            "2025-118",
            "--into",
            "G1",
            "--tonnes",
            "71.8",
            "--moisture",
            "44.8",
            "--depth",
            "85",
            on="2025-11-05",
        ).exit_code
        == 0
    )
    invoke(
        "piece",
        "reading",
        "2025-118",
        "--stage",
        "germinating",
        "--hours",
        "96",
        "--celsius",
        "16",
    )
    assert invoke("piece", "kiln", "2025-118", "--into", "K1", on="2025-11-08").exit_code == 0
    stripped = invoke(
        "piece",
        "strip",
        "2025-118",
        "--malt",
        "37.9",
        "--moisture",
        "4.4",
        "--culm",
        "1.9",
        on="2025-11-09",
    )
    assert "malting loss" in stripped.output
    assert "yield" in stripped.output


def test_a_bed_deeper_than_the_box_runs_is_refused(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    result = invoke(
        "piece",
        "cast",
        "2025-118",
        "--into",
        "G1",
        "--tonnes",
        "71.8",
        "--moisture",
        "44.8",
        "--depth",
        "140",
        on="2025-11-05",
    )
    assert result.exit_code != 0


def test_a_source_ticket_goes_on_a_piece(invoke: Invoke) -> None:
    recipes(invoke)
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
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
    invoke(
        "delivery",
        "add",
        "W-1",
        "P-1",
        "--party",
        "HOLB",
        "--gross",
        "43820",
        "--tare",
        "15640",
        on="2025-09-18",
    )
    charged(invoke)
    result = invoke("piece", "source", "2025-118", "W-1", "--tonnes", "28")
    assert result.exit_code == 0
    assert "W-1" in invoke("piece", "show", "2025-118").output


def test_a_piece_can_be_written_off_with_a_reason(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    result = invoke("piece", "writeoff", "2025-118", "--note", "steep flooded")
    assert result.exit_code == 0
    assert "written_off" in invoke("piece", "list").output


def test_writing_off_without_a_reason_is_not_possible(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    assert invoke("piece", "writeoff", "2025-118").exit_code == 2


def test_the_piece_page_carries_the_movements(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    result = invoke("piece", "show", "2025-118")
    assert "piece 2025-118" in result.output
    assert "movements" in result.output


def test_the_piece_list_narrows_by_stage(invoke: Invoke) -> None:
    recipes(invoke)
    charged(invoke)
    assert "2025-118" in invoke("piece", "list", "--stage", "steeping").output
    assert "2025-118" not in invoke("piece", "list", "--stage", "kilned").output
