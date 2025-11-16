"""A floor under the total and a floor per file.

One number is not enough. A package can sit at ninety six percent overall
with one module at forty, and that module is nearly always the one that was
written last and is doing the most.

So there are two floors, and the worst files are printed whether the gate
passes or not, because the list is the useful part.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from culmbin.tools.sources import project_root

REPORT = "coverage.json"


@dataclass(frozen=True, slots=True)
class FileCoverage:
    """One file's line coverage."""

    name: str
    covered: int
    total: int

    @property
    def percent(self) -> float:
        """Covered lines as a percentage, with an empty file counting as covered."""
        return 100.0 if self.total == 0 else self.covered / self.total * 100.0


def read_report(path: Path) -> tuple[float, list[FileCoverage]]:
    """The total and every file, out of a coverage json report."""
    data = json.loads(path.read_text(encoding="utf-8"))
    total = float(data["totals"]["percent_covered"])
    files = []
    for name, entry in sorted(data["files"].items()):
        summary = entry["summary"]
        files.append(
            FileCoverage(
                name=name,
                covered=int(summary["covered_lines"]),
                total=int(summary["num_statements"]),
            )
        )
    return total, files


def problems(total: float, files: list[FileCoverage], floor: float, file_floor: float) -> list[str]:
    """Everything under a floor, the total first."""
    found = []
    if total < floor:
        found.append(f"the package is at {total:.2f}% against a floor of {floor:.0f}%.")
    for entry in sorted(files, key=lambda item: item.percent):
        if entry.percent < file_floor:
            found.append(
                f"{entry.name} is at {entry.percent:.2f}% against a file floor of "
                f"{file_floor:.0f}%."
            )
    return found


def main(argv: list[str] | None = None) -> int:
    """Read the report, print the worst files, and gate on the two floors."""
    parser = argparse.ArgumentParser(description="gate on coverage")
    parser.add_argument("--floor", type=float, default=95.0)
    parser.add_argument("--file-floor", type=float, default=80.0)
    parser.add_argument("--worst", type=int, default=5)
    parser.add_argument("--report", type=Path, default=project_root() / REPORT)
    arguments = parser.parse_args(argv)
    if not arguments.report.exists():
        print(f"coverage: there is no report at {arguments.report}.")
        return 1
    total, files = read_report(arguments.report)
    print(f"coverage: {total:.2f}% over {len(files)} files.")
    for entry in sorted(files, key=lambda item: item.percent)[: arguments.worst]:
        print(f"  {entry.percent:6.2f}%  {entry.name}")
    found = problems(total, files, arguments.floor, arguments.file_floor)
    for problem in found:
        print(problem)
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
