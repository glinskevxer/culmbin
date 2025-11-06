"""Every error message is a sentence somebody at a weighbridge can read.

Three rules, and all three came from reading real messages out loud.

A message starts in lower case. It is going to appear after `culmbin: ` on a
terminal, and a capital in the middle of a line reads like the start of
something else.

A message does not end in a full stop, for the same reason: the console
script adds the punctuation it wants and a doubled stop looks like a typo.

A message says at least four words, counting each placeholder as one.
`raise ValidationError("bad")` is a sentence the person reading it cannot
act on. `f"no party called {code!r}"` is four and is the shortest thing that
still names what was wrong and what it was about, which is why the floor is
there and not one higher.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import relative, report, source_modules

MINIMUM_WORDS = 4
OUR_ERRORS = frozenset(
    {
        "CulmbinError",
        "ValidationError",
        "BasisError",
        "NotFoundError",
        "ConflictError",
        "StateError",
        "SegregationError",
    }
)


def _first_text(node: ast.expr) -> str | None:
    """The literal text at the front of a raised message, if there is any."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            return ""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _first_text(node.left)
    return None


def _words(node: ast.expr) -> int:
    """Roughly how many words a message has, counting a placeholder as one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return len(node.value.split())
    if isinstance(node, ast.JoinedStr):
        total = 0
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                total += len(value.value.split())
            else:
                total += 1
        return total
    return MINIMUM_WORDS


def problems() -> list[str]:
    """Every raised message that is not a sentence."""
    found = []
    for module in source_modules():
        where = relative(module.path)
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id not in OUR_ERRORS or not call.args:
                continue
            message = call.args[0]
            text = _first_text(message)
            if text is None:
                continue
            if text[:1].isupper():
                found.append(f"{where}:{node.lineno}: the message starts in upper case.")
            if isinstance(message, ast.Constant) and text.endswith("."):
                found.append(f"{where}:{node.lineno}: the message ends in a full stop.")
            if _words(message) < MINIMUM_WORDS:
                found.append(
                    f"{where}:{node.lineno}: the message is about {_words(message)} words, "
                    f"which is not something anybody can act on."
                )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "messages")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
