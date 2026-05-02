"""Index lifecycle management for the Tribes persistence layer.

Per `01-foundation-spec.md` §8.

* `ensure_indices(client, config)` is idempotent: indices that already
  exist are skipped, mappings on existing indices are not modified.
  Mapping changes go through `update_index_mapping`.
* `update_index_mapping(client, index, properties)` applies an additive
  mapping update via `PUT <index>/_mapping`. Adding new fields succeeds;
  changing an existing field's type raises
  `MappingMigrationConflictError` rather than letting ES return a
  generic `BadRequestError`.

Domain slices (02-05) register their index mappings via
`register_index(name_attr, mapping)` so `ensure_indices` discovers them
without manager.py importing every per-domain module directly.
"""

from __future__ import annotations

from typing import Any, Iterable

from elasticsearch import AsyncElasticsearch, BadRequestError

from ..config import ESConfig
from ..exceptions import MappingMigrationConflictError
from .contacts import CONTACTS_MAPPING
from .pending_jobs import PENDING_JOBS_MAPPING

# Each entry is (config-attribute-name, mapping-dict). `ensure_indices`
# resolves the actual index name by reading the named attribute off the
# `ESConfig` instance at call time so test fixtures that override
# `es_index_prefix` still see the correct names.
_REGISTRY: list[tuple[str, dict[str, Any]]] = [
    ("pending_jobs_index", PENDING_JOBS_MAPPING),
    ("contacts_index", CONTACTS_MAPPING),
]


def register_index(config_attr: str, mapping: dict[str, Any]) -> None:
    """Register a `(config_attr, mapping)` pair with the lifecycle manager.

    Domain slices call this at import time to add their index to the
    bootstrap path. Re-registering the same `config_attr` replaces the
    previously registered mapping (last write wins).
    """
    for idx, (existing_attr, _) in enumerate(_REGISTRY):
        if existing_attr == config_attr:
            _REGISTRY[idx] = (config_attr, mapping)
            return
    _REGISTRY.append((config_attr, mapping))


def registered_indices(config: ESConfig) -> list[tuple[str, dict[str, Any]]]:
    """Return the list of `(resolved_index_name, mapping)` tuples to bootstrap."""
    return [(getattr(config, attr), mapping) for attr, mapping in _REGISTRY]


async def ensure_indices(
    client: AsyncElasticsearch,
    config: ESConfig,
) -> None:
    """Create any registered index that does not yet exist.

    Idempotent: indices that already exist are left untouched. Mapping
    changes on existing indices must go through `update_index_mapping`.
    """
    for index_name, mapping in registered_indices(config):
        exists = await client.indices.exists(index=index_name)
        if not exists:
            await client.indices.create(index=index_name, **mapping)


async def update_index_mapping(
    client: AsyncElasticsearch,
    index_name: str,
    properties: dict[str, Any],
) -> None:
    """Apply an additive mapping update to an existing index.

    `properties` is the same shape ES expects under `mappings.properties`
    (e.g., ``{"new_field": {"type": "keyword"}}``).

    Raises `MappingMigrationConflictError` when ES rejects the update
    because of an incompatible field-type change. Other ES errors
    propagate unchanged so that callers see them as ESIndexError-ish.
    """
    try:
        await client.indices.put_mapping(
            index=index_name,
            properties=properties,
        )
    except BadRequestError as exc:
        if _looks_like_mapping_conflict(exc):
            raise MappingMigrationConflictError(
                f"Incompatible mapping change on index {index_name!r}: {exc}",
            ) from exc
        raise


def _looks_like_mapping_conflict(exc: BadRequestError) -> bool:
    """Inspect a `BadRequestError` for mapping-conflict signatures.

    ES surfaces incompatible mapping changes as a 400 whose
    ``error.type`` is ``illegal_argument_exception`` and whose reason
    mentions ``mapper [<field>] cannot be changed`` (existing-field type
    swap) or ``can't merge a non object mapping`` (object/scalar
    conflict). We match conservatively so unrelated 400s propagate.
    """
    types: list[str] = []
    reasons: list[str] = []
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            err_type = err.get("type")
            if isinstance(err_type, str):
                types.append(err_type)
            reason = err.get("reason")
            if isinstance(reason, str):
                reasons.append(reason)
            for cause in _walk_root_causes(err):
                cause_type = cause.get("type")
                cause_reason = cause.get("reason")
                if isinstance(cause_type, str):
                    types.append(cause_type)
                if isinstance(cause_reason, str):
                    reasons.append(cause_reason)

    type_blob = " ".join(types).lower()
    reason_blob = " ".join(reasons).lower()
    fallback_blob = str(exc).lower()

    if "illegal_argument_exception" not in type_blob and "mapper_parsing_exception" not in type_blob:
        # Some unrelated 400 — let it propagate as-is.
        return False

    haystack = f"{reason_blob} {fallback_blob}"
    return any(
        marker in haystack
        for marker in (
            "cannot be changed",
            "can't merge",
            "cannot merge",
            "merge_failures",
            "different type",
            "mapper [",
            "conflict",
        )
    )


def _walk_root_causes(err: dict[str, Any]) -> Iterable[dict[str, Any]]:
    causes = err.get("root_cause")
    if isinstance(causes, list):
        for cause in causes:
            if isinstance(cause, dict):
                yield cause
    caused_by = err.get("caused_by")
    if isinstance(caused_by, dict):
        yield caused_by


__all__ = [
    "ensure_indices",
    "update_index_mapping",
    "register_index",
    "registered_indices",
]
