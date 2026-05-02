"""Foundation bootstrap tests.

Covers:

* T-MAP-011 — `ensure_indices` is idempotent: running boot twice does not
  error and does not alter the existing index settings/mappings.
* T-MAP-101 — Re-applying the canonical mappings on an already-booted
  cluster is a no-op (no exception, no `IllegalArgumentException`).
"""

from __future__ import annotations

import pytest
from elasticsearch import AsyncElasticsearch

from app.repositories.es.config import ESConfig
from app.repositories.es.indices.manager import ensure_indices, registered_indices

pytestmark = pytest.mark.integration


async def test_ensure_indices_creates_registered_indices(
    es_client: AsyncElasticsearch,
    es_config: ESConfig,
) -> None:
    for index_name, _ in registered_indices(es_config):
        await es_client.indices.delete(index=index_name, ignore_unavailable=True)

    await ensure_indices(es_client, es_config)

    for index_name, _ in registered_indices(es_config):
        assert await es_client.indices.exists(index=index_name)


async def test_t_map_011_ensure_indices_is_idempotent(
    es_client: AsyncElasticsearch,
    es_config: ESConfig,
) -> None:
    """T-MAP-011: running boot twice is a no-op; the mapping is unchanged."""
    for index_name, _ in registered_indices(es_config):
        await es_client.indices.delete(index=index_name, ignore_unavailable=True)

    await ensure_indices(es_client, es_config)
    pending = es_config.pending_jobs_index
    first_mapping = await es_client.indices.get_mapping(index=pending)

    await ensure_indices(es_client, es_config)
    second_mapping = await es_client.indices.get_mapping(index=pending)

    assert first_mapping == second_mapping


async def test_t_map_101_reapply_mappings_no_op(
    es_client: AsyncElasticsearch,
    es_config: ESConfig,
) -> None:
    """T-MAP-101: re-applying mappings on a booted cluster does not error."""
    await ensure_indices(es_client, es_config)
    await ensure_indices(es_client, es_config)
    await ensure_indices(es_client, es_config)
