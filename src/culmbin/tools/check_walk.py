"""Every command the console script has is run by the walk in CI, or excused.

`check_workflow` asks the other question: that every command the walk runs
is a real one. This asks whether every real one is run, which is the half
that finds a command nobody has exercised since the afternoon it was
written.

A command can be excused, and the list is short and each entry says why.
Excusing one is a decision; forgetting one is what this stops.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping

from culmbin.tools.check_help import command_names
from culmbin.tools.check_workflow import WORKFLOW, walk_commands, workflow_path
from culmbin.tools.sources import report

EXCUSED: Mapping[str, str] = {
    "cli": "the group itself, which is not a command",
    "cli complaint": "a group",
    "cli contract": "a group",
    "cli call": "a group",
    "cli clean": "a group",
    "cli delivery": "a group",
    "cli gas": "a group",
    "cli journal": "a group",
    "cli lot": "a group",
    "cli bin": "a group",
    "cli party": "a group",
    "cli piece": "a group",
    "cli purchase": "a group",
    "cli recipe": "a group",
    "cli report": "a group",
    "cli ship": "a group",
    "cli silo": "a group",
    "cli spec": "a group",
    "cli standard": "a group",
    "cli trace": "a group",
    "cli variety": "a group",
    "cli vessel": "a group",
    "cli water": "a group",
    "cli complaint attach": "needs a shipment the walk has already despatched",
    "cli complaint close": "closing needs a complaint raised in the same walk",
    "cli complaint investigate": "the state between raising and closing",
    "cli complaint raise": "covered by the quality tests, which need a customer",
    "cli complaint list": "the same page as report complaints",
    "cli clean interval": "the cleaning book is exercised by its own tests",
    "cli clean record": "the cleaning book is exercised by its own tests",
    "cli clean due": "the cleaning book is exercised by its own tests",
    "cli clean show": "the cleaning book is exercised by its own tests",
    "cli gas record": "needs a stripped piece and a meter reading in the same walk",
    "cli gas show": "reads what gas record wrote",
    "cli gas list": "the same page as report gas",
    "cli gas suspect": "reads what gas record wrote",
    "cli gas waiting": "reads what gas record wrote",
    "cli water list": "the same page as report water",
    "cli water waiting": "reads what water record wrote",
    "cli journal show": "reads what every other command wrote",
    "cli journal who": "reads what every other command wrote",
    "cli lot load": "needs a file on disk, which a yaml walk should not be writing",
    "cli migrations": "says the same as version on a book that is up to date",
    "cli party close": "would take the grower out from under the rest of the walk",
    "cli party show": "covered by party list",
    "cli piece writeoff": "would take the piece out from under the rest of the walk",
    "cli purchase extend": "the walk stays inside its window",
    "cli purchase list": "covered by purchase show",
    "cli ship cancel": "would take the shipment out from under the rest of the walk",
    "cli silo sweep": "the walk leaves barley in the silo",
    "cli bin clean": "the walk leaves malt in the bin",
    "cli spec copy": "copying is exercised by its own tests",
    "cli standard copy": "copying is exercised by its own tests",
    "cli standard list": "covered by standard show",
    "cli variety promote": "the walk adds a variety already approved",
    "cli variety withdraw": "would take the variety out from under the rest of the walk",
    "cli vessel list": "covered by vessel show",
    "cli vessel retire": "would take the vessel out from under the rest of the walk",
    "cli party add": "run twice by the walk under its own name",
    "cli report grower": "run by the walk with a grower argument",
}


def run_by_the_walk() -> set[str]:
    """Every command the walk actually runs, as the click tree names it."""
    known = set(command_names())
    out = set()
    for command in walk_commands():
        words = []
        skip = False
        for token in command.split()[1:]:
            if skip:
                skip = False
                continue
            if token.startswith("--"):
                skip = "=" not in token
                continue
            words.append(token)
        for depth in range(len(words), 0, -1):
            candidate = "cli " + " ".join(words[:depth])
            if candidate in known:
                out.add(candidate)
                break
    return out


def problems() -> list[str]:
    """Every command the walk never runs and nobody has excused."""
    if not workflow_path().exists():
        return [f"{WORKFLOW}: there is no workflow to read."]
    run = run_by_the_walk()
    found = [
        f"{WORKFLOW}: the walk never runs {name!r}, and nothing excuses it."
        for name in sorted(set(command_names()) - run - set(EXCUSED))
    ]
    found += [
        f"{WORKFLOW}: {name!r} is excused and is not a command any more."
        for name in sorted(set(EXCUSED) - set(command_names()))
    ]
    return found


def main() -> int:
    """Print the problems and give back an exit status."""
    return report(problems(), "walk")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
