"""Mapping-migration smoke tests.

Covers:

* T-MAP-102 — Adding a new field to an existing index via the
  mapping-update path succeeds; the new field is visible in the
  refreshed mapping.
* T-MAP-103 — Attempting to change an existing field's type raises
  `MappingMigrationConflictError`. ES must not silently corrupt the
  index, and the typed exception must surface to the caller.
"""

from __future__ import annotations

import pytest
from elasticsearch import AsyncElasticsearch

from app.repositories.es.config import ESConfig
from app.repositories.es.exceptions import MappingMigrationConflictError
from app.repositories.es.indices.manager import update_index_mapping

pytestmark = pytest.mark.integration


async def test_t_map_102_add_new_field_succeeds(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    index_name = clean_indices.pending_jobs_index

    await update_index_mapping(
        es_client,
        index_name,
        {"new_telemetry_tag": {"type": "keyword"}},
    )

    mapping = await es_client.indices.get_mapping(index=index_name)
    body = mapping.body if hasattr(mapping, "body") else mapping
    properties = body[index_name]["mappings"]["properties"]
    assert properties["new_telemetry_tag"]["type"] == "keyword"


async def test_t_map_103_incompatible_type_change_raises(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    """`status` is `keyword` — try to redeclare it as `integer`."""
    index_name = clean_indices.pending_jobs_index

    with pytest.raises(MappingMigrationConflictError):
        await update_index_mapping(
            es_client,
            index_name,
            {"status": {"type": "integer"}},
        )
