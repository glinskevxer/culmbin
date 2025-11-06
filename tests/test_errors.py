"""The exception hierarchy is part of the interface, so it is tested.

Callers catch `CulmbinError` at the top of the console script and the
specific classes everywhere else. Both of those only work if the tree stays
the shape it is here.
"""

from __future__ import annotations

import pytest

from culmbin.errors import (
    BasisError,
    ConflictError,
    CulmbinError,
    NotFoundError,
    SegregationError,
    StateError,
    ValidationError,
)

SUBCLASSES = [
    ValidationError,
    BasisError,
    NotFoundError,
    ConflictError,
    StateError,
    SegregationError,
]


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_error_is_a_culmbin_error(cls: type[CulmbinError]) -> None:
    assert issubclass(cls, CulmbinError)


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_error_is_an_exception(cls: type[CulmbinError]) -> None:
    assert issubclass(cls, Exception)


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_catching_the_base_catches_each_one(cls: type[CulmbinError]) -> None:
    with pytest.raises(CulmbinError):
        raise cls("something the operator can read")


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_the_message_survives_the_raise(cls: type[CulmbinError]) -> None:
    err = cls("moisture 21.4 is above the 20.0 the silo takes")
    assert str(err) == "moisture 21.4 is above the 20.0 the silo takes"


def test_basis_is_not_a_validation_error() -> None:
    """A basis mistake is two right numbers, so it must not be caught as a typo."""
    assert not issubclass(BasisError, ValidationError)
    assert not issubclass(ValidationError, BasisError)


def test_segregation_is_not_a_conflict() -> None:
    """Segregation survives the movement being otherwise legal, so it stands alone."""
    assert not issubclass(SegregationError, ConflictError)


def test_the_base_is_not_bare_exception_for_callers() -> None:
    """`except Exception` in the console script would swallow bugs, so it does not."""
    assert CulmbinError.__mro__[1] is Exception


def test_the_package_carries_a_version_number() -> None:
    import culmbin

    assert culmbin.__version__.count(".") == 2
