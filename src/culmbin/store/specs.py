"""Reading and writing specifications.

A specification is written once and not edited, for the same reason a
quality standard is not: contracts name it, certificates are assessed
against it, and a clause that quietly moved restates whether malt already
shipped was in specification.

The clause order is kept, because a specification sheet is read in the order
the customer wrote it and a report that reorders it is a report somebody has
to check line by line against the original.
"""

from __future__ import annotations

from culmbin.errors import ConflictError, NotFoundError
from culmbin.model.enums import Basis, Material
from culmbin.model.spec import Clause, Specification
from culmbin.store.book import Book
from culmbin.store.query import optional
from culmbin.store.rows import as_enum, as_optional_number, as_optional_text, as_text


def save_specification(book: Book, spec: Specification) -> Specification:
    """Write a specification, its clauses and the varieties it names."""
    with book.writing() as writing:
        writing.execute(
            "INSERT INTO specification (name, material) VALUES (?, ?)",
            (spec.name, spec.material),
        )
        writing.executemany(
            "INSERT INTO clause (specification, seq, code, basis, minimum, maximum) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (spec.name, seq, clause.code, clause.basis, clause.minimum, clause.maximum)
                for seq, clause in enumerate(spec.clauses, start=1)
            ],
        )
        writing.executemany(
            "INSERT INTO specification_variety (specification, variety) VALUES (?, ?)",
            [(spec.name, variety) for variety in sorted(spec.varieties)],
        )
    return spec


def get_specification(book: Book, name: str) -> Specification:
    """One specification, or say which one was asked for."""
    row = book.first("SELECT name, material FROM specification WHERE name = ?", (name,))
    if row is None:
        raise NotFoundError(f"no specification called {name!r}")
    clauses = book.query(
        "SELECT code, basis, minimum, maximum FROM clause WHERE specification = ? ORDER BY seq",
        (name,),
    )
    varieties = book.query(
        "SELECT variety FROM specification_variety WHERE specification = ? ORDER BY variety",
        (name,),
    )
    return Specification(
        name=as_text(row, "name"),
        material=as_enum(row, "material", Material),
        clauses=tuple(
            Clause(
                code=as_text(clause, "code"),
                basis=None
                if as_optional_text(clause, "basis") is None
                else Basis(as_text(clause, "basis")),
                minimum=as_optional_number(clause, "minimum"),
                maximum=as_optional_number(clause, "maximum"),
            )
            for clause in clauses
        ),
        varieties=frozenset(as_text(item, "variety") for item in varieties),
    )


def find_specification(book: Book, name: str) -> Specification | None:
    """One specification, or nothing."""
    return optional(lambda: get_specification(book, name))


def list_specifications(book: Book, material: Material | None = None) -> tuple[Specification, ...]:
    """Every specification, in name order."""
    if material is None:
        rows = book.query("SELECT name FROM specification ORDER BY name")
    else:
        rows = book.query(
            "SELECT name FROM specification WHERE material = ? ORDER BY name", (material,)
        )
    return tuple(get_specification(book, as_text(row, "name")) for row in rows)


def copy_specification(book: Book, name: str, into: str) -> Specification:
    """Write a new specification with the clauses of an old one.

    This is how next season's starts. Copying onto a name that is taken is
    refused, because that would be an edit of something already quoted.
    """
    if find_specification(book, into) is not None:
        raise ConflictError(f"there is already a specification called {into!r}")
    old = get_specification(book, name)
    return save_specification(book, Specification(into, old.material, old.clauses, old.varieties))


def specifications_using(book: Book, code: str) -> tuple[str, ...]:
    """Every specification with a clause about one analyte, in name order.

    The laboratory uses this the other way round from everybody else: a
    method has changed, and the question is whose specification cares.
    """
    rows = book.query(
        "SELECT DISTINCT specification FROM clause WHERE code = ? ORDER BY specification", (code,)
    )
    return tuple(as_text(row, "specification") for row in rows)
