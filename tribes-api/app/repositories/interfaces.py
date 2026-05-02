"""Abstract repository interfaces for the Tribes persistence layer.

Each domain slice defines its repository contract here. Concrete
implementations live in `app/repositories/es/<repository>.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .es.models.contact import (
    BatchImportResult,
    Contact,
    ContactImportInput,
)


class IContactRepository(ABC):
    """Per `02-contacts-spec.md` §3.

    `search`, `get_by_bins`, and `get_unlabeled` belong to this same
    interface but are documented (and added) in slice 08 (Read Path).
    """

    @abstractmethod
    async def import_contact(
        self,
        user_id: str,
        data: ContactImportInput,
        *,
        strict: bool = False,
    ) -> Contact:
        """Normalize, deduplicate (via identity resolution), and upsert
        a single contact. Returns the canonical Contact (may be a
        pre-existing one if the input resolved as a duplicate).

        Raises `InvalidPhoneError` in strict mode on phone parse failure.
        """

    @abstractmethod
    async def get_by_id(self, user_id: str, contact_id: str) -> Contact | None:
        """Fetch one contact owned by `user_id`; return `None` on miss
        or ownership mismatch.
        """

    @abstractmethod
    async def batch_import(
        self,
        user_id: str,
        contacts: list[ContactImportInput],
    ) -> BatchImportResult:
        """Bulk-upsert path used for the initial iOS address-book sync.

        Returns a `BatchImportResult` of created / merged / errors counts.
        """

    @abstractmethod
    async def delete(self, user_id: str, contact_id: str) -> None:
        """Hard-delete the contact; the assignment cascade is owned by
        slice 06 and the service layer."""

    @abstractmethod
    async def count_for_owner(self, user_id: str) -> int:
        """Return the number of contacts owned by `user_id`."""


__all__ = ["IContactRepository"]
