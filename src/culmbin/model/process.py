"""A piece: one batch of barley on its way to being malt.

A piece keeps its identity all the way through. It is charged into a steep
as so many tonnes of barley at so much moisture, it comes out of the steep
half as heavy again in water, it loses dry matter on the floor to
respiration and rootlets, and it comes off the kiln as malt. The tonnage
changes at every step and the piece does not.

What is constant is not the weight. It is the dry matter, and even that only
until germination starts eating it. So the charge is recorded as delivered,
wet, and everything downstream is worked off the dry matter it carried,
because that is the only number two stages can be compared on.

A piece moves forwards. There is no going back to the steep, and the
enumeration in `model.enums` is the order. A piece that has gone wrong is
written off, which is not a stage on the path and can happen from any of
them.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from culmbin.errors import StateError, ValidationError
from culmbin.model.enums import MaltStyle, PieceStage, VesselKind, stage_follows
from culmbin.units.mass import dry_matter

STAGE_VESSEL: dict[PieceStage, VesselKind | None] = {
    PieceStage.STEEPING: VesselKind.STEEP,
    PieceStage.GERMINATING: None,
    PieceStage.KILNING: VesselKind.KILN,
    PieceStage.KILNED: None,
    PieceStage.BINNED: None,
    PieceStage.WRITTEN_OFF: None,
}
"""Which kind of vessel each stage happens in.

`None` means either it is not in a vessel at all, or the stage takes more
than one kind. Germination is the second sort: a piece can be in a box or on
a floor, and which one is a decision about the malt rather than about the
stage.
"""

GERMINATION_KINDS = frozenset({VesselKind.BOX, VesselKind.FLOOR})


@dataclass(frozen=True, slots=True)
class Piece:
    """One batch, wherever it has got to."""

    code: str
    variety: str
    crop_year: int
    style: MaltStyle
    charge_tonnes: float
    charge_moisture: float
    started: dt.date
    stage: PieceStage
    vessel: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("a piece needs a code")
        if self.charge_tonnes <= 0.0:
            raise ValidationError(f"{self.code} was charged with {self.charge_tonnes} tonnes")
        dry_matter(self.charge_tonnes, self.charge_moisture)
        if self.stage in (PieceStage.STEEPING, PieceStage.GERMINATING, PieceStage.KILNING):
            if self.vessel is None:
                raise ValidationError(f"{self.code} is {self.stage} and is not in anything")
        elif self.vessel is not None:
            raise ValidationError(f"{self.code} is {self.stage} and is still in {self.vessel}")

    @property
    def charge_dry_tonnes(self) -> float:
        """The dry matter charged into the steep.

        Everything the piece does afterwards is measured against this, so it
        is worked from the charge weight and the charge moisture rather than
        stored, because two numbers that should agree eventually do not.
        """
        return dry_matter(self.charge_tonnes, self.charge_moisture)

    @property
    def in_process(self) -> bool:
        """Whether the piece is still somewhere in the plant."""
        return self.stage in (
            PieceStage.STEEPING,
            PieceStage.GERMINATING,
            PieceStage.KILNING,
        )

    @property
    def finished(self) -> bool:
        """Whether the piece has come off the kiln, one way or the other."""
        return self.stage in (PieceStage.KILNED, PieceStage.BINNED, PieceStage.WRITTEN_OFF)

    def moved_to(self, stage: PieceStage, vessel: str | None = None) -> Piece:
        """The piece at its next stage.

        Refuses to go backwards or to stand still. A piece that is already
        germinating and is moved to germinating again is a second box, which
        is a real thing and is not this: it is a split, and a split makes two
        pieces.
        """
        if stage is PieceStage.WRITTEN_OFF:
            raise StateError(f"{self.code} is written off rather than moved, so use write_off")
        if not stage_follows(self.stage, stage):
            raise StateError(f"{self.code} is {self.stage} and cannot go to {stage}")
        return Piece(
            code=self.code,
            variety=self.variety,
            crop_year=self.crop_year,
            style=self.style,
            charge_tonnes=self.charge_tonnes,
            charge_moisture=self.charge_moisture,
            started=self.started,
            stage=stage,
            vessel=vessel,
        )

    def written_off(self) -> Piece:
        """The piece written off, from wherever it had got to.

        A write off is not on the path, so it is not a move. It can happen at
        any stage, including from one that is already finished, because malt
        can be condemned in the bin.
        """
        if self.stage is PieceStage.WRITTEN_OFF:
            raise StateError(f"{self.code} is already written off")
        return Piece(
            code=self.code,
            variety=self.variety,
            crop_year=self.crop_year,
            style=self.style,
            charge_tonnes=self.charge_tonnes,
            charge_moisture=self.charge_moisture,
            started=self.started,
            stage=PieceStage.WRITTEN_OFF,
            vessel=None,
        )

    def vessel_kind_ok(self, kind: VesselKind) -> bool:
        """Whether a vessel of a kind can hold this piece at its stage."""
        if self.stage is PieceStage.GERMINATING:
            return kind in GERMINATION_KINDS
        return STAGE_VESSEL[self.stage] is kind

    def __str__(self) -> str:
        where = f" in {self.vessel}" if self.vessel else ""
        return f"{self.code} {self.charge_tonnes:.1f}t {self.stage}{where}"
