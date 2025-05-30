"""The intake desk, end to end.

These are the tests that run through the layers rather than into one of
them, so they are the ones that would notice a rule that is implemented and
never called.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from culmbin.errors import ConflictError, NotFoundError, StateError
from culmbin.intake.desk import (
    grade_load,
    settle_load,
    statement_for,
    summarise,
    take_sample,
    weigh_in,
)
from culmbin.model.enums import Basis, IntakeOutcome, Material, RejectionReason
from culmbin.model.intake import Delivery
from culmbin.model.results import Analysis, Result, analysis_of
from culmbin.store.book import Book
from culmbin.store.deliveries import get_delivery
from culmbin.store.gradings import get_grading
from culmbin.store.parties import close_party
from culmbin.units.season import Window

ARRIVED = dt.date(2025, 9, 18)
HARVESTED = dt.date(2025, 8, 14)
GRADED = dt.date(2025, 9, 19)
NOVEMBER = dt.date(2025, 11, 4)


def ticket(name: str = "W-24188", **kwargs: object) -> Delivery:
    fields: dict[str, object] = {
        "purchase": "P-2025-014",
        "party": "HOLB",
        "arrived": ARRIVED,
        "gross_kg": 43_820.0,
        "tare_kg": 15_640.0,
        "harvested": HARVESTED,
    }
    fields.update(kwargs)
    return Delivery(ticket=name, **fields)  # type: ignore[arg-type]


def sample(reference: str = "B-1", **overrides: float) -> Analysis:
    values: dict[str, float] = {
        "moisture": 12.5,
        "screenings": 1.4,
        "germ_capacity": 99.0,
        "germ_energy": 98.0,
        "admixture": 0.4,
    }
    nitrogen = overrides.pop("nitrogen", 1.62)
    values.update(overrides)
    results = [Result(code, value) for code, value in values.items()]
    results.append(Result("nitrogen", nitrogen, Basis.DRY))
    return analysis_of(reference, Material.BARLEY, ARRIVED, results)


def through(desk: Book, name: str = "W-24188", **overrides: float) -> None:
    """A whole lorry, tipped, sampled and graded."""
    weigh_in(desk, ticket(name))
    take_sample(desk, name, sample(f"B-{name}", **overrides))
    grade_load(desk, name, GRADED)


def test_a_load_goes_in_when_everything_lines_up(desk: Book) -> None:
    weigh_in(desk, ticket())
    assert get_delivery(desk, "W-24188").net_tonnes == pytest.approx(28.18)


def test_a_load_from_the_wrong_grower_is_refused(desk: Book) -> None:
    with pytest.raises(ConflictError, match="is with HOLB"):
        weigh_in(desk, ticket(party="WYKE"))


def test_a_load_from_somebody_who_has_stopped_trading_is_refused(desk: Book) -> None:
    close_party(desk, "HOLB", dt.date(2025, 8, 1))
    with pytest.raises(ConflictError, match="not trading"):
        weigh_in(desk, ticket())


def test_a_load_outside_the_window_is_refused(desk: Book) -> None:
    """It can still be taken in, once somebody extends the window on purpose."""
    with pytest.raises(ConflictError, match="runs 2025-09-01..2025-11-30"):
        weigh_in(desk, ticket(arrived=dt.date(2025, 12, 4), harvested=HARVESTED))


def test_a_load_on_a_withdrawn_variety_is_refused(desk: Book) -> None:
    """Propino went off the list in June, so it does not serve a September contract."""
    with pytest.raises(ConflictError, match="not on the approved list"):
        weigh_in(desk, ticket(purchase="P-2025-OLD"))


def test_a_load_against_a_purchase_that_is_not_there_is_refused(desk: Book) -> None:
    with pytest.raises(NotFoundError):
        weigh_in(desk, ticket(purchase="P-2025-999"))


def test_a_sample_goes_on_and_the_analysis_is_kept(desk: Book) -> None:
    weigh_in(desk, ticket())
    take_sample(desk, "W-24188", sample(), note="second grind")
    assert get_delivery(desk, "W-24188").sample == "B-1"


def test_a_malt_analysis_cannot_be_a_barley_sample(desk: Book) -> None:
    weigh_in(desk, ticket())
    malt = analysis_of("M-1", Material.MALT, ARRIVED, [Result("malt_moisture", 4.2)])
    with pytest.raises(ConflictError, match="malt analysis"):
        take_sample(desk, "W-24188", malt)


def test_a_failed_sample_leaves_no_analysis_behind(desk: Book) -> None:
    """The analysis and the reference go on together or not at all."""
    weigh_in(desk, ticket())
    take_sample(desk, "W-24188", sample("B-1"))
    with pytest.raises(ConflictError):
        take_sample(desk, "W-24188", sample("B-2"))
    assert desk.scalar("SELECT count(*) FROM analysis") == 1


def test_grading_writes_the_answer_down(desk: Book) -> None:
    through(desk)
    grading = get_grading(desk, "W-24188")
    assert grading.outcome is IntakeOutcome.ACCEPTED
    assert grading.settled_tonnes == pytest.approx(28.18)


def test_an_unsampled_load_cannot_be_graded(desk: Book) -> None:
    weigh_in(desk, ticket())
    with pytest.raises(StateError, match="has not been sampled"):
        grade_load(desk, "W-24188", GRADED)


def test_an_undated_load_cannot_be_graded(desk: Book) -> None:
    """Nothing can say whether it is new crop, so the screen cannot run."""
    weigh_in(desk, ticket(harvested=None))
    take_sample(desk, "W-24188", sample())
    with pytest.raises(StateError, match="no harvest date"):
        grade_load(desk, "W-24188", GRADED)


def test_grading_a_load_twice_is_refused(desk: Book) -> None:
    through(desk)
    with pytest.raises(ConflictError, match="already been graded"):
        grade_load(desk, "W-24188", GRADED)


def test_a_finding_rejects_a_load_the_lab_passed(desk: Book) -> None:
    weigh_in(desk, ticket())
    take_sample(desk, "W-24188", sample())
    grading = grade_load(desk, "W-24188", GRADED, findings=frozenset({RejectionReason.INSECT}))
    assert grading.rejected


def test_a_settled_load_is_worth_what_the_purchase_says(desk: Book) -> None:
    through(desk)
    settlement = settle_load(desk, "W-24188")
    assert settlement is not None
    assert settlement.base_per_tonne == Decimal("232.50")
    assert settlement.value == Decimal("6551.85")


def test_a_rejected_load_settles_to_nothing_at_all(desk: Book) -> None:
    through(desk, germ_capacity=90.0)
    assert settle_load(desk, "W-24188") is None


def test_an_ungraded_load_cannot_be_settled(desk: Book) -> None:
    weigh_in(desk, ticket())
    with pytest.raises(NotFoundError, match="has not been graded"):
        settle_load(desk, "W-24188")


def test_a_statement_carries_the_settled_loads_only(desk: Book) -> None:
    through(desk, "W-1")
    through(desk, "W-2", germ_capacity=90.0)
    weigh_in(desk, ticket("W-3"))
    statement = statement_for(desk, "HOLB", Window(ARRIVED, NOVEMBER))
    assert [item.ticket for item in statement] == ["W-1"]


def test_a_statement_for_somebody_with_nothing_is_empty(desk: Book) -> None:
    assert statement_for(desk, "WYKE", Window(ARRIVED, NOVEMBER)) == ()


def test_a_statement_stops_at_the_window(desk: Book) -> None:
    through(desk, "W-1")
    assert statement_for(desk, "HOLB", Window(dt.date(2025, 10, 1), NOVEMBER)) == ()


def test_a_summary_counts_what_was_graded(desk: Book) -> None:
    through(desk, "W-1")
    through(desk, "W-2", germ_capacity=90.0)
    summary = summarise(desk, Window(ARRIVED, NOVEMBER))
    assert summary.loads == 2
    assert summary.rejected == 1
    assert summary.rejection_rate == pytest.approx(50.0)


def test_a_summary_ignores_a_load_nobody_has_graded(desk: Book) -> None:
    weigh_in(desk, ticket("W-3"))
    assert summarise(desk, Window(ARRIVED, NOVEMBER)).loads == 0


def test_a_summary_of_nothing_has_no_rejection_rate(desk: Book) -> None:
    summary = summarise(desk, Window(ARRIVED, NOVEMBER))
    assert summary.loads == 0
    assert summary.rejection_rate == 0.0


def test_the_shrinkage_is_what_was_not_paid_for(desk: Book) -> None:
    through(desk, "W-1", moisture=15.0, screenings=3.4)
    summary = summarise(desk, Window(ARRIVED, NOVEMBER))
    assert summary.shrinkage_tonnes > 0.0
    assert summary.settled_tonnes < summary.net_tonnes
