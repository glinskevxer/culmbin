"""A floor under the total and a floor per file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from culmbin.tools import coverage_gate
from culmbin.tools.coverage_gate import FileCoverage


def a_report(path: Path, total: float, files: dict[str, tuple[int, int]]) -> Path:
    path.write_text(
        json.dumps(
            {
                "totals": {"percent_covered": total},
                "files": {
                    name: {"summary": {"covered_lines": covered, "num_statements": statements}}
                    for name, (covered, statements) in files.items()
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_a_file_percent_is_covered_over_total() -> None:
    assert FileCoverage("a.py", 8, 10).percent == pytest.approx(80.0)


def test_an_empty_file_counts_as_covered() -> None:
    assert FileCoverage("a.py", 0, 0).percent == pytest.approx(100.0)


def test_a_report_reads_back(tmp_path: Path) -> None:
    path = a_report(tmp_path / "coverage.json", 96.0, {"a.py": (8, 10)})
    total, files = coverage_gate.read_report(path)
    assert total == pytest.approx(96.0)
    assert files[0].name == "a.py"


def test_a_total_under_the_floor_is_a_problem() -> None:
    found = coverage_gate.problems(90.0, [], 95.0, 80.0)
    assert any("against a floor of 95%" in item for item in found)


def test_one_thin_file_hides_in_a_good_total() -> None:
    """Which is the whole reason there are two floors."""
    files = [FileCoverage("thin.py", 4, 10), FileCoverage("thick.py", 100, 100)]
    found = coverage_gate.problems(96.0, files, 95.0, 80.0)
    assert len(found) == 1
    assert "thin.py" in found[0]


def test_everything_over_both_floors_is_no_problem() -> None:
    files = [FileCoverage("a.py", 9, 10)]
    assert coverage_gate.problems(96.0, files, 95.0, 80.0) == []


def test_a_missing_report_is_a_failure(tmp_path: Path) -> None:
    assert coverage_gate.main(["--report", str(tmp_path / "nothing.json")]) == 1


def test_a_good_report_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = a_report(tmp_path / "coverage.json", 99.0, {"a.py": (10, 10)})
    assert coverage_gate.main(["--report", str(path)]) == 0
    assert "99.00%" in capsys.readouterr().out


def test_a_bad_report_fails(tmp_path: Path) -> None:
    path = a_report(tmp_path / "coverage.json", 50.0, {"a.py": (5, 10)})
    assert coverage_gate.main(["--report", str(path)]) == 1
