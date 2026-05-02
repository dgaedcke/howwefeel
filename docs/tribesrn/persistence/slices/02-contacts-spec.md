# Slice 2 — Contacts: Spec

> **Read `00-shared-context.md` FIRST.** This slice assumes the V1 decisions, vector inventory, refresh contract, perf baselines, naming conventions, and glossary are already in context. Do not re-state them here.

## Related slices

Depends on **slice 01 (Foundation)** for the ES client, config, base error contract, lifecycle, and `tribes_contacts` mapping bootstrap. The detailed `tribes_contacts` field-level mapping referenced below is owned by this slice (the Foundation epic creates the index from this slice's mapping).

Forward references:
- Slice 04 (Assignments) — depends on `Contact` domain model.
- Slice 05 (Tribes) — uses `Contact` for static-tribe member resolution.
- Slice 06 (Cascade) — `delete` cascades to assignments.
- Slice 08 (Read Path) — `search`, `get_by_bins`, `get_unlabeled` query patterns and cursor stability live there.

---

## 1. `tribes_contacts` Mapping

One document per **resolved contact entity** (post-deduplication). A single real-world person may have been imported by multiple users; each import creates a `tribes_assignments` record pointing to this document.

```python
CONTACTS_MAPPING = {
    "mappings": {
        "dynamic": "strict",
        "properties": {
            # --- Identity ---
            "contact_id":       {"type": "keyword"},          # UUID, system-assigned
            "owner_user_id":    {"type": "keyword"},
            "source":           {"type": "keyword"},          # "ios_contacts" | "manual"
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
                    "e164":         {"type": "keyword"},      # +1XXXXXXXXXX normalized
                    "raw":          {"type": "keyword"},      # Original input, preserved verbatim on parse failure (see §4)
                    "country_code": {"type": "keyword"},      # ISO country code (e.g., "US")
                    "label":        {"type": "keyword"},      # "mobile" | "home" | "work"
                    "value_hash":   {"type": "keyword"},      # SHA-256 for privacy matching and merge dedup key (§6)
                }
            },
            "email_addresses":  {
                "type": "nested",
                "properties": {
                    "address":      {"type": "keyword"},      # lowercased
                    "label":        {"type": "keyword"},
                    "value_hash":   {"type": "keyword"},      # SHA-256 of address; merge dedup key (§6)
                }
            },

            # --- Location (city-level only, per PRD NFR) ---
            "city":             {"type": "keyword"},
            "state":            {"type": "keyword"},
            "country":          {"type": "keyword", "null_value": "US"},

            # --- Identity Resolution ---
            "resolution_status": {"type": "keyword"},        # "raw" | "unified" | "duplicate"
            "canonical_id":     {"type": "keyword"},         # Points to the surviving doc if duplicate
            "blocking_keys":    {"type": "keyword"},         # Multi-value: computed by blocking.py
            "merge_audit":      {"type": "nested",            # Append-only — see §6 below
                                 "properties": {
                                     "import_idempotency_token": {"type": "keyword"},
                                     "merged_at":                {"type": "date"},
                                     "similarity_score":         {"type": "float"},
                                     "incoming_snapshot":        {"type": "object", "enabled": False},
                                     "fields_overwritten":       {"type": "keyword"},
                                     "merged_by":                {"type": "keyword"},
                                 }},

            # --- Search convenience ---
            "search_text":      {"type": "text",
                                 "analyzer": "tribes_name"},  # Denormalized: name + nickname
        }
    },
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
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
}
```

The `tribes_name` analyzer config is duplicated from slice 01 here for self-containment; production code uses the shared definition installed during `ensure_indices`.

---

## 2. Domain Models (Pydantic v2)

```python
# repositories/es/models/contact.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class PhoneNumber(BaseModel):
    e164: str | None = None                            # null when parse fails (see §4)
    raw: str | None = None                             # Verbatim input, populated on parse failure
    country_code: str | None = None                    # ISO country code (e.g., "US")
    label: Literal["mobile", "home", "work", "other"] = "mobile"
    value_hash: str                                    # SHA-256 over normalized number; merge dedup key (§6)


class EmailAddress(BaseModel):
    address: str                                       # lowercased
    label: Literal["home", "work", "icloud", "other"] = "home"
    value_hash: str                                    # SHA-256(address); merge dedup key (§6)


class ResolutionStatus(str, Enum):
    RAW = "raw"
    UNIFIED = "unified"
    DUPLICATE = "duplicate"


class Contact(BaseModel):
    contact_id: str
    owner_user_id: str
    source: Literal["ios_contacts", "manual"]
    display_name: str
    given_name: str | None = None
    family_name: str | None = None
    nickname: str | None = None
    phone_numbers: list[PhoneNumber] = Field(default_factory=list)
    email_addresses: list[EmailAddress] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    country: str = "US"
    resolution_status: ResolutionStatus = ResolutionStatus.RAW
    canonical_id: str | None = None
    imported_at: datetime
    updated_at: datetime


class ContactImportInput(BaseModel):
    """What the iOS Contacts framework provides; no IDs yet."""
    given_name: str | None = None
    family_name: str | None = None
    nickname: str | None = None
    phone_numbers: list[dict]                          # Raw; normalized by repo
    email_addresses: list[dict]                        # Raw; normalized by repo
    city: str | None = None
    state: str | None = None
    import_idempotency_token: str                      # UUID v4, stable per import
    source: Literal["ios_contacts", "manual"] = "ios_contacts"
```

---

## 3. ContactRepository Contract

```python
class IContactRepository(ABC):

    @abstractmethod
    async def import_contact(
        self, user_id: str, data: ContactImportInput, *, strict: bool = False
    ) -> Contact:
        """
        Normalize, deduplicate (via identity resolution), and upsert a contact.
        Returns the canonical Contact (may be pre-existing if resolved as duplicate).
        Raises InvalidPhoneError in strict mode on phone parse failure.
        """

    @abstractmethod
    async def get_by_id(self, user_id: str, contact_id: str) -> Contact | None:
        """Fetch single contact. Returns None if not found or not owned by user_id."""

    @abstractmethod
    async def batch_import(
        self, user_id: str, contacts: list[ContactImportInput]
    ) -> BatchImportResult:
        """
        Bulk upsert for initial iOS address book sync.
        Returns counts: created, merged, skipped.
        """

    @abstractmethod
    async def delete(self, user_id: str, contact_id: str) -> None:
        """Hard delete. Also deletes all assignments for this contact."""

    @abstractmethod
    async def count_for_owner(self, user_id: str) -> int:
        """Return number of contacts owned by user_id."""
```

`search`, `get_by_bins`, and `get_unlabeled` are part of the same interface but documented in slice 08 (Read Path) where their query semantics, cursor stability, and shard implications belong.

---

## 4. Identity Resolution — Blocking Key Generation

Blocking keys reduce the candidate search space for identity resolution without missing true matches.

```python
# repositories/es/identity/blocking.py

def generate_blocking_keys(input: ContactImportInput) -> list[str]:
    keys = []

    for phone in input.phone_numbers:
        e164 = normalize_phone(phone["number"])
        if e164:
            keys.append(f"phone:{e164}")                       # Exact phone match
            keys.append(f"phone_last7:{e164[-7:]}")            # Last 7 digits (fuzzy)

    for email in input.email_addresses:
        addr = normalize_email(email["address"])
        if addr:
            keys.append(f"email:{addr}")                       # Exact email
            domain = addr.split("@")[1]
            local = addr.split("@")[0]
            keys.append(f"email_local:{local}")                # Local part only (fuzzy)

    if input.family_name and input.given_name:
        name_key = f"name:{soundex(input.family_name)}:{input.given_name[0].lower()}"
        keys.append(name_key)                                  # Phonetic family + first initial

    return list(set(keys))
```

### Phone E.164 Normalization Contract

- Library: `phonenumbers` (Google libphonenumber Python port, 8.x).
- Default parse region: `US` (V1). User-locale override deferred to V1.5.
- Format with `phonenumbers.format_number(num, PhoneNumberFormat.E164)`.

**Invalid number contract.** When `phonenumbers.parse(...)` raises `NumberParseException`, the wrapper:

1. Sets `phone.e164 = null` on the contact document.
2. Writes the original input to `phone.raw` (preserved verbatim, no transformation).
3. Strips all non-digit characters from `phone.raw`; if 7+ digits remain, generates ONLY the `phone_last7:{last7_digits}` blocking key (skips the `phone:{e164}` key).
4. If fewer than 7 digits remain after stripping, generates no phone-derived blocking key for this entry.

**Strict mode.** Callers may pass `strict=True` to `import_contact`; in strict mode, `NumberParseException` propagates as a typed `InvalidPhoneError` instead of falling through to raw-digit handling. Default is non-strict.

### Soundex Contract

American Soundex (Russell algorithm) via `jellyfish.soundex(name)`. Returns 4-character codes (e.g., `Smith` → `S530`, `Smyth` → `S530`).

**Known limitation.** American Soundex has a high collision rate for short or unusual surnames and does not handle non-English names well (e.g., `Nguyen` → `N250`, same as `Naga`, `Nahko`). This is acceptable in V1 because Soundex is supplementary — phone E.164 (score 1.0) and email exact (score 0.95) carry the actual matching weight. Soundex contributes only 0.3 to the composite score and never fires in isolation against the 0.85 merge threshold.

Library version pin: `jellyfish>=1.0.0,<2.0.0`. The Soundex output is stable across this version range.

---

## 5. Probabilistic Scorer

```python
# repositories/es/identity/resolver.py

FIELD_WEIGHTS = {
    "exact_phone":      1.0,   # Definitive match
    "exact_email":      0.95,
    "last7_phone":      0.6,
    "email_local":      0.4,
    "phonetic_name":    0.3,
}

MERGE_THRESHOLD = 0.85        # Configurable via env TRIBES_ID_MERGE_THRESHOLD


def score_candidate(input: ContactImportInput, candidate: Contact) -> float:
    """
    Returns 0.0–1.0 match score between import input and existing Contact.
    Score >= MERGE_THRESHOLD → treat as duplicate.
    """
    score = 0.0

    # Exact phone match
    input_phones = {normalize_phone(p["number"]) for p in input.phone_numbers}
    cand_phones  = {p.e164 for p in candidate.phone_numbers}
    if input_phones & cand_phones:
        score = max(score, FIELD_WEIGHTS["exact_phone"])

    # Exact email match
    input_emails = {normalize_email(e["address"]) for e in input.email_addresses}
    cand_emails  = {e.address for e in candidate.email_addresses}
    if input_emails & cand_emails:
        score = max(score, FIELD_WEIGHTS["exact_email"])

    # ... additional scoring logic (last7, email_local, soundex/initial) ...

    return score
```

The `score_candidate` function accumulates field weights **additively, capping the composite score at 1.0**. A single `exact_phone` match (weight 1.0) reaches the cap on its own; multiple weaker signals sum (e.g., `last7_phone + phonetic_name = 0.6 + 0.3 = 0.9`, per test plan **T-CONTACT-IDRES-025 — the canonical case for the additive rule**). The `max(score, FIELD_WEIGHTS[...])` calls in the sketch above are equivalent to additive-with-cap when only that one signal matches; the elided scoring logic for `last7_phone`, `email_local`, and `phonetic_name` accumulates with `score += weight` and the function returns `min(score, 1.0)`.

`MERGE_THRESHOLD` is read from `TRIBES_ID_MERGE_THRESHOLD` (default 0.85) per shared-context.

---

## 6. Identity Resolution Merge — Field-Level Rules

**Trigger.** `import_contact` resolves a candidate with composite similarity score >= 0.85.

| Field | Rule |
|---|---|
| `blocking_keys` (array) | UNION — append incoming keys not already present; NEVER replace or truncate. |
| `phone_numbers` (nested, keyed by `value_hash`) | UNION by `value_hash`. Existing record preserved on hash collision. No deletions. |
| `email_addresses` (nested, keyed by `value_hash`) | Same as `phone_numbers`. |
| `family_name`, `given_name` | Incoming wins if non-empty (after trim); else candidate preserved. |
| `display_name` | Recomputed from winning `given_name`/`family_name` after merge. |
| `canonical_id` | IMMUTABLE after first assignment. Incoming `canonical_id` recorded in `merge_audit` only. |
| `resolution_status` | Transitions: `unresolved` → `candidate` → `merged`. Once `merged`, no further transitions without explicit admin override (V2). |
| All other scalars (incl. `source`) | Candidate (existing) wins. Incoming recorded in `merge_audit.incoming_snapshot`. |

**`canonical_id` Immutability.** Wrapper MUST validate before issuing `update`; raise `MergeIntegrityError` if caller attempts to overwrite.

**Concurrency Safety.** All merge updates MUST use `if_seq_no` + `if_primary_term` from the candidate document. The wrapper internally retries the full read-merge-write cycle up to 3 times. Each retry attempt's `VersionConflictEngineException` (the raw Elasticsearch optimistic-lock error) is logged at WARN level and **not raised** — `VersionConflictError` from Foundation §7 never surfaces above the merge wrapper. Only after the 3rd consecutive failure does the wrapper raise `MergeConflictError` to the caller, who may decide whether to retry externally.

**Idempotency Token.** Callers MUST supply `import_idempotency_token` (UUID v4, stable for the lifetime of a single import). Before merging, wrapper checks `merge_audit` for an existing record with matching token + same `canonical_id`. If found: return previously recorded result without re-applying.

**Audit Trail (`merge_audit` nested field on contact, append-only):**

```
merge_audit[]:
  import_idempotency_token   keyword
  merged_at                  date
  similarity_score           float
  incoming_snapshot          object   (enabled: false)
  fields_overwritten         keyword[]
  merged_by                  keyword
```

Wrapper MUST NOT delete or overwrite prior entries.

---

## 7. Write Internals — `import_contact`

```python
# Step 1: Normalize inputs
e164_phones  = [normalize_phone(p) for p in input.phone_numbers]
norm_emails  = [normalize_email(e) for e in input.email_addresses]
blocking_keys = generate_blocking_keys(input)

# Step 2: Candidate search (read step, informs write decision)
candidates = await self._find_candidates(user_id, blocking_keys)
best = max(candidates, key=lambda c: score_candidate(input, c), default=None)

if best and score_candidate(input, best) >= MERGE_THRESHOLD:
    # Duplicate detected — apply field-level merge rules under version pin,
    # append a merge_audit entry, and return canonical without writing a new doc
    return await self._merge_into(best, input)

# Step 3: Index new contact
contact_id = str(uuid4())
doc = build_contact_doc(user_id, contact_id, input, blocking_keys)

await self.client.index(
    index=self.config.contacts_index,
    id=contact_id,
    document=doc,
    # refresh contract: cold path uses refresh=False;
    # the merge update path uses refresh="wait_for" (see slice 07)
)
return Contact(**doc)
```

### Refresh contract for this slice

- `import_contact` cold path (no merge): `refresh=False` (default).
- `import_contact` merge update path: `refresh="wait_for"` (per shared-context exception list).
- `delete`: `refresh=False`.

The full per-method refresh matrix lives in slice 07.

### `batch_import`

```python
operations = []
for contact_input in contacts:
    contact_id = str(uuid4())
    doc = build_contact_doc(user_id, contact_id, contact_input)
    operations.extend([
        {"index": {"_index": self.config.contacts_index, "_id": contact_id}},
        doc,
    ])

response = await self.client.bulk(operations=operations)
created = sum(1 for item in response["items"] if item["index"]["result"] == "created")
merged  = 0   # Identity resolution handled pre-bulk (blocking query pass first)
errors  = [item for item in response["items"] if "error" in item["index"]]

return BatchImportResult(created=created, merged=merged, errors=len(errors))
```

Identity resolution for batch import runs as a single blocking-query pass before the bulk write. Per-document errors do not abort the batch; counts and errors are returned.

### `delete` (cascade reference)

```python
# 1. Verify ownership (get_by_id raises ContactOwnershipError if mismatch)
await self.get_by_id(user_id, contact_id)

# 2. Delete all assignments for this contact first (slice 06 owns the cascade contract)
await self.assignment_repo.delete_by_contact(user_id, contact_id)

# 3. Hard delete the contact document
try:
    await self.client.delete(index=self.config.contacts_index, id=contact_id)
except NotFoundError:
    raise ContactNotFoundError(contact_id)
```

---

## 8. Stories (Reference)

From spec §13:

- **Story 2: Contact Domain Model & Base Repository** — Pydantic models, abstract `IContactRepository`, phone/email normalization helpers, SHA-256 hashing.
- **Story 3: ContactRepository — Import & Get** — `import_contact`, `get_by_id`, `delete`.
- **Story 5: ContactRepository — Batch Import** — bulk path, partial-success semantics.
- **Story 13: Identity Resolution — Blocking** — `blocking.py` with phone/email/name keys.
- **Story 14: Identity Resolution — Probabilistic Scorer & Integration** — `resolver.py`, integration into `import_contact`.

Stories 4 and 6 (search, `get_by_bins`, `get_unlabeled`) are scoped into slice 08 (Read Path), not here.

---

Pairs with `02-contacts-tests.md`.
