"""Every error message is a sentence somebody at a weighbridge can read."""

from __future__ import annotations

import ast

from culmbin.tools import check_messages


def parse(text: str) -> ast.expr:
    """The expression at the front of a one line statement."""
    node = ast.parse(text).body[0]
    assert isinstance(node, ast.Expr)
    return node.value


def test_the_check_passes_on_this_tree() -> None:
    assert check_messages.problems() == []


def test_a_plain_string_is_counted_word_by_word() -> None:
    assert check_messages._words(parse('"one two three"')) == 3


def test_a_placeholder_counts_as_one_word() -> None:
    """`f"no party called {code!r}"` is four, and that is the floor."""
    assert check_messages._words(parse('f"no party called {code!r}"')) == 4


def test_something_that_is_not_a_literal_is_given_the_benefit() -> None:
    assert check_messages._words(parse("message")) == check_messages.MINIMUM_WORDS


def test_the_leading_text_of_a_format_string_comes_back() -> None:
    assert check_messages._first_text(parse('f"no party called {code!r}"')) == "no party called "


def test_a_format_string_starting_with_a_placeholder_has_no_leading_text() -> None:
    assert check_messages._first_text(parse('f"{code} is not here"')) == ""


def test_a_plain_string_is_its_own_leading_text() -> None:
    assert check_messages._first_text(parse('"nothing to be done"')) == "nothing to be done"


def test_something_that_is_not_a_string_has_no_leading_text() -> None:
    assert check_messages._first_text(parse("message")) is None


def test_every_one_of_our_errors_is_checked() -> None:
    from culmbin import errors

    named = {name for name in dir(errors) if name.endswith("Error") and not name.startswith("_")}
    assert named - {"Exception"} == check_messages.OUR_ERRORS
