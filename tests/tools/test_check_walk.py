"""Every command the console script has is run by the walk in CI, or excused."""

from __future__ import annotations

from culmbin.tools import check_walk
from culmbin.tools.check_help import command_names


def test_the_check_passes_on_this_tree() -> None:
    assert check_walk.problems() == []


def test_the_walk_runs_a_good_share_of_the_commands() -> None:
    run = check_walk.run_by_the_walk()
    assert len(run) > 50
    assert "cli silo draw" in run


def test_every_excused_command_is_still_a_command() -> None:
    """An excuse for a command that has gone is an excuse that hides the next one."""
    assert set(check_walk.EXCUSED) <= set(command_names())


def test_every_excuse_says_why() -> None:
    for name, why in check_walk.EXCUSED.items():
        assert why.strip(), name
        assert len(why.split()) >= 2, name


def test_the_two_checks_ask_opposite_questions() -> None:
    """One asks that the walk names real commands, this asks that it names them all."""
    from culmbin.tools import check_workflow

    assert check_workflow.unknown_commands() == []
    assert check_walk.problems() == []


def test_a_group_is_excused_because_it_is_not_a_command() -> None:
    assert check_walk.EXCUSED["cli report"] == "a group"


def test_the_walk_runs_every_report_page() -> None:
    run = check_walk.run_by_the_walk()
    reports = [name for name in command_names() if name.startswith("cli report ")]
    assert set(reports) <= run
