"""The command reference is written out of the console script."""

from __future__ import annotations

from pathlib import Path

import pytest

from culmbin.tools import build_docs
from culmbin.tools.check_help import command_names


def test_the_reference_on_disk_is_current() -> None:
    assert build_docs.main(["--check"]) == 0


def test_every_command_is_in_the_reference() -> None:
    """It cannot miss one, because it walks the tree rather than a list."""
    text = build_docs.render()
    for path in command_names():
        if path == "cli":
            continue
        assert f"`{path.replace('cli ', 'culmbin ', 1)}" in text


def test_the_arguments_are_written_the_way_they_are_typed() -> None:
    assert "culmbin ship allocate CODE CONTRACT_CODE LOT" in build_docs.render()


def test_an_option_carries_what_it_is_for() -> None:
    text = build_docs.render()
    assert "the moisture the contract tonne is written at" in text


def test_a_required_option_is_marked() -> None:
    assert "| `--tonnes` | yes |" in build_docs.render()


def test_a_command_with_no_options_has_no_table() -> None:
    text = build_docs.render()
    block = text.split("## `culmbin status`")[1].split("## ")[0]
    assert "| option |" not in block


def test_generating_writes_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "commands.md"
    monkeypatch.setattr(build_docs, "document_path", lambda: target)
    assert build_docs.main([]) == 0
    assert target.read_text(encoding="utf-8") == build_docs.render()


def test_a_stale_reference_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_docs, "document_path", lambda: tmp_path / "nothing.md")
    assert build_docs.main(["--check"]) == 1
