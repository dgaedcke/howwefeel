"""V1 vector-field absence regression guard.

T-MAP-V1-VEC-NONE — `00-shared-context.md` declares "V1 Vector Field
Inventory: NONE". This test walks every `tribes_*` mapping known to the
Foundation registry and asserts no leaf has type `dense_vector`. A
contributor introducing vector search must explicitly amend this test
plus the spec — silent introduction is impossible.
"""

from __future__ import annotations

from typing import Iterable

import pytest
from elasticsearch import AsyncElasticsearch

from app.repositories.es.config import ESConfig
from app.repositories.es.indices.manager import registered_indices

pytestmark = [pytest.mark.integration, pytest.mark.regression_guard]


async def test_t_map_v1_vec_none_no_dense_vector_anywhere(
    clean_indices: ESConfig,
    es_client: AsyncElasticsearch,
) -> None:
    for index_name, _ in registered_indices(clean_indices):
        mapping = await es_client.indices.get_mapping(index=index_name)
        body = mapping.body if hasattr(mapping, "body") else mapping
        properties = body[index_name]["mappings"].get("properties", {})
        offenders = list(_dense_vector_paths(properties))
        assert not offenders, (
            f"V1 boundary breached: {index_name} has dense_vector field(s) "
            f"at {offenders}. V1 contains NO dense_vector fields; "
            f"see 00-shared-context.md `V1 Vector Field Inventory: NONE`."
        )


def _dense_vector_paths(node: dict, prefix: str = "") -> Iterable[str]:
    """Yield dotted paths to any leaf where `type == "dense_vector"`."""
    for name, value in node.items():
        if not isinstance(value, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        if value.get("type") == "dense_vector":
            yield path
        nested_props = value.get("properties")
        if isinstance(nested_props, dict):
            yield from _dense_vector_paths(nested_props, path)
        nested_fields = value.get("fields")
        if isinstance(nested_fields, dict):
            yield from _dense_vector_paths(nested_fields, path)
