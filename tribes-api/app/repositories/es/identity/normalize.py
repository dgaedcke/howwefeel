"""Phone, email, and value-hash helpers for the identity-resolution layer.

Per `02-contacts-spec.md` §4 (phone E.164 contract) and §6 (`value_hash`
serves as the nested-array merge dedup key).

These helpers are pure: they return canonical strings (or `None` on
failure) and never raise. Strict-mode enforcement (`InvalidPhoneError`)
lives in `ContactRepository.import_contact`, not here.
"""

from __future__ import annotations

import hashlib

import phonenumbers


def normalize_phone(value: str | None, *, region: str = "US") -> str | None:
    """Parse `value` and return its E.164 form, or `None` on failure.

    Returns `None` when the input is empty/None, when `phonenumbers.parse`
    raises `NumberParseException`, or when the parsed number is not a
    fully-formed dialable number. We require the strict `IS_POSSIBLE`
    reason: `IS_POSSIBLE_LOCAL_ONLY` (e.g., `"abc-1234567"` → 7-digit
    local-only stub) is treated as a parse failure per spec §4 — those
    cases must fall through to the `phone_last7` blocking-key path.

    Callers running in strict mode are responsible for raising
    `InvalidPhoneError` on `None`.
    """
    if value is None:
        return None
    if not value.strip():
        return None
    try:
        parsed = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException:
        return None
    reason = phonenumbers.is_possible_number_with_reason(parsed)
    if reason != phonenumbers.ValidationResult.IS_POSSIBLE:
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value: str | None) -> str | None:
    """Lowercase and strip an email address; return `None` if empty."""
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def value_hash(value: str) -> str:
    """SHA-256 hex digest of `value` (UTF-8). Used as merge dedup key."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = ["normalize_phone", "normalize_email", "value_hash"]
