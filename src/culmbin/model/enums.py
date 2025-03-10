"""The closed vocabularies.

Everything in here is closed because the alternative is a free text column
that eventually holds `kilning`, `Kilning`, `in kiln` and `KILN` for the same
thing. They are string enumerations so that the value written into the book
is the name and not an integer nobody can read in a `sqlite3` shell.

What is deliberately *not* an enumeration is barley variety. Varieties are
added and withdrawn every year by somebody who is not a programmer, so they
live in a register table in the book.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class Basis(StrEnum):
    """Which weight a percentage is a percentage of.

    Every result in the package carries one of these. A result without a
    basis is not a result, it is a number somebody remembers the basis of.
    """

    AS_IS = "as_is"
    DRY = "dry"


@unique
class Material(StrEnum):
    """Barley or malt.

    The same word means different things either side of the kiln. Moisture on
    barley is around twelve percent and on malt around four, and a
    specification clause that does not say which material it is about will
    eventually be read against the wrong one.
    """

    BARLEY = "barley"
    MALT = "malt"


@unique
class Habit(StrEnum):
    """Spring or winter barley.

    It matters because winter barley is generally higher nitrogen and comes
    off the field earlier, so the two are contracted separately even when the
    variety is approved for both.
    """

    SPRING = "spring"
    WINTER = "winter"


@unique
class IntakeOutcome(StrEnum):
    """What happened to a lorry load at the weighbridge.

    `REJECTED` is not the bottom of the deduction schedule. A rejected load
    has no settlement at all, and the schedule does not apply to it.
    """

    ACCEPTED = "accepted"
    ACCEPTED_ON_DEDUCTION = "accepted_on_deduction"
    REJECTED = "rejected"


@unique
class RejectionReason(StrEnum):
    """Why a load went back down the road.

    The first four are gradings. The last three are findings, and a finding
    rejects a load whatever the grading says, which is why they are in the
    same enumeration rather than in a schedule.
    """

    GERMINATION = "germination"
    MOISTURE = "moisture"
    SCREENINGS = "screenings"
    NITROGEN = "nitrogen"
    INSECT = "insect"
    ODOUR = "odour"
    TREATED_SEED = "treated_seed"


@unique
class VesselKind(StrEnum):
    """The four kinds of thing a piece of malt can be sitting in."""

    STEEP = "steep"
    BOX = "box"
    FLOOR = "floor"
    KILN = "kiln"


@unique
class PieceStage(StrEnum):
    """Where a piece has got to.

    The order here is the order a piece goes through, and the package relies
    on that: `STEEPING` is before `GERMINATING` because it is written above
    it, and there is a test that will notice if somebody sorts this file.
    """

    STEEPING = "steeping"
    GERMINATING = "germinating"
    KILNING = "kilning"
    KILNED = "kilned"
    BINNED = "binned"
    WRITTEN_OFF = "written_off"


@unique
class LegKind(StrEnum):
    """A steep is wet stands and air rests, and nothing else."""

    WET_STAND = "wet_stand"
    AIR_REST = "air_rest"


@unique
class KilnPhase(StrEnum):
    """The three parts of a kiln curve, in the order the kiln runs them."""

    FREE_DRYING = "free_drying"
    BREAK = "break"
    CURING = "curing"


@unique
class MaltStyle(StrEnum):
    """What the malt is meant to be when it comes off the kiln."""

    LAGER = "lager"
    PALE_ALE = "pale_ale"
    DISTILLING = "distilling"
    VIENNA = "vienna"


@unique
class BinState(StrEnum):
    """What a malt bin is doing.

    A sealed bin can be drawn from and cannot be added to. That is the whole
    reason the state exists: it is what makes a lot's analysis mean anything,
    because the thing that was sampled is the thing that is still in there.
    """

    EMPTY = "empty"
    FILLING = "filling"
    SEALED = "sealed"
    DRAWING = "drawing"


@unique
class ContractState(StrEnum):
    """Where a supply contract has got to."""

    DRAFT = "draft"
    SIGNED = "signed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@unique
class ShipmentState(StrEnum):
    """Where a load of malt going out has got to."""

    PLANNED = "planned"
    LOADED = "loaded"
    DESPATCHED = "despatched"
    CANCELLED = "cancelled"


@unique
class Conformance(StrEnum):
    """Whether a result meets a clause.

    `UNTESTED` is not a failure and it is not a pass either. A specification
    with an untested clause has not been assessed, and reporting that as a
    pass is how malt leaves the building against a clause nobody looked at.
    """

    PASS = "pass"
    FAIL = "fail"
    UNTESTED = "untested"


STAGE_ORDER: tuple[PieceStage, ...] = (
    PieceStage.STEEPING,
    PieceStage.GERMINATING,
    PieceStage.KILNING,
    PieceStage.KILNED,
    PieceStage.BINNED,
)
"""The stages a piece passes through, in order, with the write off left out.

A piece can be written off from any stage, so it is not on the path and does
not belong in a sequence that is used to answer what comes next.
"""


def stage_follows(earlier: PieceStage, later: PieceStage) -> bool:
    """Whether one stage comes after another on the normal path.

    A write off is not on the path, so nothing follows it and it follows
    nothing. Callers asking about a written off piece get `False` both ways,
    which is the answer, not a missing case.
    """
    if earlier not in STAGE_ORDER or later not in STAGE_ORDER:
        return False
    return STAGE_ORDER.index(later) > STAGE_ORDER.index(earlier)
