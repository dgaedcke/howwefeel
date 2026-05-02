# Slice 1 — Foundation: Spec

> **Read `00-shared-context.md` FIRST.** This slice assumes the V1 decisions, vector inventory, refresh contract, perf baselines, naming conventions, and glossary are already in context. Do not re-state them here.

## Related slices

This is the prerequisite slice for everything else. The mappings, client, config, error contract, and lifecycle defined here are referenced by every later slice (02–08). It depends on no other slice.

---

## 1. Goals & Non-Goals

### Goals
- Hide all Elasticsearch DSL behind strongly-typed Python interfaces.
- Callers (service layer) never import `elasticsearch` directly.
- All query inputs are Pydantic v2 models; all outputs are domain types.
- Index mappings, field names, boost values, and query shapes are internal details.
- Full async throughout (`AsyncElasticsearch`).

### Non-Goals (V1)
- Community `certaintyWeight` aggregation (V2).
- Agentic bin rule evaluation (V2).
- Vector / semantic similarity search (V2).
- Multi-hop graph traversal (ArangoDB / V2).
- Offline sync / conflict resolution.

---

## 2. Module Layout

```
tribes-api/app/repositories/
├── __init__.py
├── es/
│   ├── __init__.py
│   ├── client.py              # Connection factory, singleton
│   ├── config.py              # Index names, ES settings from env
│   ├── exceptions.py          # Domain exceptions (no ES types leak out)
│   ├── indices/
│   │   ├── contacts.py        # Index mapping definition
│   │   ├── bins.py
│   │   ├── assignments.py
│   │   └── tribes.py
│   ├── models/
│   │   ├── contact.py         # Pydantic domain models
│   │   ├── bin.py
│   │   ├── assignment.py
│   │   └── tribe.py
│   ├── repositories/
│   │   ├── base.py            # BaseRepository abstract class
│   │   ├── contact_repo.py
│   │   ├── bin_repo.py
│   │   ├── assignment_repo.py
│   │   └── tribe_repo.py
│   └── identity/
│       ├── resolver.py        # Identity resolution logic
│       └── blocking.py        # Blocking key generation
└── interfaces.py              # Abstract protocols (service layer imports these only)
```

---

## 3. Index Designs — Top-Level Overview

V1 ships four functional indices plus one operational index:

| Index | Purpose | `_id` scheme | Shards (V1) |
|---|---|---|---|
| `tribes_contacts` | Resolved contact entities | UUID4 | 2 |
| `tribes_bins` | User-owned labels | `sha256("{owner}#{slug(name)}")[:32]` | 3 |
| `tribes_assignments` | `(owner, contact, bin)` triples | `f"{owner}#{contact}#{bin}"` truncated/hashed | 3 |
| `tribes_tribes` | Coordination units | UUID4 | 1 |
| `tribes_pending_jobs` | Cross-index cascade retry | `sha256(op_type + primary_id)` | (operational) |

The detailed mapping for each functional index is owned by the slice that owns the repository: bins live in slice 03, contacts in slice 02, assignments in slice 04, tribes in slice 05. Slice 01 owns the **shared analyzer config**, the `tribes_pending_jobs` mapping, and the index lifecycle / bootstrap path.

---

## 4. `tribes_pending_jobs` Mapping (Operational)

Used for cross-index cascade retry. Detailed write protocol and lifecycle live in slice 06 (Cascade); this slice owns only the index existence and mapping.

```json
{
  "mappings": {
    "properties": {
      "op_type":         { "type": "keyword" },
      "primary_id":      { "type": "keyword" },
      "target_index":    { "type": "keyword" },
      "query_dsl":       { "type": "object", "enabled": false },
      "created_at":      { "type": "date" },
      "retry_count":     { "type": "integer" },
      "last_attempted":  { "type": "date" },
      "next_attempt_at": { "type": "date" },
      "status":          { "type": "keyword" },
      "error_log":       { "type": "text" }
    }
  }
}
```

- The document `_id` is `sha256(op_type + primary_id)`; this hash IS the job's identifier. No separate `job_id` field is stored — re-submitting the same logical cascade upserts the same `_id`.
- The opaque blob holding the cascade query is named `query_dsl` (single canonical name; tests assert the same field).
- Status enum: `"pending"`, `"succeeded"`, `"failed_permanent"`. `next_attempt_at` carries the next retry time (sweep filters on `status="pending" AND next_attempt_at <= now`); see slice 06 for the write/sweep protocol.

---

## 5. Broad Analyzer Config

Custom analyzer used by `tribes_contacts` text fields:

```python
"settings": {
  "analysis": {
    "analyzer": {
      "tribes_name": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "asciifolding", "tribes_edge_ngram"]
      }
    },
    "filter": {
      "tribes_edge_ngram": {
        "type": "edge_ngram",
        "min_gram": 2,
        "max_gram": 15
      }
    }
  }
}
```

The canonical name for this analyzer is `tribes_name` (spec mapping above and tests T-MAP-006, T-MAP-010 agree).

The `standard` analyzer used on `tribes_bins.name_search` and `tribes_bins.normalized_name.text` is built-in and requires no configuration.

---

## 6. Top-Level Configuration

### Client

```python
# repositories/es/client.py
from elasticsearch import AsyncElasticsearch
from functools import lru_cache
from .config import ESConfig


@lru_cache(maxsize=1)
def get_es_client() -> AsyncElasticsearch:
    config = ESConfig()
    return AsyncElasticsearch(
        hosts=[config.es_url],
        api_key=config.es_api_key,                  # GCP Secret Manager
        retry_on_timeout=True,
        max_retries=3,
        request_timeout=10,
        sniff_on_start=False,                        # Cloud Elasticsearch: no sniffing
    )
```

### Config

```python
# repositories/es/config.py
from pydantic_settings import BaseSettings


class ESConfig(BaseSettings):
    es_url: str                                      # TRIBES_ES_URL
    es_api_key: str                                  # TRIBES_ES_API_KEY
    es_index_prefix: str = "tribes"                  # TRIBES_ES_INDEX_PREFIX

    @property
    def contacts_index(self) -> str: return f"{self.es_index_prefix}_contacts"

    @property
    def bins_index(self) -> str: return f"{self.es_index_prefix}_bins"

    @property
    def assignments_index(self) -> str: return f"{self.es_index_prefix}_assignments"

    @property
    def tribes_index(self) -> str: return f"{self.es_index_prefix}_tribes"

    class Config:
        env_prefix = "TRIBES_"
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRIBES_ES_URL` | Yes | — | Elasticsearch cluster URL |
| `TRIBES_ES_API_KEY` | Yes | — | API key (from GCP Secret Manager) |
| `TRIBES_ES_INDEX_PREFIX` | No | `tribes` | Index name prefix (use `test_<uuid>` in tests) |
| `TRIBES_ID_MERGE_THRESHOLD` | No | `0.85` | Minimum score to merge as duplicate (used in slice 02) |

---

## 7. Error Handling Contract

All ES exceptions are caught inside the repository layer and re-raised as domain exceptions. Service layer catches only domain exceptions.

```python
# repositories/es/exceptions.py

class TribesRepositoryError(Exception):
    """Base for all repository errors."""

class ContactNotFoundError(TribesRepositoryError):
    def __init__(self, contact_id: str):
        super().__init__(f"Contact not found: {contact_id}")

class ContactOwnershipError(TribesRepositoryError):
    """Contact exists but is not owned by requesting user."""

class BinNotFoundError(TribesRepositoryError): ...
class BinOwnershipError(TribesRepositoryError): ...
class BinNameConflictError(TribesRepositoryError):
    """Bin with same name already exists for this user."""

class AssignmentNotFoundError(TribesRepositoryError): ...
class TribeNotFoundError(TribesRepositoryError): ...
class TribeQueryInvalidError(TribesRepositoryError):
    """Dynamic tribe query references bin_ids not owned by user."""

class ESUnavailableError(TribesRepositoryError):
    """Elasticsearch cluster unreachable. Triggers 503 at API layer."""

class ESIndexError(TribesRepositoryError):
    """Document indexing failed after retries."""
```

Exception mapping table (cross-cutting; full per-method failure modes live in slice 08):

| ES Exception | Domain Exception | HTTP Status |
|---|---|---|
| `NotFoundError` | `*NotFoundError` | 404 |
| `ConflictError` | `BinNameConflictError` | 409 |
| `ConnectionError` | `ESUnavailableError` | 503 |
| `RequestError` | `ESIndexError` | 500 |
| `AuthenticationException` | `ESUnavailableError` | 503 |

Slice 02–06 introduce additional typed exceptions that subclass the base above (e.g., `MergeIntegrityError`, `MergeConflictError`, `BinWriteVerificationError`, `StaleCursorError`, `MappingMigrationConflictError`, `InvalidPhoneError`, `InvalidBinNameError`, `InvalidTribeShapeError`, `EsTimeoutError`, `EsServerError`, `EsMappingConflictError`, `VersionConflictError`, `EsScriptError`). Foundation epic must export these from a single canonical module and register the `ConflictError` → `VersionConflictError` mapping for optimistic-lock failures.

---

## 8. Index Lifecycle Management

```python
# repositories/es/indices/manager.py
# Called at FastAPI lifespan startup

async def ensure_indices(client: AsyncElasticsearch, config: ESConfig) -> None:
    """
    Creates indices if missing. Does NOT update mappings on existing indices
    (use migrations for that). Safe to call on every startup.
    """
    for index_name, mapping in [
        (config.contacts_index, CONTACTS_MAPPING),
        (config.bins_index, BINS_MAPPING),
        (config.assignments_index, ASSIGNMENTS_MAPPING),
        (config.tribes_index, TRIBES_MAPPING),
        (config.pending_jobs_index, PENDING_JOBS_MAPPING),  # added in Foundation epic
    ]:
        exists = await client.indices.exists(index=index_name)
        if not exists:
            await client.indices.create(index=index_name, body=mapping)
```

Bootstrap is idempotent — calling `ensure_indices` twice is a no-op (T-MAP-011, T-MAP-101). Mapping changes require a separate migration path (T-MAP-102, T-MAP-103) which raises `MappingMigrationConflictError` on incompatible field-type changes.

---

## 9. FastAPI Dependency Injection

```python
# app/core/dependencies.py
from repositories.interfaces import (
    IContactRepository, IBinRepository,
    IAssignmentRepository, ITribeRepository
)
from repositories.es.repositories.contact_repo import ESContactRepository
from repositories.es.repositories.bin_repo import ESBinRepository
from repositories.es.repositories.assignment_repo import ESAssignmentRepository
from repositories.es.repositories.tribe_repo import ESTribeRepository
from repositories.es.client import get_es_client
from repositories.es.config import ESConfig


def get_contact_repo() -> IContactRepository:
    return ESContactRepository(client=get_es_client(), config=ESConfig())

def get_bin_repo() -> IBinRepository:
    return ESBinRepository(client=get_es_client(), config=ESConfig())

def get_assignment_repo() -> IAssignmentRepository:
    return ESAssignmentRepository(client=get_es_client(), config=ESConfig())

def get_tribe_repo() -> ITribeRepository:
    return ESTribeRepository(client=get_es_client(), config=ESConfig())


# Usage in route handler:
@router.post("/contacts/import")
async def import_contact(
    data: ContactImportInput,
    repo: IContactRepository = Depends(get_contact_repo),
    current_user: User = Depends(get_current_user),
) -> ContactResponse:
    contact = await repo.import_contact(current_user.uid, data)
    return ContactResponse.from_domain(contact)
```

`ensure_indices` is wired into the FastAPI `lifespan` so cold-start creates indices before any request handler runs. Shutdown closes the ES client cleanly.

---

## 10. Module Boundary Rule

Service layer imports ONLY from `repositories.interfaces` and `repositories.es.models.*`. Never from `elasticsearch`. The Foundation epic enforces this with an import-lint rule (no `from elasticsearch` in `app/services/`).

---

## 11. Stories (Reference)

Spec §13 enumerates the implementation-story breakdown. Stories that map into this Foundation slice:

- **Story 1: ES Client & Config Foundation** — `client.py`, `config.py`, `exceptions.py`, `indices/manager.py`. Sets up the singleton client, env-driven config, error contract, and `ensure_indices` boot path.
- **Story 15: Repository Dependency Injection & FastAPI Integration** — wires `get_*_repo` into FastAPI, registers `lifespan` hooks for startup/shutdown.

Stories 2–14 belong to the per-domain slices (02–05) and the cross-cutting slices (06–08).

---

Pairs with `01-foundation-tests.md`.
