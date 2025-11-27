"""The glossary is written out of the enumerations and the analyte table."""

from __future__ import annotations

from pathlib import Path

import pytest

from culmbin.model.analytes import ANALYTES
from culmbin.model.enums import Basis, PieceStage
from culmbin.tools import build_glossary


def test_the_glossary_on_disk_is_current() -> None:
    assert build_glossary.main(["--check"]) == 0


def test_every_enumeration_is_in_it() -> None:
    text = build_glossary.render()
    assert "## Basis" in text
    assert "## PieceStage" in text


def test_every_member_of_an_enumeration_is_in_it() -> None:
    """Nobody argues with it, because every word in it is one the code knows."""
    text = build_glossary.render()
    for stage in PieceStage:
        assert f"`{stage.value}`" in text
    for basis in Basis:
        assert f"`{basis.value}`" in text


def test_every_analyte_is_in_it() -> None:
    text = build_glossary.render()
    for code in ANALYTES:
        assert f"`{code}`" in text


def test_the_analytes_are_split_by_material() -> None:
    text = build_glossary.render()
    assert "what the laboratory measures on barley" in text
    assert "what the laboratory measures on malt" in text


def test_the_enumerations_carry_their_own_first_line() -> None:
    assert "Which weight a percentage is a percentage of." in build_glossary.render()


def test_generating_writes_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "glossary.md"
    monkeypatch.setattr(build_glossary, "document_path", lambda: target)
    assert build_glossary.main([]) == 0
    assert target.read_text(encoding="utf-8") == build_glossary.render()


def test_a_stale_glossary_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_glossary, "document_path", lambda: tmp_path / "nothing.md")
    assert build_glossary.main(["--check"]) == 1
