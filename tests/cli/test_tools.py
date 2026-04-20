"""The two commands that are about the book rather than about malt."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Invoke


def test_find_says_what_a_code_is(invoke: Invoke) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    result = invoke("find", "HOLB")
    assert result.exit_code == 0
    assert "party" in result.output
    assert "Holbeach" in result.output


def test_find_says_plainly_when_there_is_nothing(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("find", "NOTHING")
    assert "nothing in the book is called" in result.output


def test_the_registers_command_counts_everything(invoke: Invoke) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    result = invoke("registers")
    assert "party" in result.output
    assert "tables would be exported" in result.output


def test_export_writes_a_file_per_table(invoke: Invoke, tmp_path: Path) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    into = tmp_path / "csv"
    result = invoke("export", str(into))
    assert result.exit_code == 0
    assert (into / "party.csv").exists()


def test_exporting_twice_into_one_directory_is_refused(invoke: Invoke, tmp_path: Path) -> None:
    invoke("init")
    into = tmp_path / "csv"
    invoke("export", str(into))
    assert invoke("export", str(into)).exit_code != 0


def test_the_doctor_passes_on_a_fresh_book(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("doctor")
    assert result.exit_code == 0
    assert "nothing is wrong with this book." in result.output


def test_the_doctor_can_be_quiet_for_a_cron_job(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("doctor", "--quiet")
    assert result.exit_code == 0
    assert "0 wrong" in result.output


def test_the_doctor_says_what_is_in_the_book(invoke: Invoke) -> None:
    invoke("party", "add", "HOLB", "Holbeach", "--role", "grower", on="2011-06-01")
    result = invoke("doctor")
    assert "what is in it" in result.output
    assert "party" in result.output
