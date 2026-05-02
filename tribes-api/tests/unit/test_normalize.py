"""Unit tests for `app.repositories.es.identity.normalize`.

Covers spec §4 (phone E.164 normalization, parse-failure contract) and
§6 (`value_hash` deterministic SHA-256). No ES dependency.
"""

from __future__ import annotations

import hashlib

import pytest

from app.repositories.es.identity.normalize import (
    normalize_email,
    normalize_phone,
    value_hash,
)

pytestmark = pytest.mark.unit


# --- normalize_phone -----------------------------------------------------------------


class TestNormalizePhone:
    def test_us_format_to_e164(self) -> None:
        assert normalize_phone("(555) 123-4567") == "+15551234567"

    def test_already_e164_passthrough(self) -> None:
        assert normalize_phone("+15551234567") == "+15551234567"

    def test_with_extension_strips_extension(self) -> None:
        # T-CONTACT-IDRES-004: E.164 form omits the extension digits.
        assert normalize_phone("(555) 123-4567 ext 123") == "+15551234567"
        assert normalize_phone("555-123-4567 x123") == "+15551234567"

    def test_invalid_letters_only_returns_none(self) -> None:
        # T-CONTACT-IDRES-PHONE-INVALID-B
        assert normalize_phone("abc") is None

    def test_invalid_partial_letters_returns_none(self) -> None:
        # T-CONTACT-IDRES-PHONE-INVALID-A
        assert normalize_phone("abc-1234567") is None

    def test_garbage_returns_none(self) -> None:
        assert normalize_phone("not-a-phone-number-at-all") is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize_phone("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_phone("   ") is None

    def test_none_returns_none(self) -> None:
        assert normalize_phone(None) is None

    def test_international_passthrough_with_country_code(self) -> None:
        # libphonenumber recognizes leading-+ as international even when
        # the default region is US.
        assert normalize_phone("+44 20 7123 4567") == "+442071234567"

    def test_dotted_us_format(self) -> None:
        assert normalize_phone("555.123.4567") == "+15551234567"

    def test_leading_one_us(self) -> None:
        assert normalize_phone("1-555-123-4567") == "+15551234567"

    def test_too_short_returns_none(self) -> None:
        # Possible-number gate rejects single digits / runts.
        assert normalize_phone("1") is None

    def test_region_override(self) -> None:
        # GB local number when caller specifies region="GB".
        assert normalize_phone("020 7123 4567", region="GB") == "+442071234567"


# --- normalize_email -----------------------------------------------------------------


class TestNormalizeEmail:
    def test_lowercases(self) -> None:
        # T-CONTACT-IDRES-005 ("A@Example.COM" → "a@example.com").
        assert normalize_email("A@Example.COM") == "a@example.com"

    def test_trims_whitespace(self) -> None:
        assert normalize_email("  alice@example.com  ") == "alice@example.com"
        assert normalize_email("\talice@example.com\n") == "alice@example.com"

    def test_combined_trim_and_lowercase(self) -> None:
        assert normalize_email("  AlIcE@Example.com ") == "alice@example.com"

    def test_empty_returns_none(self) -> None:
        assert normalize_email("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_email("   \t\n") is None

    def test_none_returns_none(self) -> None:
        assert normalize_email(None) is None

    def test_does_not_validate_format(self) -> None:
        # The normalizer is permissive — RFC validation is the API
        # layer's job. We only canonicalize.
        assert normalize_email("not-an-email") == "not-an-email"


# --- value_hash ----------------------------------------------------------------------


class TestValueHash:
    def test_returns_hex_string(self) -> None:
        digest = value_hash("anything")
        assert isinstance(digest, str)
        # SHA-256 hex is 64 lowercase hex chars.
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic(self) -> None:
        a = value_hash("alice@example.com")
        b = value_hash("alice@example.com")
        assert a == b

    def test_distinct_inputs_distinct_hashes(self) -> None:
        a = value_hash("alice@example.com")
        b = value_hash("bob@example.com")
        assert a != b

    def test_matches_hashlib_sha256(self) -> None:
        expected = hashlib.sha256(b"+15551234567").hexdigest()
        assert value_hash("+15551234567") == expected

    def test_unicode_input(self) -> None:
        # value_hash encodes UTF-8 explicitly; ensure it doesn't crash on
        # non-ASCII payloads.
        digest = value_hash("zoë@example.com")
        assert len(digest) == 64

    def test_empty_string_hashes(self) -> None:
        # Hashing the empty string is well-defined; do NOT special-case None.
        expected = hashlib.sha256(b"").hexdigest()
        assert value_hash("") == expected
