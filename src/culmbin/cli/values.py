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
from culmbin.model.enums import KilnPhase, LegKind, Material
from culmbin.model.results import Result
from culmbin.model.spec import Clause
from culmbin.process.kiln import KilnStep
from culmbin.process.steep import SteepLeg

LEG_KINDS = {"wet": LegKind.WET_STAND, "air": LegKind.AIR_REST}
KILN_PHASES = {
    "dry": KilnPhase.FREE_DRYING,
    "break": KilnPhase.BREAK,
    "cure": KilnPhase.CURING,
}


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


def _three(text: str, what: str, shape: str) -> tuple[str, float, float]:
    """Read a `word:hours:degrees` triple, or say what it should look like."""
    parts = text.split(":")
    if len(parts) != 3:
        raise ValidationError(f"{text!r} is not a {what} like {shape}")
    word = parts[0].strip().lower()
    try:
        hours = float(parts[1])
        degrees = float(parts[2])
    except ValueError as exc:
        raise ValidationError(f"{text!r} is not a {what} like {shape}") from exc
    return word, hours, degrees


def parse_leg(text: str) -> SteepLeg:
    """Read a steep leg written `wet:8:14` or `air:16:16`."""
    word, hours, degrees = _three(text, "steep leg", "wet:8:14")
    if word not in LEG_KINDS:
        raise ValidationError(f"{word!r} is not a steep leg, which is wet or air")
    return SteepLeg(LEG_KINDS[word], hours, degrees)


def parse_step(text: str) -> KilnStep:
    """Read a kiln step written `dry:10:60`, `break:4:70` or `cure:4:85`."""
    word, hours, degrees = _three(text, "kiln step", "dry:10:60")
    if word not in KILN_PHASES:
        raise ValidationError(f"{word!r} is not a kiln step, which is dry, break or cure")
    return KilnStep(KILN_PHASES[word], hours, degrees)


def parse_clause(text: str) -> Clause:
    """Read a specification clause written the way a customer writes one.

    `colour<=4.5` is a ceiling, `extract_fine>=80.5` is a floor and
    `colour=2.5..4.5` is both. The basis is not typed for the same reason it
    is not typed on a result: it is a property of the determination.
    """
    for sign, floor in (("<=", False), (">=", True)):
        if sign in text:
            code, raw = (part.strip() for part in text.split(sign, 1))
            value = _number(raw, text)
            item = analyte(code)
            if floor:
                return Clause(code, item.basis, minimum=value)
            return Clause(code, item.basis, maximum=value)
    if "=" in text and ".." in text:
        code, raw = (part.strip() for part in text.split("=", 1))
        low, high = (part.strip() for part in raw.split("..", 1))
        item = analyte(code)
        return Clause(code, item.basis, minimum=_number(low, text), maximum=_number(high, text))
    raise ValidationError(f"{text!r} is not a clause like colour=2.5..4.5 or colour<=4.5")


def _number(raw: str, text: str) -> float:
    """Read the number out of a clause, or say what the clause looked like."""
    try:
        return float(raw)
    except ValueError as exc:
        raise ValidationError(f"{text!r} has {raw!r} where a number goes") from exc


def parse_draw(text: str) -> tuple[str, float]:
    """Read a blend part written `L-2025-0412:40`."""
    if text.count(":") != 1:
        raise ValidationError(f"{text!r} is not a draw like L-2025-0412:40")
    lot, raw = (part.strip() for part in text.split(":"))
    return lot, _number(raw, text)
