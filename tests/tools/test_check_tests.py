"""Every source module has a test module, and every test module has a source.

The second half is the one that finds things: a test module left behind
after its code was renamed goes on passing forever.
"""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_tests, sources


def test_the_check_passes_on_this_tree() -> None:
    assert check_tests.problems() == []


def test_nothing_is_missing_a_test() -> None:
    assert check_tests.missing_tests() == []


def test_nothing_is_left_behind() -> None:
    assert check_tests.orphaned_tests() == []


def test_the_expected_test_mirrors_the_source_path() -> None:
    wanted = check_tests._expected_test(sources.package_root() / "units" / "mass.py")
    assert wanted == sources.tests_root() / "units" / "test_mass.py"


def test_a_package_init_is_not_asked_for_a_test() -> None:
    """It holds a docstring and some re-exports."""
    assert "culmbin.units" in check_tests.NO_TEST_NEEDED


def test_the_support_modules_are_not_tests() -> None:
    assert "tests.support" in check_tests.SUPPORT


def test_a_dotted_name_drops_the_init(tmp_path: Path) -> None:
    (tmp_path / "thing").mkdir()
    (tmp_path / "thing" / "__init__.py").touch()
    dotted = check_tests._dotted(tmp_path / "thing" / "__init__.py", tmp_path, "root")
    assert dotted == "root.thing"


def test_a_dotted_name_keeps_a_module(tmp_path: Path) -> None:
    (tmp_path / "thing.py").touch()
    assert check_tests._dotted(tmp_path / "thing.py", tmp_path, "root") == "root.thing"
