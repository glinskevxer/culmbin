"""Values reach SQLite as parameters, and the short list of names is the gate."""

from __future__ import annotations

import ast

from culmbin.tools import check_sql


def joined(text: str) -> ast.JoinedStr:
    """The format string in a one line expression."""
    node = ast.parse(text).body[0]
    assert isinstance(node, ast.Expr)
    assert isinstance(node.value, ast.JoinedStr)
    return node.value


def test_the_check_passes_on_this_tree() -> None:
    assert check_sql.problems() == []


def test_a_statement_is_recognised_by_its_first_word() -> None:
    assert check_sql._is_sql("SELECT code FROM party")
    assert check_sql._is_sql("  INSERT INTO party VALUES (?)")
    assert not check_sql._is_sql("the grower was not trading")


def test_an_interpolated_name_is_found() -> None:
    names = check_sql._interpolations(joined('f"SELECT * FROM party WHERE code = {code}"'))
    assert names == ["code"]


def test_a_joined_clause_list_reads_as_the_list() -> None:
    """`" AND ".join(clauses)` is the list, not the call, so it can be on the safe list."""
    names = check_sql._interpolations(joined("f\"SELECT 1 WHERE {' AND '.join(clauses)}\""))
    assert names == ["clauses"]


def test_a_call_reads_as_the_thing_being_called() -> None:
    names = check_sql._interpolations(joined('f"SELECT * FROM {table(name)}"'))
    assert names == ["table"]


def test_the_column_lists_are_the_only_safe_names() -> None:
    assert "_COLUMNS" in check_sql.SAFE_NAMES
    assert "code" not in check_sql.SAFE_NAMES


def test_only_one_module_may_interpolate_a_table_name() -> None:
    """A second has to be argued for, which is the point of the list."""
    assert frozenset({"culmbin.store.book"}) == check_sql.ALLOWED_INTERPOLATION
