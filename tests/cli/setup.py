"""Setting a book up through the console script, once.

Five test files had each written the same twenty lines: a variety, three
vessels and a recipe of each kind. They had drifted, as duplicated setup
always does. One of them built a box with a hundred and twenty square metres
of floor, which will not take the steep out weight of the charge the same
file goes on to make, and the test passed because it never cast anything.

Everything here goes through the console script rather than through the
store, which is the point of a CLI test: the setup exercises the commands
too, so a command that stops working is caught by every file that uses it.
"""

from __future__ import annotations

from tests.cli.conftest import Invoke

GOOD_SAMPLE = (
    "--result",
    "moisture=12.5",
    "--result",
    "screenings=1.4",
    "--result",
    "germ_capacity=99.0",
    "--result",
    "germ_energy=98.0",
    "--result",
    "admixture=0.4",
    "--result",
    "nitrogen=1.62",
)

MALT_RESULTS = (
    "--result",
    "malt_moisture=4.2",
    "--result",
    "extract_fine=81.4",
    "--result",
    "colour=3.4",
)


def a_variety(invoke: Invoke, code: str = "LAUR", name: str = "Laureate") -> None:
    """One variety on the approved list."""
    invoke("variety", "add", code, name, "--approval", "approved", on="2018-12-01")


def a_grower(invoke: Invoke, code: str = "HOLB", name: str = "Holbeach Grange") -> None:
    """One grower, trading since 2011."""
    invoke("party", "add", code, name, "--role", "grower", "--holding", "12/345", on="2011-06-01")


def a_customer(invoke: Invoke, code: str = "BRWY", name: str = "Sheldrake Brewing") -> None:
    """One customer, trading since 2016."""
    invoke("party", "add", code, name, "--role", "customer", on="2016-02-01")


def the_plant(invoke: Invoke) -> None:
    """A steep, a box, a kiln, and a recipe of each kind for pale ale.

    The box is a hundred and seventy square metres because a forty five
    tonne charge comes out of the steep at about seventy two tonnes, and a
    box sized for the barley cannot take the piece.
    """
    a_variety(invoke)
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", on="1998-04-01")
    invoke(
        "vessel",
        "add",
        "G1",
        "box 1",
        "--kind",
        "box",
        "--area",
        "170",
        "--depth",
        "90",
        on="1998-04-01",
    )
    invoke(
        "vessel",
        "add",
        "K1",
        "kiln 1",
        "--kind",
        "kiln",
        "--area",
        "140",
        "--depth",
        "100",
        on="1998-04-01",
    )
    invoke(
        "recipe", "programme", "p", "--style", "pale_ale", "--leg", "wet:8:14", "--target", "44.5"
    )
    invoke("recipe", "schedule", "s", "--style", "pale_ale", "--target", "1200")
    invoke(
        "recipe",
        "curve",
        "c",
        "--style",
        "pale_ale",
        "--step",
        "dry:10:60",
        "--step",
        "cure:4:85",
        "--target",
        "4.2",
    )


def a_purchase(invoke: Invoke, code: str = "P-1", party: str = "HOLB") -> None:
    """A standard and a purchase to deliver against."""
    invoke("standard", "add", "malting 2025")
    invoke(
        "purchase",
        "add",
        code,
        party,
        "LAUR",
        "--tonnes",
        "480",
        "--price",
        "232.50",
        "--standard",
        "malting 2025",
        "--crop",
        "2025",
        "--from",
        "2025-09-01",
        "--to",
        "2025-11-30",
        on="2025-03-12",
    )


def a_charge(
    invoke: Invoke, code: str = "2025-118", steep: str = "S1", share: bool = False
) -> None:
    """A piece charged into a steep on the third of November."""
    extra = ["--share"] if share else []
    invoke(
        "piece",
        "charge",
        code,
        "--variety",
        "LAUR",
        "--crop",
        "2025",
        "--style",
        "pale_ale",
        "--steep",
        steep,
        "--tonnes",
        "45",
        "--moisture",
        "12",
        "--programme",
        "p",
        "--schedule",
        "s",
        "--curve",
        "c",
        *extra,
        on="2025-11-03",
    )


def a_cast_piece(invoke: Invoke, code: str = "2025-118", box: str = "G1") -> None:
    """A piece charged and cast into a bed."""
    a_charge(invoke, code)
    invoke(
        "piece",
        "cast",
        code,
        "--into",
        box,
        "--tonnes",
        "71.8",
        "--moisture",
        "44.8",
        "--depth",
        "85",
        on="2025-11-05",
    )


def a_stripped_piece(invoke: Invoke, code: str = "2025-118") -> None:
    """A piece taken all the way through to the malt bin door."""
    a_cast_piece(invoke, code)
    invoke("piece", "kiln", code, "--into", "K1", on="2025-11-08")
    invoke(
        "piece",
        "strip",
        code,
        "--malt",
        "37.9",
        "--moisture",
        "4.4",
        "--culm",
        "1.9",
        on="2025-11-09",
    )
