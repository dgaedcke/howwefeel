"""Mapping for the operational `tribes_pending_jobs` index.

Per `01-foundation-spec.md` §4 (locked by Story A / hwf-9r9):

- The document `_id` is `sha256(op_type + primary_id)`; this hash IS the
  job identifier. There is no separate `job_id` field stored.
- The cascade query blob is named `query_dsl` (single canonical name;
  `payload` was renamed during Story A).
- `next_attempt_at` carries the next retry time; the sweep filters on
  `status == "pending" AND next_attempt_at <= now`.
- Status enum values: ``"pending"``, ``"succeeded"``, ``"failed_permanent"``.
"""

from __future__ import annotations

from typing import Any

PENDING_JOBS_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "op_type": {"type": "keyword"},
            "primary_id": {"type": "keyword"},
            "target_index": {"type": "keyword"},
            "query_dsl": {"type": "object", "enabled": False},
            "created_at": {"type": "date"},
            "retry_count": {"type": "integer"},
            "last_attempted": {"type": "date"},
            "next_attempt_at": {"type": "date"},
            "status": {"type": "keyword"},
            "error_log": {"type": "text"},
        },
    },
}


__all__ = ["PENDING_JOBS_MAPPING"]
