"""`tribes_contacts` index mapping. Owned by slice 02 (Contacts).

Per `02-contacts-spec.md` §1 (post-Story-B field set: `value_hash` on
both nested handle types, `raw` and `country_code` on `phone_numbers`).
"""

from __future__ import annotations

from typing import Any

CONTACTS_MAPPING: dict[str, Any] = {
    "mappings": {
        "dynamic": "strict",
        "properties": {
            # --- Identity ---
            "contact_id":       {"type": "keyword"},
            "owner_user_id":    {"type": "keyword"},
            "source":           {"type": "keyword"},
            "imported_at":      {"type": "date"},
            "updated_at":       {"type": "date"},

            # --- Names (EAV: sparse fields, all optional) ---
            "display_name":     {"type": "text",
                                 "analyzer": "tribes_name",
                                 "fields": {"keyword": {"type": "keyword"}}},
            "given_name":       {"type": "text", "analyzer": "tribes_name"},
            "family_name":      {"type": "text", "analyzer": "tribes_name"},
            "nickname":         {"type": "text", "analyzer": "tribes_name"},

            # --- Contact Handles (multi-value, normalized) ---
            "phone_numbers":    {
                "type": "nested",
                "properties": {
                    "e164":         {"type": "keyword"},
                    "raw":          {"type": "keyword"},
                    "country_code": {"type": "keyword"},
                    "label":        {"type": "keyword"},
                    "value_hash":   {"type": "keyword"},
                },
            },
            "email_addresses":  {
                "type": "nested",
                "properties": {
                    "address":      {"type": "keyword"},
                    "label":        {"type": "keyword"},
                    "value_hash":   {"type": "keyword"},
                },
            },

            # --- Location (city-level only, per PRD NFR) ---
            "city":             {"type": "keyword"},
            "state":            {"type": "keyword"},
            "country":          {"type": "keyword", "null_value": "US"},

            # --- Identity Resolution ---
            "resolution_status": {"type": "keyword"},
            "canonical_id":     {"type": "keyword"},
            "blocking_keys":    {"type": "keyword"},
            "merge_audit":      {
                "type": "nested",
                "properties": {
                    "import_idempotency_token": {"type": "keyword"},
                    "merged_at":                {"type": "date"},
                    "similarity_score":         {"type": "float"},
                    "incoming_snapshot":        {"type": "object", "enabled": False},
                    "fields_overwritten":       {"type": "keyword"},
                    "merged_by":                {"type": "keyword"},
                },
            },

            # --- Search convenience ---
            "search_text":      {"type": "text",
                                 "analyzer": "tribes_name"},
        },
    },
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "tribes_name": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "tribes_edge_ngram"],
                },
            },
            "filter": {
                "tribes_edge_ngram": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 15,
                },
            },
        },
    },
}


__all__ = ["CONTACTS_MAPPING"]
