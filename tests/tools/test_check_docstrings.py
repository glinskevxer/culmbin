"""Every module and public definition has a docstring that says why.

Two things are tested for each check. It passes on this tree, which is what
CI cares about, and it fails on something planted, which is what says the
check does anything at all. A check that has only ever passed has been
watched, not tested.
"""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_docstrings, sources


def test_the_docstring_check_passes_on_this_tree() -> None:
    assert check_docstrings.problems() == []


def test_a_missing_docstring_is_found(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module with something undocumented in it."""\n\n\ndef work():\n    pass\n'
    )
    module = sources.read(path)
    found = check_docstrings._check_module(module)
    assert any("work has no docstring" in item for item in found)


def test_a_docstring_that_says_the_name_back_is_found(tmp_path: Path) -> None:
    """`def malting_loss(): "Malting loss."` is worse than nothing."""
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module with a docstring that says nothing."""\n\n\n'
        'def malting_loss_percent():\n    """Malting loss percent."""\n'
    )
    found = check_docstrings._check_module(sources.read(path))
    assert any("says its own name back" in item for item in found)


def test_a_two_word_docstring_is_found(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text('"""A module."""\n\n\ndef work():\n    """Does work."""\n')
    found = check_docstrings._check_module(sources.read(path))
    assert any("2 words" in item for item in found)


def test_a_private_definition_is_not_asked_for_one(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text('"""A module with a private helper in it."""\n\n\ndef _work():\n    pass\n')
    assert check_docstrings._check_module(sources.read(path)) == []


def test_a_module_with_no_docstring_is_found(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text("x = 1\n")
    found = check_docstrings._check_module(sources.read(path))
    assert any("the module has no docstring" in item for item in found)
