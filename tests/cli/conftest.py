"""Running the console script in a test.

`invoke` runs a command against a book on disk and gives back the result.
The book is a real file rather than an in-memory one, because half of what
the console script does is open and close it and an in-memory book would
hide every mistake in that.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from culmbin.cli.main import cli

Invoke = Callable[..., Result]


@pytest.fixture
def book_path(tmp_path: Path) -> Path:
    return tmp_path / "book.sqlite3"


@pytest.fixture
def invoke(book_path: Path) -> Invoke:
    runner = CliRunner()

    def run(*args: str, on: str = "2025-11-04") -> Result:
        return runner.invoke(cli, ["--book", str(book_path), "--on", on, *args])

    return run
