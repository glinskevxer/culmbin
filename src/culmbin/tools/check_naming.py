"""A test name says what is true, not that something was tested.

`test_grade_works` tells a reader who has just watched it fail exactly
nothing. `test_a_rejected_load_has_no_settled_weight` tells them what was
supposed to happen, which is most of the way to knowing why it did not.

So the vague words below are banned in test names. The list is short on
purpose: a long list turns into an argument about wording.

**`good` is deliberately not on it.** A good load is what the intake office
calls a load that passes the screen, and banning the word would push the
tests into saying something worse.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import Module, public, relative, report, source_modules, test_modules

VAGUE = frozenset(
    {
        "works",
        "work",
        "correct",
        "correctly",
        "properly",
        "valid",
        "invalid",
        "ok",
        "basic",
        "simple",
        "handles",
        "handling",
        "stuff",
        "misc",
    }
)

MINIMUM_WORDS = 4
CHECK_INTERFACE = ("problems", "main")


def _test_functions(module: Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every top level function in a test module whose name starts with test."""
    return [
        node
        for node in module.top_level()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    ]


def vague_names() -> list[str]:
    """Every test whose name uses a word that says nothing."""
    found = []
    for module in test_modules():
        for node in _test_functions(module):
            words = set(node.name.split("_"))
            for word in sorted(words & VAGUE):
                found.append(
                    f"{relative(module.path)}:{node.lineno}: {node.name} says {word!r}, "
                    f"which is not a fact about the malthouse."
                )
    return found


def thin_names() -> list[str]:
    """Every test whose name is too short to be a sentence."""
    found = []
    for module in test_modules():
        for node in _test_functions(module):
            words = [word for word in node.name.split("_")[1:] if word]
            if len(words) < MINIMUM_WORDS:
                found.append(
                    f"{relative(module.path)}:{node.lineno}: {node.name} is "
                    f"{len(words)} words, which does not say what is true."
                )
    return found


def check_shapes() -> list[str]:
    """Every check module that does not have the shape CI expects.

    A check without a `problems()` cannot be tested from inside the suite,
    and one without a `main()` cannot be run by CI, so both are required.
    """
    found = []
    for module in source_modules():
        name = module.dotted.rsplit(".", 1)[-1]
        if not name.startswith("check_"):
            continue
        defined = {node.name for node in module.top_level() if public(node.name)}
        for wanted in CHECK_INTERFACE:
            if wanted not in defined:
                found.append(f"{relative(module.path)}: has no {wanted}().")
    return found


def problems() -> list[str]:
    """Every naming problem in the tests and every misshapen check."""
    return [*vague_names(), *thin_names(), *check_shapes()]


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "naming")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
