"""Unit tests for `app.repositories.interfaces`.

Validates the abstract surface of `IContactRepository` per
`02-contacts-spec.md` §3.
"""

from __future__ import annotations

import inspect

import pytest

from app.repositories.interfaces import IContactRepository

pytestmark = pytest.mark.unit


REQUIRED_METHODS = {
    "import_contact",
    "get_by_id",
    "batch_import",
    "delete",
    "count_for_owner",
}


def test_is_abstract_class() -> None:
    assert inspect.isabstract(IContactRepository)


def test_cannot_instantiate_directly() -> None:
    with pytest.raises(TypeError):
        IContactRepository()  # type: ignore[abstract]


def test_required_methods_present_and_abstract() -> None:
    abstract = IContactRepository.__abstractmethods__
    assert REQUIRED_METHODS.issubset(abstract)


def test_required_methods_are_async() -> None:
    for name in REQUIRED_METHODS:
        method = getattr(IContactRepository, name)
        assert inspect.iscoroutinefunction(method), f"{name} must be async"


def test_no_search_methods_yet() -> None:
    # Spec §3 explicitly defers `search`, `get_by_bins`, `get_unlabeled`
    # to slice 08. They MUST NOT appear on the slice-02 ABC.
    abstract = IContactRepository.__abstractmethods__
    for name in ("search", "get_by_bins", "get_unlabeled"):
        assert name not in abstract


def test_concrete_subclass_must_implement_all() -> None:
    class Stub(IContactRepository):
        pass

    with pytest.raises(TypeError):
        Stub()  # type: ignore[abstract]
