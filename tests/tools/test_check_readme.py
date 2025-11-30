"""The README and the design note name code, so a machine can say when they rot."""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_readme


def test_the_check_passes_on_this_tree() -> None:
    assert check_readme.problems() == []


def test_all_three_documents_are_read() -> None:
    assert set(check_readme.DOCUMENTS) == {"README.md", "docs/design.md", "CHANGELOG.md"}


def test_a_module_that_has_gone_is_found(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("The work happens in `culmbin.units.gone`.\n")
    found = check_readme._check(path)
    assert any("not there any more" in item for item in found)


def test_a_module_that_is_there_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("The work happens in `culmbin.units.mass`.\n")
    assert check_readme._check(path) == []


def test_an_attribute_of_a_module_resolves(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("See `culmbin.units.mass.dry_matter`.\n")
    assert check_readme._check(path) == []


def test_a_command_that_is_not_one_is_found(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("Run `culmbin delivery unload`.\n")
    found = check_readme._check(path)
    assert any("which is not one" in item for item in found)


def test_a_command_that_is_one_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("Run `culmbin delivery waiting`.\n")
    assert check_readme._check(path) == []


def test_a_command_with_options_stops_at_the_options(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("Run `culmbin report intake --from 2025-09-01`.\n")
    assert check_readme._check(path) == []


def test_a_document_that_is_not_there_is_found(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("See `docs/nothing.md`.\n")
    found = check_readme._check(path)
    assert any("which is not there" in item for item in found)


def test_ordinary_prose_in_backticks_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("A `wet stand` is not a module and not a command.\n")
    assert check_readme._check(path) == []


def test_a_document_that_does_not_exist_at_all_is_reported(tmp_path: Path) -> None:
    found = check_readme._check(tmp_path / "nothing.md")
    assert found == ["nothing.md: there is no such document."]
