"""A package that re-exports says what it re-exports, and both lists agree."""

from __future__ import annotations

from pathlib import Path

from culmbin.tools import check_exports, sources


def test_the_check_passes_on_this_tree() -> None:
    assert check_exports.problems() == []


def test_a_module_with_no_all_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text('"""A module that exports nothing on purpose."""\n\nx = 1\n')
    assert check_exports._check(sources.read(path)) == []


def test_a_name_imported_and_not_listed_is_found(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A package that forgot to list one of its names."""\n\n'
        "from culmbin.units.mass import dry_matter, wet_weight\n\n"
        '__all__ = ["dry_matter"]\n'
    )
    found = check_exports._check(sources.read(path))
    assert any("wet_weight is imported and not in __all__" in item for item in found)


def test_a_name_listed_and_not_imported_is_found(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A package that lists a name it does not import."""\n\n'
        "from culmbin.units.mass import dry_matter\n\n"
        '__all__ = ["dry_matter", "gone"]\n'
    )
    found = check_exports._check(sources.read(path))
    assert any("gone is in __all__ and not imported" in item for item in found)


def test_the_order_is_the_one_the_formatter_enforces() -> None:
    """Sorting it any other way means the check and ruff undo each other forever."""
    names = ["dry_matter", "MOISTURE_CEILING", "Leg", "at_moisture"]
    assert sorted(names, key=check_exports.sort_key) == [
        "MOISTURE_CEILING",
        "Leg",
        "at_moisture",
        "dry_matter",
    ]


def test_an_unsorted_list_is_found(tmp_path: Path) -> None:
    """Otherwise the diff on adding one name is unreadable."""
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A package whose list is in the order somebody typed it."""\n\n'
        "from culmbin.units.mass import dry_matter, wet_weight\n\n"
        '__all__ = ["wet_weight", "dry_matter"]\n'
    )
    found = check_exports._check(sources.read(path))
    assert any("not sorted" in item for item in found)


def test_the_units_package_lists_what_it_imports() -> None:
    module = sources.read(sources.package_root() / "units" / "__init__.py")
    listed = check_exports._all_names(module)
    assert listed is not None
    assert set(listed) == check_exports._imported(module)


def test_an_import_from_outside_the_package_is_not_a_re_export(tmp_path: Path) -> None:
    path = tmp_path / "thing.py"
    path.write_text(
        '"""A package that imports the standard library."""\n\n'
        "import datetime as dt\nfrom culmbin.units.mass import dry_matter\n\n"
        '__all__ = ["dry_matter"]\n'
    )
    assert check_exports._check(sources.read(path)) == []
