"""Unit tests for the Pydantic v2 contact-domain models.

Validates required fields, optional defaults, enum/literal constraints,
and default factories per `02-contacts-spec.md` §2 (post-Story-B).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.repositories.es.models.contact import (
    BatchImportResult,
    Contact,
    ContactImportInput,
    EmailAddress,
    PhoneNumber,
    ResolutionStatus,
)

pytestmark = pytest.mark.unit


# --- PhoneNumber ---------------------------------------------------------------------


class TestPhoneNumber:
    def test_value_hash_is_required(self) -> None:
        with pytest.raises(ValidationError):
            PhoneNumber()  # type: ignore[call-arg]

    def test_e164_raw_country_code_optional(self) -> None:
        phone = PhoneNumber(value_hash="abc")
        assert phone.e164 is None
        assert phone.raw is None
        assert phone.country_code is None

    def test_default_label_is_mobile(self) -> None:
        assert PhoneNumber(value_hash="abc").label == "mobile"

    def test_label_must_be_one_of_allowed(self) -> None:
        with pytest.raises(ValidationError):
            PhoneNumber(value_hash="abc", label="primary")  # type: ignore[arg-type]

    def test_all_label_values_accepted(self) -> None:
        for lab in ("mobile", "home", "work", "other"):
            assert PhoneNumber(value_hash="x", label=lab).label == lab  # type: ignore[arg-type]

    def test_post_story_b_fields_present(self) -> None:
        # Spec post-Story-B: PhoneNumber carries `raw` and `country_code`
        # alongside e164.
        phone = PhoneNumber(
            e164="+15551234567",
            raw="(555) 123-4567",
            country_code="US",
            value_hash="abc",
        )
        assert phone.raw == "(555) 123-4567"
        assert phone.country_code == "US"


# --- EmailAddress --------------------------------------------------------------------


class TestEmailAddress:
    def test_address_and_value_hash_required(self) -> None:
        with pytest.raises(ValidationError):
            EmailAddress(address="alice@example.com")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            EmailAddress(value_hash="abc")  # type: ignore[call-arg]

    def test_default_label_is_home(self) -> None:
        email = EmailAddress(address="a@b.com", value_hash="h")
        assert email.label == "home"

    def test_label_must_be_one_of_allowed(self) -> None:
        with pytest.raises(ValidationError):
            EmailAddress(
                address="a@b.com", value_hash="h", label="primary",  # type: ignore[arg-type]
            )

    def test_all_label_values_accepted(self) -> None:
        for lab in ("home", "work", "icloud", "other"):
            email = EmailAddress(address="a@b.com", value_hash="h", label=lab)  # type: ignore[arg-type]
            assert email.label == lab


# --- ResolutionStatus ----------------------------------------------------------------


class TestResolutionStatus:
    def test_enum_values(self) -> None:
        assert ResolutionStatus.RAW == "raw"
        assert ResolutionStatus.UNIFIED == "unified"
        assert ResolutionStatus.DUPLICATE == "duplicate"

    def test_str_subclass(self) -> None:
        # str(Enum) so values can flow into ES keyword fields directly.
        assert isinstance(ResolutionStatus.RAW, str)


# --- Contact -------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestContact:
    def _minimal_kwargs(self) -> dict:
        return {
            "contact_id": "c-1",
            "owner_user_id": "u-1",
            "source": "ios_contacts",
            "display_name": "Alice Smith",
            "imported_at": _now(),
            "updated_at": _now(),
        }

    def test_minimal_construction(self) -> None:
        c = Contact(**self._minimal_kwargs())
        assert c.contact_id == "c-1"
        assert c.given_name is None
        assert c.family_name is None
        assert c.nickname is None
        assert c.canonical_id is None

    def test_default_country_us(self) -> None:
        assert Contact(**self._minimal_kwargs()).country == "US"

    def test_default_resolution_status_raw(self) -> None:
        assert Contact(**self._minimal_kwargs()).resolution_status == ResolutionStatus.RAW

    def test_phone_email_default_to_empty_lists(self) -> None:
        c = Contact(**self._minimal_kwargs())
        assert c.phone_numbers == []
        assert c.email_addresses == []

    def test_phone_email_default_factories_independent(self) -> None:
        # Default-factory list must not be aliased across instances.
        a = Contact(**self._minimal_kwargs())
        b = Contact(**self._minimal_kwargs())
        a.phone_numbers.append(PhoneNumber(value_hash="x"))
        assert b.phone_numbers == []

    def test_source_must_be_known(self) -> None:
        kwargs = self._minimal_kwargs()
        kwargs["source"] = "google_import"
        with pytest.raises(ValidationError):
            Contact(**kwargs)

    def test_required_fields_enforced(self) -> None:
        # Drop one required field at a time.
        for key in ("contact_id", "owner_user_id", "source", "display_name",
                    "imported_at", "updated_at"):
            kwargs = self._minimal_kwargs()
            kwargs.pop(key)
            with pytest.raises(ValidationError):
                Contact(**kwargs)

    def test_nested_phone_numbers_round_trip(self) -> None:
        kwargs = self._minimal_kwargs()
        kwargs["phone_numbers"] = [
            PhoneNumber(e164="+15551234567", raw="(555) 123-4567",
                        country_code="US", value_hash="abc"),
        ]
        c = Contact(**kwargs)
        assert c.phone_numbers[0].e164 == "+15551234567"
        assert c.phone_numbers[0].country_code == "US"


# --- ContactImportInput --------------------------------------------------------------


class TestContactImportInput:
    def test_default_source_is_ios_contacts(self) -> None:
        ci = ContactImportInput(import_idempotency_token="t-1")
        assert ci.source == "ios_contacts"

    def test_token_required(self) -> None:
        with pytest.raises(ValidationError):
            ContactImportInput()  # type: ignore[call-arg]

    def test_phone_email_default_to_empty_lists(self) -> None:
        ci = ContactImportInput(import_idempotency_token="t")
        assert ci.phone_numbers == []
        assert ci.email_addresses == []

    def test_source_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            ContactImportInput(
                import_idempotency_token="t",
                source="bad",  # type: ignore[arg-type]
            )

    def test_accepts_arbitrary_phone_dicts(self) -> None:
        # Pre-normalization: callers hand us raw dicts.
        ci = ContactImportInput(
            import_idempotency_token="t",
            phone_numbers=[{"number": "(555) 123-4567"}],
            email_addresses=[{"address": "a@b.com"}],
        )
        assert ci.phone_numbers[0]["number"] == "(555) 123-4567"
        assert ci.email_addresses[0]["address"] == "a@b.com"


# --- BatchImportResult ---------------------------------------------------------------


class TestBatchImportResult:
    def test_all_three_counts_required(self) -> None:
        res = BatchImportResult(created=10, merged=2, errors=0)
        assert res.created == 10
        assert res.merged == 2
        assert res.errors == 0

    def test_missing_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BatchImportResult(created=1, merged=2)  # type: ignore[call-arg]
