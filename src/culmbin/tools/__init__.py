"""The self-checks and the document generators.

Every check in here reads the source tree with `ast` rather than importing
it. That is deliberate: a module that fails to import is exactly the module
worth reporting on, and a check that imports the package cannot report on
it because it never gets that far.

Each check is a module with a `problems()` that gives back a list of
sentences, and a `main()` that prints them and exits 1 if there are any. CI
runs every one of them, and there is a check that says so.
"""

from __future__ import annotations
