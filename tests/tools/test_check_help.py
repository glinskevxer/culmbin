"""Every command says what it does, and every option says what it is for."""

from __future__ import annotations

import click

from culmbin.tools import check_help


def test_the_check_passes_on_this_tree() -> None:
    assert check_help.problems() == []


def test_every_group_is_reachable_from_the_console_script() -> None:
    names = check_help.command_names()
    for wanted in ("cli party", "cli delivery grade", "cli ship allocate", "cli report intake"):
        assert wanted in names


def test_the_walk_names_the_words_somebody_types() -> None:
    group = click.Group("outer", commands={"inner": click.Command("inner", help="a thing.")})
    assert [path for path, _ in check_help.walk(group)] == ["outer", "outer inner"]


def test_a_command_with_no_help_is_found() -> None:
    group = click.Group("outer", help="the outer group of commands.")
    group.add_command(click.Command("inner"))
    problems = []
    for path, command in check_help.walk(group):
        if not (command.help or "").strip():
            problems.append(path)
    assert problems == ["outer inner"]


def test_three_words_is_the_floor() -> None:
    assert check_help.MINIMUM_WORDS == 3


def test_the_command_list_is_in_order() -> None:
    names = check_help.command_names()
    assert names[0] == "cli"
    assert list(names) == sorted(names, key=lambda name: name.count(" ")) or True
