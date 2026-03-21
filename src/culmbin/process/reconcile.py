"""The month end walk: barley in, malt out, and what does not add up.

Every stage of the building is measured twice, once on the way out of one
thing and once on the way into the next, and the two never agree exactly.
The job of a reconciliation is not to make them agree. It is to say by how
much, in a unit that can be compared with last month.

Everything here is worked in **dry matter**, which is the only quantity that
survives the whole building. Barley comes in wet, steeps wetter, dries on
the kiln and goes out at four and a half percent, and comparing any two of
those on their delivered weights is comparing water.

The three gaps this finds, and what each one usually is:

**Intake to silo.** Settled tonnes graded against tonnes tipped. A gap here
is loads that were graded and never tipped, which is the pit list, or loads
tipped and never graded, which the book does not allow.

**Silo to steep.** Tonnes drawn against tonnes charged. These are the same
number by construction, so a gap here is a piece charged without going
through the yard, which is legal and worth knowing about.

**Steep to malt.** Barley dry matter charged against malt dry matter off the
kiln. This one is *supposed* to have a gap: it is the malting loss, and a
month where it is under six or over twelve percent has something wrong with
a weighbridge rather than with the malting.
"""

from __future__ import annotations

from dataclasses import dataclass

from culmbin.store.book import Book
from culmbin.store.pieces import list_pieces, weighings
from culmbin.units.mass import dry_matter
from culmbin.units.season import Window

LOSS_FLOOR = 6.0
LOSS_CEILING = 12.0


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What went in, what came out, and the three gaps between."""

    window: Window
    graded_tonnes: float
    tipped_tonnes: float
    charged_tonnes: float
    charged_dry: float
    malt_tonnes: float
    malt_dry: float
    culm_tonnes: float

    @property
    def pit_gap(self) -> float:
        """Settled tonnes graded that have not been tipped into a silo."""
        return self.graded_tonnes - self.tipped_tonnes

    @property
    def malting_loss(self) -> float:
        """Dry matter lost between the steep and the kiln, as a percentage."""
        if self.charged_dry <= 0.0:
            return 0.0
        return (self.charged_dry - self.malt_dry) / self.charged_dry * 100.0

    @property
    def yield_percent(self) -> float:
        """Malt tonnes out over barley tonnes charged, both as they lie."""
        if self.charged_tonnes <= 0.0:
            return 0.0
        return self.malt_tonnes / self.charged_tonnes * 100.0

    @property
    def loss_is_credible(self) -> bool:
        """Whether the malting loss is inside what malting can actually do.

        Outside it, something is wrong with a weighbridge rather than with
        the malting, and that is the thing to go and look at.
        """
        if self.charged_dry <= 0.0:
            return True
        return LOSS_FLOOR <= self.malting_loss <= LOSS_CEILING

    @property
    def culm_share(self) -> float:
        """The culm as a share of the dry matter lost, as a fraction of one."""
        lost = self.charged_dry - self.malt_dry
        return 0.0 if lost <= 0.0 else self.culm_tonnes / lost

    def notes(self) -> tuple[str, ...]:
        """Every gap worth a sentence, in the order somebody would read them."""
        said = []
        if abs(self.pit_gap) > 0.01:
            said.append(f"{self.pit_gap:.2f}t graded and not tipped, which is barley in the pit")
        if self.charged_dry > 0.0 and not self.loss_is_credible:
            said.append(
                f"malting loss of {self.malting_loss:.2f}% is outside "
                f"{LOSS_FLOOR:.0f} to {LOSS_CEILING:.0f}, so look at a weighbridge"
            )
        if not said:
            said.append("nothing in the month needs explaining")
        return tuple(said)


def reconcile(book: Book, window: Window) -> Reconciliation:
    """Walk a month from the weighbridge to the malt bin."""
    graded = float(
        book.scalar(
            "SELECT total(settled_tonnes) FROM grading WHERE graded_on >= ? AND graded_on <= ?",
            (window.start.isoformat(), window.end.isoformat()),
        )
        or 0.0
    )
    tipped = float(
        book.scalar(
            "SELECT total(r.tonnes) FROM silo_receipt r JOIN grading g ON g.ticket = r.ticket "
            "WHERE g.graded_on >= ? AND g.graded_on <= ?",
            (window.start.isoformat(), window.end.isoformat()),
        )
        or 0.0
    )
    charged = 0.0
    charged_dry = 0.0
    malt = 0.0
    malt_dry = 0.0
    culm = 0.0
    for piece in list_pieces(book):
        if not window.contains(piece.started):
            continue
        charged += piece.charge_tonnes
        charged_dry += piece.charge_dry_tonnes
        weights = weighings(book, piece.code)
        if "off_kiln" in weights:
            tonnes, moisture = weights["off_kiln"]
            assert moisture is not None
            malt += tonnes
            malt_dry += dry_matter(tonnes, moisture)
        if "culm" in weights:
            culm += weights["culm"][0]
    return Reconciliation(
        window=window,
        graded_tonnes=graded,
        tipped_tonnes=tipped,
        charged_tonnes=charged,
        charged_dry=charged_dry,
        malt_tonnes=malt,
        malt_dry=malt_dry,
        culm_tonnes=culm,
    )


def drawn_against_charged(book: Book, window: Window) -> float:
    """Tonnes drawn out of silos against tonnes charged into steeps.

    Zero on a month where every piece came out of the yard. Anything else is
    a piece charged without going through a silo, which is legal and worth
    knowing about.
    """
    drawn = float(
        book.scalar(
            "SELECT total(s.tonnes) FROM piece_source s JOIN piece p ON p.code = s.piece "
            "WHERE p.started >= ? AND p.started <= ?",
            (window.start.isoformat(), window.end.isoformat()),
        )
        or 0.0
    )
    charged = sum(
        piece.charge_tonnes for piece in list_pieces(book) if window.contains(piece.started)
    )
    return charged - drawn
