"""The design note lists the layers that exist, and says something about each."""

from __future__ import annotations

from culmbin.tools import check_design
from culmbin.tools.check_layers import BELOW


def test_the_check_passes_on_this_tree() -> None:
    assert check_design.problems() == []


def test_the_note_lists_exactly_the_packages() -> None:
    assert check_design.layers_in_the_note() == check_design.layers_in_the_table()


def test_every_package_is_in_the_table() -> None:
    listed = set(check_design.layers_in_the_table())
    assert listed == set(BELOW) - {"", "errors"}


def test_errors_is_deliberately_not_in_the_block() -> None:
    """It is a module rather than a package, and the note describes it in prose."""
    assert "errors" not in check_design.layers_in_the_note()


def test_every_layer_has_a_paragraph_naming_it() -> None:
    """A line in a code block is not an explanation."""
    assert check_design.explained() == set(check_design.layers_in_the_table())


def test_the_block_is_found_in_the_note() -> None:
    assert len(check_design.layers_in_the_note()) > 8


def test_the_order_of_the_note_is_the_order_of_the_table() -> None:
    """Otherwise a reader is left working out which one is the real one."""
    assert check_design.layers_in_the_note()[0] == "units"
    assert check_design.layers_in_the_note()[-1] == "tools"
