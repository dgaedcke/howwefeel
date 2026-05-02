"""`tribes_pending_jobs` mapping tests.

Covers:

* T-MAP-081 — The document `_id` IS the job_id; no separate `job_id`
  field is stored. (Locked by Story A / hwf-9r9.)
* T-MAP-087 — Date fields on `tribes_pending_jobs` are typed as `date`.

The spec §4 mapping (locked by Story A) names the date fields
`created_at`, `last_attempted`, and `next_attempt_at`. The original test
plan referenced `last_attempt_at`; spec authority wins, so this test
asserts against the spec's `last_attempted` field.
"""

from __future__ import annotations

import pytest
from elasticsearch import AsyncElasticsearch

from app.repositories.es.config import ESConfig

pytestmark = pytest.mark.integration


async def test_t_map_080_pending_jobs_index_exists(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    """T-MAP-080: the operational pending-jobs index exists after boot."""
    assert await es_client.indices.exists(index=clean_indices.pending_jobs_index)


async def test_t_map_081_no_separate_job_id_field(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    """T-MAP-081: `job_id` is not stored as a property; `_id` IS the job_id."""
    mapping = await es_client.indices.get_mapping(index=clean_indices.pending_jobs_index)
    properties = _properties(mapping, clean_indices.pending_jobs_index)
    assert "job_id" not in properties, (
        "tribes_pending_jobs must not declare a `job_id` field; "
        "the document _id is the job identifier (spec §4, Story A)."
    )


async def test_t_map_087_date_fields_typed_as_date(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    """T-MAP-087: created_at, last_attempted, next_attempt_at are `date`."""
    mapping = await es_client.indices.get_mapping(index=clean_indices.pending_jobs_index)
    properties = _properties(mapping, clean_indices.pending_jobs_index)
    for field in ("created_at", "last_attempted", "next_attempt_at"):
        assert properties.get(field, {}).get("type") == "date", (
            f"{field} should be type=date, got {properties.get(field)}"
        )


async def test_pending_jobs_keyword_and_object_fields(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    """Spec §4: keyword/object/integer/text shape sanity check.

    Bundles T-MAP-082..086, 088 — these are not explicitly listed in the
    Story 1 scope, but they share the same mapping fetch and lock the
    spec §4 contract that downstream slices depend on.
    """
    mapping = await es_client.indices.get_mapping(index=clean_indices.pending_jobs_index)
    properties = _properties(mapping, clean_indices.pending_jobs_index)

    for keyword_field in ("op_type", "primary_id", "target_index", "status"):
        assert properties[keyword_field]["type"] == "keyword"

    assert properties["retry_count"]["type"] == "integer"
    assert properties["error_log"]["type"] == "text"

    query_dsl = properties["query_dsl"]
    assert query_dsl.get("type") == "object"
    assert query_dsl.get("enabled") is False, (
        "query_dsl must be `enabled: false` so the cascade payload is not indexed"
    )


def _properties(mapping_response: dict, index_name: str) -> dict:
    """Pull `mappings.properties` out of a `get_mapping` response.

    Tolerates both raw-dict and ObjectApiResponse wrappers from the ES
    client.
    """
    body = mapping_response.body if hasattr(mapping_response, "body") else mapping_response
    return body[index_name]["mappings"]["properties"]
