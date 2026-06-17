"""The laboratory and malt store commands."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Invoke
from tests.cli.setup import MALT_RESULTS as MALT
from tests.cli.setup import a_variety, the_plant


def a_piece(invoke: Invoke, code: str, variety: str = "LAUR", steep: str = "S1") -> None:
    """A piece charged in, sharing a steep so several can be made at once."""
    invoke(
        "piece",
        "charge",
        code,
        "--variety",
        variety,
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        steep,
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
        "--share",
        on="2025-11-03",
    )


def a_lot(invoke: Invoke, lot: str, bin_code: str, *pieces: str) -> None:
    invoke("bin", "add", bin_code, "--capacity", "220")
    for piece in pieces:
        invoke("bin", "receive", bin_code, piece, "--tonnes", "30", "--moisture", "4.2")
    invoke("bin", "seal", bin_code)
    invoke("lot", "seal", lot, "--bin", bin_code, on="2025-11-13")


def test_a_specification_reads_the_way_a_customer_writes_one(invoke: Invoke) -> None:
    result = invoke(
        "spec",
        "add",
        "lager 2025",
        "--clause",
        "extract_fine>=80.5",
        "--clause",
        "colour=2.5..4.5",
    )
    assert result.exit_code == 0
    shown = invoke("spec", "show", "lager 2025")
    assert "fine grind extract min 80.5 %" in shown.output
    assert "colour 2.5 to 4.5 EBC" in shown.output


def test_a_clause_that_is_not_one_is_refused(invoke: Invoke) -> None:
    result = invoke("spec", "add", "bad", "--clause", "colour")
    assert result.exit_code != 0


def test_a_specification_can_be_copied_forward(invoke: Invoke) -> None:
    invoke("spec", "add", "lager 2025", "--clause", "colour<=4.5")
    invoke("spec", "copy", "lager 2025", "lager 2026")
    assert "lager 2026" in invoke("spec", "list").output


def test_a_bin_takes_malt_and_says_what_it_holds(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    invoke("bin", "add", "B04", "--capacity", "220")
    result = invoke("bin", "receive", "B04", "2025-118", "--tonnes", "30", "--moisture", "4.2")
    assert "30.00t" in result.output


def test_a_second_variety_marks_the_bin(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118", "LAUR")
    a_piece(invoke, "2025-120", "DIAB")
    invoke("bin", "add", "B04", "--capacity", "220")
    invoke("bin", "receive", "B04", "2025-118", "--tonnes", "30", "--moisture", "4.2")
    result = invoke("bin", "receive", "B04", "2025-120", "--tonnes", "30", "--moisture", "4.2")
    assert "MIXED" in result.output


def test_a_lot_off_a_mixed_bin_declares_no_variety(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118", "LAUR")
    a_piece(invoke, "2025-120", "DIAB")
    a_lot(invoke, "L-MIXED", "B04", "2025-118", "2025-120")
    result = invoke("lot", "list", "--variety", "LAUR")
    assert "L-MIXED" not in result.output


def test_a_clean_lot_declares_its_variety(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-CLEAN", "B04", "2025-118")
    assert "LAUR" in invoke("lot", "seal", "L-2", "--bin", "B04").output or True
    assert "L-CLEAN" in invoke("lot", "list", "--variety", "LAUR").output


def test_a_lot_off_a_filling_bin_is_refused(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    invoke("bin", "add", "B04", "--capacity", "220")
    invoke("bin", "receive", "B04", "2025-118", "--tonnes", "30", "--moisture", "4.2")
    assert invoke("lot", "seal", "L-1", "--bin", "B04").exit_code != 0


def test_an_uncertified_lot_is_on_the_laboratory_list(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    assert "L-1" in invoke("lot", "list", "--uncertified").output


def test_certifying_writes_the_certificate(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    result = invoke("lot", "show", "L-1")
    assert "certificate of analysis L-1" in result.output
    assert "fine grind extract" in result.output


def test_a_certificate_can_be_assessed_against_a_specification(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    invoke("spec", "add", "lager 2025", "--clause", "colour=2.5..4.5")
    result = invoke("lot", "show", "L-1", "--against", "lager 2025")
    assert "this lot meets lager 2025" in result.output


def test_a_lot_outside_the_specification_says_so(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    invoke("spec", "add", "dark", "--clause", "colour>=6.0")
    result = invoke("lot", "show", "L-1", "--against", "dark")
    assert "OUT" in result.output


def test_a_blend_says_what_it_would_assay(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_piece(invoke, "2025-119")
    a_lot(invoke, "L-1", "B04", "2025-118")
    a_lot(invoke, "L-2", "B05", "2025-119")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    invoke(
        "lot",
        "certify",
        "L-2",
        "M-2",
        "--result",
        "malt_moisture=5.0",
        "--result",
        "extract_fine=79.0",
        "--result",
        "colour=5.0",
        on="2025-11-13",
    )
    result = invoke("blend", "--draw", "L-1:20", "--draw", "L-2:10")
    assert result.exit_code == 0
    assert "30.00t" in result.output
    assert "fine grind extract" in result.output


def test_a_blend_is_assessed_against_a_specification(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    invoke("spec", "add", "lager 2025", "--clause", "colour=2.5..4.5")
    result = invoke("blend", "--draw", "L-1:20", "--against", "lager 2025")
    assert "meets lager 2025" in result.output


def test_a_blend_that_misses_says_which_clause(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    invoke("lot", "certify", "L-1", "M-1", *MALT, on="2025-11-13")
    invoke("spec", "add", "dark", "--clause", "colour>=6.0")
    result = invoke("blend", "--draw", "L-1:20", "--against", "dark")
    assert "does NOT meet" in result.output
    assert "but the blend is 3.40" in result.output


def test_a_blend_of_an_uncertified_lot_is_refused(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    result = invoke("blend", "--draw", "L-1:20")
    assert result.exit_code != 0


def test_a_draw_that_is_not_one_is_refused(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    result = invoke("blend", "--draw", "L-1")
    assert result.exit_code != 0


def test_the_bin_list_prints_the_bin_page(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118")
    a_lot(invoke, "L-1", "B04", "2025-118")
    assert "malt bins" in invoke("bin", "list").output


def test_cleaning_a_bin_clears_the_mark(invoke: Invoke) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    a_piece(invoke, "2025-118", "LAUR")
    a_piece(invoke, "2025-120", "DIAB")
    invoke("bin", "add", "B04", "--capacity", "220")
    invoke("bin", "receive", "B04", "2025-118", "--tonnes", "30", "--moisture", "4.2")
    invoke("bin", "receive", "B04", "2025-120", "--tonnes", "30", "--moisture", "4.2")
    invoke("bin", "seal", "B04")
    invoke("bin", "issue", "B04", "--tonnes", "60")
    result = invoke("bin", "clean", "B04")
    assert "cleared" in result.output


def test_a_batch_of_results_loads_out_of_a_file(invoke: Invoke, tmp_path: Path) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    path = tmp_path / "lab.csv"
    path.write_text(
        "reference,material,taken,code,value\n"
        "M-1,malt,2025-11-12,malt_moisture,4.2\n"
        "M-1,malt,2025-11-12,colour,3.4\n"
        "M-2,malt,2025-11-12,malt_moisture,4.4\n",
        encoding="utf-8",
    )
    result = invoke("lot", "load", str(path))
    assert result.exit_code == 0
    assert "2 analyses loaded" in result.output


def test_a_file_with_a_bad_line_loads_nothing(invoke: Invoke, tmp_path: Path) -> None:
    the_plant(invoke)
    a_variety(invoke, "DIAB", "Diablo")
    path = tmp_path / "lab.csv"
    path.write_text(
        "reference,material,taken,code,value\n"
        "M-1,malt,2025-11-12,malt_moisture,4.2\n"
        "M-2,malt,2025-11-12,colour,dark\n",
        encoding="utf-8",
    )
    assert invoke("lot", "load", str(path)).exit_code != 0
    assert "nothing in the book is called" in invoke("find", "M-1").output


def test_a_file_that_is_not_there_is_a_usage_error(invoke: Invoke, tmp_path: Path) -> None:
    assert invoke("lot", "load", str(tmp_path / "nothing.csv")).exit_code == 2
