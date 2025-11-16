"""The walk in CI is a shell script inside yaml, and nothing compiles it."""

from __future__ import annotations

from culmbin.tools import check_workflow


def test_the_check_passes_on_this_tree() -> None:
    assert check_workflow.problems() == []


def test_the_workflow_is_where_the_check_looks() -> None:
    assert check_workflow.workflow_path().exists()
    assert check_workflow.workflow_path().name == "ci.yml"


def test_the_walk_runs_a_good_number_of_commands() -> None:
    assert len(check_workflow.walk_commands()) > 40


def test_every_command_in_the_walk_is_a_real_command() -> None:
    assert check_workflow.unknown_commands() == []


def test_every_check_module_is_run_by_ci() -> None:
    """A check written and not added to CI runs locally and never in anger."""
    assert check_workflow.checks_not_run() == []


def test_a_continued_line_is_joined_up() -> None:
    joined = check_workflow.walk_commands()
    assert any("--role grower --holding" in command for command in joined)


def test_the_command_words_leave_out_the_options() -> None:
    words = check_workflow._words(
        "culmbin --book /tmp/b.sqlite3 --on 2025-09-18 delivery add W-1 P-1 --party HOLB"
    )
    assert words == ["delivery", "add", "W-1", "P-1"]


def test_an_option_written_with_an_equals_takes_no_value_word() -> None:
    words = check_workflow._words("culmbin lot certify L-1 M-1 --result colour=3.4")
    assert words == ["lot", "certify", "L-1", "M-1"]
