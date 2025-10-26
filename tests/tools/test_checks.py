"""The self-checks, run against the tree they check.

Two things are tested for each check. It passes on this tree, which is what
CI cares about, and it fails on something planted, which is what says the
check does anything at all. A check that has only ever passed has been
watched, not tested.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from culmbin.tools import check_docstrings, check_layers, sources


def test_the_docstring_check_passes_on_this_tree() -> None:
    assert check_docstrings.problems() == []


def test_the_layer_check_passes_on_this_tree() -> None:
    assert check_layers.problems() == []


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


def test_every_layer_in_the_tree_is_in_the_table() -> None:
    """A package added and not put in the table is caught by the check itself."""
    in_tree = {module.layer for module in sources.source_modules()}
    assert in_tree <= set(check_layers.layers())


def test_units_may_not_import_from_model() -> None:
    """The table is the rule, so the test asks the table rather than the tree."""
    assert "model" not in check_layers.BELOW["units"]
    assert "store" not in check_layers.BELOW["model"]


def test_nothing_may_import_from_the_console_script() -> None:
    for layer, allowed in check_layers.BELOW.items():
        if layer != "tools":
            assert "cli" not in allowed


def test_a_module_knows_its_dotted_name() -> None:
    module = sources.read(sources.package_root() / "units" / "mass.py")
    assert module.dotted == "culmbin.units.mass"
    assert module.layer == "units"


def test_a_package_init_drops_its_last_part() -> None:
    module = sources.read(sources.package_root() / "units" / "__init__.py")
    assert module.dotted == "culmbin.units"


def test_a_module_lists_what_it_imports() -> None:
    module = sources.read(sources.package_root() / "units" / "mass.py")
    assert "culmbin.errors" in set(module.imports())


def test_the_tree_reader_finds_every_module() -> None:
    modules = sources.source_modules()
    assert len(modules) > 40
    assert all(module.path.suffix == ".py" for module in modules)


def test_the_tree_reader_finds_the_tests() -> None:
    assert len(sources.test_modules()) > 20


def test_a_public_name_is_one_without_an_underscore() -> None:
    assert sources.public("work")
    assert not sources.public("_work")


def test_reporting_nothing_is_a_pass(capsys: pytest.CaptureFixture[str]) -> None:
    assert sources.report([], "nothing") == 0
    assert "nothing to report" in capsys.readouterr().out


def test_reporting_something_is_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    assert sources.report(["one thing"], "something") == 1
    output = capsys.readouterr().out
    assert "one thing" in output
    assert "1 to fix" in output


def test_a_relative_path_is_printed_from_the_project_root() -> None:
    path = sources.package_root() / "units" / "mass.py"
    assert sources.relative(path) == "src/culmbin/units/mass.py"


def test_top_level_definitions_leave_out_the_nested_ones(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module with a nested function."""\n\n\ndef outer():\n    def inner():\n        pass\n'
    )
    module = sources.read(path)
    assert [node.name for node in module.top_level()] == ["outer"]
    assert {node.name for node in module.definitions()} == {"outer", "inner"}


def test_the_names_used_include_attributes(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module that uses a name."""\n\n\ndef work(thing):\n    return thing.value\n'
    )
    names = set(sources.read(path).names())
    assert {"thing", "value"} <= names


def test_a_module_docstring_comes_back(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text('"""What this module is for."""\n')
    assert sources.read(path).docstring == "What this module is for."
    assert isinstance(sources.read(path).tree, ast.Module)
