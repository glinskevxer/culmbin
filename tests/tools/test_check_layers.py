"""The layering table, and what it forbids.

Two things are tested for each check. It passes on this tree, which is what
CI cares about, and it fails on something planted, which is what says the
check does anything at all. A check that has only ever passed has been
watched, not tested.
"""

from __future__ import annotations

from culmbin.tools import check_layers, sources


def test_the_layer_check_passes_on_this_tree() -> None:
    assert check_layers.problems() == []


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
