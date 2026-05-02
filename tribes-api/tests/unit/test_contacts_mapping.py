"""Unit tests for the `tribes_contacts` mapping definition.

Locks the post-Story-B mapping shape (per `02-contacts-spec.md` §1) and
verifies registration with the indices manager. No ES required.
"""

from __future__ import annotations

import pytest

from app.repositories.es.indices.contacts import CONTACTS_MAPPING
from app.repositories.es.indices.manager import registered_indices

pytestmark = pytest.mark.unit


# --- Mapping shape -------------------------------------------------------------------


def test_mapping_top_level_keys() -> None:
    assert set(CONTACTS_MAPPING.keys()) == {"mappings", "settings"}


def test_mappings_dynamic_strict() -> None:
    assert CONTACTS_MAPPING["mappings"]["dynamic"] == "strict"


def test_settings_2_shards_1_replica() -> None:
    settings = CONTACTS_MAPPING["settings"]
    assert settings["number_of_shards"] == 2
    assert settings["number_of_replicas"] == 1


def test_tribes_name_analyzer_present() -> None:
    analyzer = CONTACTS_MAPPING["settings"]["analysis"]["analyzer"]["tribes_name"]
    assert analyzer["type"] == "custom"
    assert analyzer["tokenizer"] == "standard"
    assert analyzer["filter"] == ["lowercase", "asciifolding", "tribes_edge_ngram"]


def test_edge_ngram_filter_present() -> None:
    filt = CONTACTS_MAPPING["settings"]["analysis"]["filter"]["tribes_edge_ngram"]
    assert filt == {"type": "edge_ngram", "min_gram": 2, "max_gram": 15}


# --- Identity fields -----------------------------------------------------------------


def test_identity_fields_keyword() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]
    for field in ("contact_id", "owner_user_id", "source"):
        assert props[field] == {"type": "keyword"}


def test_imported_at_and_updated_at_dates() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]
    assert props["imported_at"] == {"type": "date"}
    assert props["updated_at"] == {"type": "date"}


# --- Name fields ---------------------------------------------------------------------


def test_display_name_text_with_keyword_subfield() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]["display_name"]
    assert props["type"] == "text"
    assert props["analyzer"] == "tribes_name"
    assert props["fields"]["keyword"] == {"type": "keyword"}


@pytest.mark.parametrize("field", ["given_name", "family_name", "nickname"])
def test_other_name_fields_text_with_analyzer(field: str) -> None:
    spec = CONTACTS_MAPPING["mappings"]["properties"][field]
    assert spec == {"type": "text", "analyzer": "tribes_name"}


# --- Phone numbers (post-Story-B: e164 + raw + country_code + value_hash + label) ----


def test_phone_numbers_nested_post_story_b() -> None:
    phones = CONTACTS_MAPPING["mappings"]["properties"]["phone_numbers"]
    assert phones["type"] == "nested"
    props = phones["properties"]
    assert set(props.keys()) == {"e164", "raw", "country_code", "label", "value_hash"}
    for f in props.values():
        assert f == {"type": "keyword"}


# --- Email addresses (post-Story-B: address + label + value_hash) --------------------


def test_email_addresses_nested_post_story_b() -> None:
    emails = CONTACTS_MAPPING["mappings"]["properties"]["email_addresses"]
    assert emails["type"] == "nested"
    props = emails["properties"]
    assert set(props.keys()) == {"address", "label", "value_hash"}
    for f in props.values():
        assert f == {"type": "keyword"}


# --- Location ------------------------------------------------------------------------


def test_country_default_us() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]
    assert props["country"]["null_value"] == "US"
    assert props["country"]["type"] == "keyword"
    assert props["city"] == {"type": "keyword"}
    assert props["state"] == {"type": "keyword"}


# --- Identity resolution -------------------------------------------------------------


def test_identity_resolution_fields() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]
    assert props["resolution_status"] == {"type": "keyword"}
    assert props["canonical_id"] == {"type": "keyword"}
    assert props["blocking_keys"] == {"type": "keyword"}


def test_merge_audit_nested_with_required_subfields() -> None:
    audit = CONTACTS_MAPPING["mappings"]["properties"]["merge_audit"]
    assert audit["type"] == "nested"
    sub = audit["properties"]
    assert sub["import_idempotency_token"] == {"type": "keyword"}
    assert sub["merged_at"] == {"type": "date"}
    assert sub["similarity_score"] == {"type": "float"}
    # `incoming_snapshot` is intentionally non-indexed (object, enabled=false).
    assert sub["incoming_snapshot"] == {"type": "object", "enabled": False}
    assert sub["fields_overwritten"] == {"type": "keyword"}
    assert sub["merged_by"] == {"type": "keyword"}


# --- Search convenience --------------------------------------------------------------


def test_search_text_field() -> None:
    props = CONTACTS_MAPPING["mappings"]["properties"]
    assert props["search_text"] == {"type": "text", "analyzer": "tribes_name"}


# --- V1 invariant --------------------------------------------------------------------


def _walk_types(node: dict) -> list[str]:
    seen: list[str] = []
    for value in node.values():
        if not isinstance(value, dict):
            continue
        if "type" in value and isinstance(value["type"], str):
            seen.append(value["type"])
        for sub_key in ("properties", "fields"):
            sub = value.get(sub_key)
            if isinstance(sub, dict):
                seen.extend(_walk_types(sub))
    return seen


def test_no_dense_vector_anywhere() -> None:
    types = _walk_types(CONTACTS_MAPPING["mappings"]["properties"])
    assert "dense_vector" not in types


# --- Manager wiring ------------------------------------------------------------------


class _StubConfig:
    """Minimal stand-in for ESConfig so we can assert wiring without
    booting a real container or settings env."""

    contacts_index = "tribes_contacts"
    pending_jobs_index = "tribes_pending_jobs"


def test_contacts_mapping_registered() -> None:
    indices = dict(registered_indices(_StubConfig()))  # type: ignore[arg-type]
    assert "tribes_contacts" in indices
    assert indices["tribes_contacts"] is CONTACTS_MAPPING
