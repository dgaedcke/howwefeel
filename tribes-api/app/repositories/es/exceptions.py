"""Domain exception hierarchy for the Tribes persistence layer.

All Elasticsearch (`elasticsearch.*`) exceptions raised by the repository layer
are caught and re-raised as one of the typed exceptions defined here. The
service layer never sees an `elasticsearch` exception; it only handles
subclasses of `TribesRepositoryError`.

Exception -> HTTP mapping is documented in `01-foundation-spec.md` §7.
"""

from __future__ import annotations


class TribesRepositoryError(Exception):
    """Base for all repository errors."""


# --- Entity-not-found / ownership ---------------------------------------------------


class ContactNotFoundError(TribesRepositoryError):
    def __init__(self, contact_id: str) -> None:
        super().__init__(f"Contact not found: {contact_id}")
        self.contact_id = contact_id


class ContactOwnershipError(TribesRepositoryError):
    """Contact exists but is not owned by the requesting user."""


class BinNotFoundError(TribesRepositoryError):
    def __init__(self, bin_id: str) -> None:
        super().__init__(f"Bin not found: {bin_id}")
        self.bin_id = bin_id


class BinOwnershipError(TribesRepositoryError):
    """Bin exists but is not owned by the requesting user."""


class BinNameConflictError(TribesRepositoryError):
    """Bin with same name already exists for this user."""


class AssignmentNotFoundError(TribesRepositoryError):
    def __init__(self, assignment_id: str) -> None:
        super().__init__(f"Assignment not found: {assignment_id}")
        self.assignment_id = assignment_id


class TribeNotFoundError(TribesRepositoryError):
    def __init__(self, tribe_id: str) -> None:
        super().__init__(f"Tribe not found: {tribe_id}")
        self.tribe_id = tribe_id


class TribeQueryInvalidError(TribesRepositoryError):
    """Dynamic tribe query references bin_ids not owned by the user."""


# --- ES infrastructure / availability -----------------------------------------------


class ESUnavailableError(TribesRepositoryError):
    """Elasticsearch cluster unreachable. Triggers 503 at the API layer."""


class ESIndexError(TribesRepositoryError):
    """Document indexing failed after retries."""


class EsTimeoutError(TribesRepositoryError):
    """ES request timed out after the configured retry budget."""


class EsServerError(TribesRepositoryError):
    """ES returned a 5xx server error not otherwise classified."""


class EsMappingConflictError(TribesRepositoryError):
    """Mapping definition rejected by ES at index-create time."""


class EsScriptError(TribesRepositoryError):
    """Painless script error during update_by_query / scripted update."""


# --- Cross-cutting / cross-slice ---------------------------------------------------
#
# These typed exceptions are referenced by slices 02-08. They are defined here so the
# Foundation epic owns the canonical export surface, even though their *raising* sites
# live in later slices.


class MergeIntegrityError(TribesRepositoryError):
    """Identity-merge invariant violated (e.g., merge audit chain broken)."""


class MergeConflictError(TribesRepositoryError):
    """Two merge candidates collided under the resolution rules."""


class BinWriteVerificationError(TribesRepositoryError):
    """Safeguard B: post-write verification on `tribes_bins` failed."""


class StaleCursorError(TribesRepositoryError):
    """A PIT/`search_after` cursor expired or is otherwise unusable."""


class MappingMigrationConflictError(TribesRepositoryError):
    """Incompatible field-type change attempted via the mapping-update path."""


class VersionConflictError(TribesRepositoryError):
    """Optimistic-lock failure (ES `version_conflict_engine_exception` -> 409)."""


class InvalidPhoneError(TribesRepositoryError):
    """Phone number failed E.164 normalization or repository-layer validation."""


class InvalidBinNameError(TribesRepositoryError):
    """Bin name is empty, too long, or otherwise rejected by repository validation."""


class InvalidTribeShapeError(TribesRepositoryError):
    """Tribe document violates static/dynamic shape invariants."""


__all__ = [
    "TribesRepositoryError",
    "ContactNotFoundError",
    "ContactOwnershipError",
    "BinNotFoundError",
    "BinOwnershipError",
    "BinNameConflictError",
    "AssignmentNotFoundError",
    "TribeNotFoundError",
    "TribeQueryInvalidError",
    "ESUnavailableError",
    "ESIndexError",
    "EsTimeoutError",
    "EsServerError",
    "EsMappingConflictError",
    "EsScriptError",
    "MergeIntegrityError",
    "MergeConflictError",
    "BinWriteVerificationError",
    "StaleCursorError",
    "MappingMigrationConflictError",
    "VersionConflictError",
    "InvalidPhoneError",
    "InvalidBinNameError",
    "InvalidTribeShapeError",
]
