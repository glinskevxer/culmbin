"""A test name says what is true, not that something was tested."""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_naming, sources


def test_the_check_passes_on_this_tree() -> None:
    assert check_naming.problems() == []


def test_no_test_in_the_suite_uses_a_vague_word() -> None:
    assert check_naming.vague_names() == []


def test_no_test_in_the_suite_is_too_short_to_be_a_sentence() -> None:
    assert check_naming.thin_names() == []


def test_every_check_module_has_the_shape_ci_expects() -> None:
    assert check_naming.check_shapes() == []


def test_good_is_deliberately_not_a_vague_word() -> None:
    """A good load is what the intake office calls one that passes the screen."""
    assert "good" not in check_naming.VAGUE
    assert "works" in check_naming.VAGUE


def test_a_test_function_is_one_that_starts_with_test(tmp_path: Path) -> None:
    path = tmp_path / "test_thing.py"
    path.write_text(
        '"""A module with one test and one helper in it."""\n\n\n'
        "def helper():\n    pass\n\n\ndef test_a_thing_is_the_thing_it_is():\n    pass\n"
    )
    names = [node.name for node in check_naming._test_functions(sources.read(path))]
    assert names == ["test_a_thing_is_the_thing_it_is"]


def test_the_minimum_is_four_words_after_the_prefix() -> None:
    assert check_naming.MINIMUM_WORDS == 4


def test_a_check_without_problems_is_reported() -> None:
    """Every check has to be callable from inside the suite as well as by ci."""
    assert set(check_naming.CHECK_INTERFACE) == {"problems", "main"}
