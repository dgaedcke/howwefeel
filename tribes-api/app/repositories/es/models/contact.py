"""Contact domain models for the Tribes persistence layer.

Per `02-contacts-spec.md` §2 (post-Story-B field set: `value_hash` on both
nested handle types, `raw` and `country_code` on `PhoneNumber`).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PhoneNumber(BaseModel):
    """One nested phone entry on a `Contact`.

    `e164` is null when E.164 normalization fails; in that case `raw`
    preserves the original input verbatim per spec §4.
    """

    e164: str | None = None
    raw: str | None = None
    country_code: str | None = None
    label: Literal["mobile", "home", "work", "other"] = "mobile"
    value_hash: str


class EmailAddress(BaseModel):
    """One nested email entry on a `Contact`.

    `address` is the lowercased canonical form. `value_hash` is the
    SHA-256 of `address` and serves as the merge dedup key (spec §6).
    """

    address: str
    label: Literal["home", "work", "icloud", "other"] = "home"
    value_hash: str


class ResolutionStatus(str, Enum):
    RAW = "raw"
    UNIFIED = "unified"
    DUPLICATE = "duplicate"


class Contact(BaseModel):
    """A resolved contact entity in `tribes_contacts` (spec §1)."""

    contact_id: str
    owner_user_id: str
    source: Literal["ios_contacts", "manual"]
    display_name: str
    given_name: str | None = None
    family_name: str | None = None
    nickname: str | None = None
    phone_numbers: list[PhoneNumber] = Field(default_factory=list)
    email_addresses: list[EmailAddress] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    country: str = "US"
    resolution_status: ResolutionStatus = ResolutionStatus.RAW
    canonical_id: str | None = None
    imported_at: datetime
    updated_at: datetime


class ContactImportInput(BaseModel):
    """The shape the iOS Contacts framework hands us; pre-normalization."""

    given_name: str | None = None
    family_name: str | None = None
    nickname: str | None = None
    phone_numbers: list[dict] = Field(default_factory=list)
    email_addresses: list[dict] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    import_idempotency_token: str
    source: Literal["ios_contacts", "manual"] = "ios_contacts"


class BatchImportResult(BaseModel):
    """Counts returned by `IContactRepository.batch_import` (spec §7)."""

    created: int
    merged: int
    errors: int


__all__ = [
    "PhoneNumber",
    "EmailAddress",
    "ResolutionStatus",
    "Contact",
    "ContactImportInput",
    "BatchImportResult",
]
