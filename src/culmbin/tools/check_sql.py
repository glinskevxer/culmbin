"""Values reach SQLite as parameters, and the short list of names is the gate.

An f-string with a value in it is how a delivery ticket typed as
`W-1'; DROP TABLE piece; --` stops being funny. The rule is simple and
absolute: a statement is a literal, and everything that varies about it is a
parameter.

There is one thing that cannot be a parameter, which is an identifier. A
table name has to be interpolated, and the four places that do it are listed
here by hand so that a fifth has to be argued for. Every one of them checks
the name first and quotes it after, because `nothing` is alphanumeric and is
also a SQLite keyword.
"""

from __future__ import annotations

import ast
import sys

from culmbin.tools.sources import relative, report, source_modules

SQL_WORDS = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE ", "PRAGMA ", "DROP ")

ALLOWED_INTERPOLATION = frozenset(
    {
        "culmbin.store.book",
        "culmbin.store.export",
        "culmbin.store.search",
        "culmbin.cli.main",
    }
)
"""The modules that interpolate a table name, each of which checks it first."""

SAFE_NAMES = frozenset({"_COLUMNS", "_CALL_COLUMNS", "where", "clauses"})
"""Module constants that are literal column lists rather than values.

They are literals written once at the top of a module and never built out of
anything a caller supplied, which is why interpolating them is not the thing
this check is about.
"""


def _is_sql(text: str) -> bool:
    """Whether a piece of text looks like the start of a statement."""
    stripped = text.lstrip()
    return any(stripped.upper().startswith(word) for word in SQL_WORDS)


def _interpolations(node: ast.JoinedStr) -> list[str]:
    """The names interpolated into a format string."""
    out = []
    for value in node.values:
        if isinstance(value, ast.FormattedValue):
            inner = value.value
            if isinstance(inner, ast.Name):
                out.append(inner.id)
            elif isinstance(inner, ast.Call):
                out.append(_call_name(inner))
            else:
                out.append(ast.dump(inner)[:40])
    return out


def _call_name(node: ast.Call) -> str:
    """What a call interpolated into a statement is really made of.

    A literal separator joined over a list of clause fragments is the list,
    not the call, so `" AND ".join(clauses)` reads as `clauses` and can be
    on the safe list where it belongs.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "join" and node.args:
        argument = node.args[0]
        if isinstance(argument, ast.Name):
            return argument.id
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ast.dump(func)[:40]


def problems() -> list[str]:
    """Every statement built out of something that is not a literal."""
    found = []
    for module in source_modules():
        where = relative(module.path)
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            text = "".join(
                value.value
                for value in node.values
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            )
            if not _is_sql(text):
                continue
            names = [name for name in _interpolations(node) if name not in SAFE_NAMES]
            if not names:
                continue
            if module.dotted in ALLOWED_INTERPOLATION:
                continue
            found.append(
                f"{where}:{node.lineno}: a statement interpolates {', '.join(names)}, "
                f"and a value reaches SQLite as a parameter."
            )
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "sql")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
