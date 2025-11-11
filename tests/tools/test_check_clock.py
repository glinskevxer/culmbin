"""One module asks what day it is, and everything else is told."""

from __future__ import annotations

import ast

from culmbin.tools import check_clock


def test_the_check_passes_on_this_tree() -> None:
    assert check_clock.problems() == []


def test_only_the_console_script_may_read_a_clock() -> None:
    assert frozenset({"culmbin.cli.main"}) == check_clock.ALLOWED


def test_asking_for_today_is_a_clock_call() -> None:
    node = ast.parse("dt.date.today()").body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)
    assert check_clock._clock_call(node.value) == "today"


def test_asking_for_now_is_a_clock_call() -> None:
    node = ast.parse("datetime.now(tz=UTC)").body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)
    assert check_clock._clock_call(node.value) == "now"


def test_a_bare_call_by_that_name_is_a_clock_call() -> None:
    node = ast.parse("today()").body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)
    assert check_clock._clock_call(node.value) == "today"


def test_an_ordinary_call_is_not_a_clock_call() -> None:
    """A date is a value, and the ban is on asking for the current one."""
    node = ast.parse("dt.date(2025, 11, 4)").body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.Call)
    assert check_clock._clock_call(node.value) is None
