"""A public name nothing refers to is dead, and its own module does not count."""

from __future__ import annotations

import ast
from pathlib import Path

from culmbin.tools import check_wiring, sources


def test_the_check_passes_on_this_tree() -> None:
    assert check_wiring.problems() == []


def test_only_functions_are_looked_at(tmp_path: Path) -> None:
    """A constant is defined to be named, and a class is used without saying its name."""
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module with a constant, a class and a function in it."""\n\n'
        "LIMIT = 3\n\n\nclass Thing:\n    pass\n\n\ndef work():\n    pass\n"
    )
    names = [name for name, _ in check_wiring._defined(sources.read(path))]
    assert names == ["work"]


def test_a_private_function_is_not_looked_at(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text('"""A module with a private helper."""\n\n\ndef _work():\n    pass\n')
    assert check_wiring._defined(sources.read(path)) == []


def test_a_console_command_is_wired_by_its_decorator(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module holding one console command."""\n\nimport click\n\n\n'
        "@click.command()\ndef work():\n    pass\n"
    )
    assert check_wiring._defined(sources.read(path)) == []


def test_a_group_command_is_wired_by_its_decorator(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module holding one grouped command."""\n\n\n'
        '@party.command("add")\ndef party_add():\n    pass\n'
    )
    assert check_wiring._defined(sources.read(path)) == []


def test_an_ordinary_decorator_does_not_exempt_a_function(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A module with a cached function in it."""\n\n\n@cache\ndef work():\n    pass\n'
    )
    names = [name for name, _ in check_wiring._defined(sources.read(path))]
    assert names == ["work"]


def test_the_entry_points_ci_calls_are_exempt() -> None:
    assert {"main", "problems"} <= check_wiring.EXEMPT


def test_a_name_used_in_a_test_counts_as_wired() -> None:
    """A helper only the tests call is still a helper somebody wrote for a reason."""
    used = check_wiring._used_elsewhere()
    assert any("tests" in path for path in used["barley_sample"])


def test_a_command_is_recognised_from_its_decorator() -> None:
    node = ast.parse("@click.command()\ndef work():\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)
    assert check_wiring._is_command(node)
