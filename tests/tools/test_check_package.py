"""The pins in pyproject are all in the constraints, at the same version."""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_package


def test_the_check_passes_on_this_tree() -> None:
    assert check_package.problems() == []


def test_every_direct_pin_is_in_the_closure() -> None:
    asked = set(check_package.declared()) - {"hatchling"}
    assert asked <= set(check_package.constrained())


def test_the_closure_is_larger_than_what_is_asked_for() -> None:
    """It is the transitive closure, so it holds things nobody asked for."""
    assert len(check_package.constrained()) > len(check_package.declared())


def test_a_name_is_compared_the_way_pip_compares_it() -> None:
    assert check_package.normalise("pytest_cov") == "pytest-cov"
    assert check_package.normalise("Typing.Extensions") == "typing-extensions"


def test_a_pin_is_read_out_of_a_line() -> None:
    match = check_package.PIN.match('  "click==8.1.8",')
    assert match is not None
    assert match.group(1) == "click"
    assert match.group(2) == "8.1.8"


def test_a_comment_is_not_a_pin(tmp_path: Path) -> None:
    path = tmp_path / "constraints.txt"
    path.write_text("# click==9.9.9\nclick==8.1.8\n")
    assert check_package._pins(path) == {"click": "8.1.8"}


def test_a_line_that_is_not_a_pin_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "constraints.txt"
    path.write_text("click>=8\nclick==8.1.8\n")
    assert check_package._pins(path) == {"click": "8.1.8"}
