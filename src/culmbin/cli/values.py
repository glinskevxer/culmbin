"""Reading results off a command line.

Results arrive as `code=value` pairs, and the basis is not typed: it comes
off the analyte table, because the laboratory reports each determination on
one basis and typing it every time is how it eventually gets typed wrong.

That is the whole module. It is separate because three command groups take
results and none of them should be parsing them itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from culmbin.errors import ValidationError
from culmbin.model.analytes import analyte
from culmbin.model.enums import Material
from culmbin.model.results import Result


def parse_result(text: str) -> Result:
    """Read one `code=value` pair.

    The basis comes off the table rather than the command line. A caller who
    wants a result on the other basis converts it before typing it, which is
    a conversation with the laboratory rather than a command line option.
    """
    if text.count("=") != 1:
        raise ValidationError(f"{text!r} is not a result like extract_fine=81.4")
    code, raw = (part.strip() for part in text.split("="))
    item = analyte(code)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValidationError(f"{raw!r} is not a number for {item.label}") from exc
    return Result(code, value, item.basis)


def parse_results(items: Sequence[str], material: Material) -> list[Result]:
    """Read several pairs and check they are all about the same material."""
    results = [parse_result(item) for item in items]
    for result in results:
        found = analyte(result.code).material
        if found is not material:
            raise ValidationError(
                f"{analyte(result.code).label} is a {found} determination "
                f"and this is a {material} sample"
            )
    return results
