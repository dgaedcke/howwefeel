# Slice 2 — Contacts: Tests

> **Read `00-shared-context.md` FIRST.** This slice assumes the V1 decisions, vector inventory, refresh contract, perf baselines, naming conventions, and glossary are already in context. Do not re-state them here.

## Related slices

Depends on slice 01 (Foundation) for fixtures (`clean_indices`, `es_client`, `contact_repo`). Search/cursor tests for `ContactRepository` live in slice 08.

---

## Conventions

Test ID areas used here: `CONTACT`, `CONTACT-IDRES`, `CONTACT-MERGE`. Markers: `@pytest.mark.integration` with `@pytest.mark.slow` for tests that wait on refresh.

Spec sections validated: identity resolution, blocking keys, probabilistic scoring, field-level merge rules, idempotency token, version pin, merge_audit, phone E.164 contract, Soundex contract.

---

## Section 3: ContactRepository

### Basic CRUD

| ID            | Asserts                                                                            | Setup           | Trigger                       | Expected                                          |
| ------------- | ---------------------------------------------------------------------------------- | --------------- | ----------------------------- | ------------------------------------------------- |
| T-CONTACT-001 | `create()` writes a doc and returns a non-empty `canonical_id`                     | Clean indices   | `repo.create({...})`          | Returned `canonical_id` is a non-empty string     |
| T-CONTACT-002 | `get_by_id()` returns the doc just created                                         | One doc created | `repo.get_by_id(canonical_id)`| Doc fields equal the input                        |
| T-CONTACT-003 | `get_by_id()` on missing id returns `None`, not raises                             | Clean indices   | `repo.get_by_id("nope")`      | `None`                                            |
| T-CONTACT-004 | `delete()` hard-deletes (cascade is service-layer, see slice 06)                   | One doc created | `repo.delete(canonical_id)`   | Subsequent `get_by_id` returns `None`             |
| T-CONTACT-005 | `count_for_owner(owner_user_id)` returns correct count after writes                | 5 docs created  | `repo.count_for_owner(owner)` | Returns 5                                         |

### Blocking key generation

Spec: `phone:{e164}`, `phone_last7:{last7}`, `email:{addr}`, `email_local:{local}`, `name:{soundex(family)}:{initial}`.

| ID                  | Asserts                                                                                       | Setup | Trigger                                                       | Expected                                                |
| ------------------- | --------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------- | ------------------------------------------------------- |
| T-CONTACT-IDRES-001 | `phone:{e164}` block key generated via `phonenumbers` (libphonenumber Python port), parsed with `region="US"`; e.g., `"(555) 123-4567"` produces `+15551234567` | None  | `repo._compute_blocking_keys({"phone_numbers": [{"value": "(555) 123-4567"}]})` | Set contains `"phone:+15551234567"`                     |
| T-CONTACT-IDRES-002 | `phone_last7:{last7}` block key generated from the last 7 digits                              | None  | Same                                                          | Set contains `"phone_last7:1234567"`                    |
| T-CONTACT-IDRES-003 | Multiple phones produce one phone block key per number                                        | None  | Two phones                                                    | Set contains both `phone:` keys                         |
| T-CONTACT-IDRES-004 | Phone with an extension is normalized to E.164 base via `phonenumbers` parsed with `region="US"`; the `phone:{e164}` blocking key omits the extension (e.g., `"(555) 123-4567 ext 123"` produces `+15551234567`) | None  | Phone with `extension="123"`                                  | E.164 key omits extension                               |
| T-CONTACT-IDRES-005 | `email:{addr}` block key uses lowercased full address                                         | None  | `compute_blocking_keys({"email_addresses": ["A@Example.COM"]})` | Contains `"email:a@example.com"`                        |
| T-CONTACT-IDRES-006 | `email_local:{local}` uses local part only                                                    | None  | Same                                                          | Contains `"email_local:a"`                              |
| T-CONTACT-IDRES-007 | `name:{soundex(family)}:{initial}` uses American Soundex via `jellyfish.soundex` (4-char output, library pin `jellyfish>=1.0.0,<2.0.0`); `Smith` → `S530`, `Smyth` → `S530` (same code) | None  | `{"family_name": "Smith", "given_name": "John"}`              | Contains `"name:S530:J"`                                |
| T-CONTACT-IDRES-008 | Missing family name produces no `name:` key (don't generate a degenerate key)                 | None  | `{"given_name": "John"}`                                      | No `name:` prefix in set                                |
| T-CONTACT-IDRES-009 | Missing given name produces no `name:` key                                                    | None  | `{"family_name": "Smith"}`                                    | No `name:` prefix in set                                |
| T-CONTACT-IDRES-010 | Empty input produces empty set                                                                | None  | `compute_blocking_keys({})`                                   | Empty set                                               |

**T-CONTACT-IDRES-PHONE-INVALID-A** — Invalid phone string falls through to raw-digits last7. Setup: contact import with `phone="abc-1234567"`. Trigger: `import_contact` (non-strict). Expected: contact document persisted with `phone.e164=null`, `phone.raw="abc-1234567"`, blocking_keys contains `"phone_last7:1234567"` and does NOT contain any `"phone:{e164}"` entry. Validates: spec §4 — Phone E.164 invalid-number contract.

**T-CONTACT-IDRES-PHONE-INVALID-B** — Invalid phone with fewer than 7 digits generates no phone blocking key. Setup: contact import with `phone="abc"`. Trigger: `import_contact`. Expected: blocking_keys contains no phone-derived entry. Validates: spec §4 — Phone E.164 invalid-number contract.

**T-CONTACT-IDRES-PHONE-STRICT** — Strict mode raises `InvalidPhoneError`. Setup: contact import with `phone="garbage"`, `strict=True`. Trigger: `import_contact(..., strict=True)`. Expected: raises `InvalidPhoneError`; no document persisted. Validates: spec §4 — strict mode contract.

**T-CONTACT-IDRES-SOUNDEX-COLLISION** — Soundex collision does not cause false-positive merge. Setup: two contacts with surnames that produce identical Soundex codes (e.g., `Nguyen` and a controlled second surname collapsing to `N250`), no overlapping phone or email. Trigger: import second contact. Expected: composite similarity score for the candidate match is at most 0.3 (Soundex weight) + initial-match weight; well below the 0.85 merge threshold; second contact persisted as a separate document. Validates: spec §4 — Soundex known-limitation contract.

### Probabilistic scoring

Spec: phone exact = 1.0, email exact = 0.95, phone last7 = 0.6, email local = 0.4, soundex name = 0.3, threshold = 0.85.

| ID                  | Asserts                                                                                                                  | Setup                                                | Trigger                                  | Expected                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | ---------------------------------------- | ----------------------------------------- |
| T-CONTACT-IDRES-020 | Phone exact match scores 1.0                                                                                             | Two contacts share full E.164                        | `repo._score(candidate, incoming)`        | Score == 1.0                              |
| T-CONTACT-IDRES-021 | Email exact match scores 0.95                                                                                            | Two contacts share full email                        | Same                                     | Score == 0.95                             |
| T-CONTACT-IDRES-022 | Phone last7 match scores 0.6                                                                                             | Two contacts share last 7 only                       | Same                                     | Score == 0.6                              |
| T-CONTACT-IDRES-023 | Email local match scores 0.4                                                                                             | Two contacts share local part only                   | Same                                     | Score == 0.4                              |
| T-CONTACT-IDRES-024 | Soundex name match scores 0.3                                                                                            | Two contacts share family soundex + given initial    | Same                                     | Score == 0.3                              |
| T-CONTACT-IDRES-025 | Multiple matches sum (phone last7 0.6 + soundex 0.3 = 0.9, above threshold)                                              | Constructed pair                                     | Same                                     | Score == 0.9, above threshold             |
| T-CONTACT-IDRES-026 | Score below threshold (0.85) does NOT trigger merge                                                                      | Pair scoring 0.4                                     | `repo.import_contact(incoming)`           | New contact created, no merge_audit       |
| T-CONTACT-IDRES-027 | Score at threshold (0.85) triggers merge (boundary inclusive)                                                            | Pair scoring exactly 0.85                            | `repo.import_contact(incoming)`           | Merge into existing                       |
| T-CONTACT-IDRES-028 | Score above threshold triggers merge                                                                                     | Pair scoring 1.0                                     | `repo.import_contact(incoming)`           | Merge into existing                       |
| T-CONTACT-IDRES-029 | Multiple candidates above threshold: highest score wins; warning logged                                                  | 3 candidates: 0.86, 0.9, 0.95                        | `repo.import_contact(incoming)`           | Merged into 0.95 candidate; warning log   |
| T-CONTACT-IDRES-030 | Candidate fetch returns empty: new contact created (covered also as failure mode in slice 08)                            | Empty candidate set                                  | `repo.import_contact(incoming)`           | New contact, no merge_audit               |

### Field-level merge rules (CONTACT-MERGE)

Spec: UNION rules on `blocking_keys`, nested arrays merged by `value_hash`, incoming-wins-if-non-empty for names, immutable `canonical_id`, append-only `merge_audit`.

| ID                  | Asserts                                                                                                              | Setup                                                                                  | Trigger                                                       | Expected                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| T-CONTACT-MERGE-001 | `blocking_keys` UNION: existing has {a, b}, incoming has {b, c}, result is {a, b, c}                                  | Existing contact written; incoming with overlapping keys                               | `repo.import_contact(incoming)`                                | Doc has all three keys; no duplicates                                                          |
| T-CONTACT-MERGE-002 | `phone_numbers` nested UNION by `value_hash`: same hash dedups                                                        | Existing has phone hash X; incoming has phone hash X with different `country_code`     | `repo.import_contact(incoming)`                                | One nested entry remains (existing wins on hash collision per spec); test the documented rule  |
| T-CONTACT-MERGE-003 | `phone_numbers` UNION: distinct hashes both kept                                                                     | Existing has hash X; incoming has hash Y                                               | `repo.import_contact(incoming)`                                | Two nested entries, both present                                                               |
| T-CONTACT-MERGE-004 | `email_addresses` nested UNION by `value_hash`                                                                       | As above for emails                                                                    | Same                                                          | Same as 002 / 003 for emails                                                                   |
| T-CONTACT-MERGE-005 | `family_name` incoming-wins-if-non-empty: existing has `"Smith"`, incoming has `"Jones"`                              | Existing written                                                                       | `repo.import_contact({"family_name": "Jones", ...})`           | Result has `"Jones"`                                                                           |
| T-CONTACT-MERGE-006 | `family_name` incoming-empty-loses: existing `"Smith"`, incoming `""` or missing                                      | Existing written                                                                       | `repo.import_contact({...no family_name...})`                  | Result still has `"Smith"`                                                                     |
| T-CONTACT-MERGE-007 | `given_name` follows same incoming-wins-if-non-empty rule                                                            | As above for given                                                                     | Same                                                          | Same                                                                                           |
| T-CONTACT-MERGE-008 | `display_name` follows same incoming-wins-if-non-empty rule                                                          | As above for display                                                                   | Same                                                          | Same                                                                                           |
| T-CONTACT-MERGE-009 | `canonical_id` is immutable: merge into existing must NOT overwrite the existing `canonical_id`                       | Existing has `canonical_id="C-123"`                                                    | `repo.import_contact(incoming)` triggers merge                 | Result `canonical_id == "C-123"`; incoming's tentative id discarded                            |
| T-CONTACT-MERGE-010 | `merge_audit` append-only: each merge adds one entry, never replaces                                                  | Existing has 2 audit entries                                                           | Trigger 1 more merge                                          | Audit length is 3                                                                              |
| T-CONTACT-MERGE-011 | `merge_audit` entry contains `import_idempotency_token`, `incoming_snapshot`, `fields_overwritten`, `merged_by`       | Trigger one merge                                                                      | Inspect last audit entry                                       | All 4 fields present, types correct                                                            |
| T-CONTACT-MERGE-012 | `merge_audit` `incoming_snapshot` records the discarded canonical_id (incoming's tentative)                          | Trigger merge                                                                          | Inspect last audit entry                                       | `incoming_snapshot.canonical_id` equals incoming's tentative id                                |
| T-CONTACT-MERGE-013 | `if_seq_no`/`if_primary_term` version pin: after wrapper exhausts its 3 internal retries against repeated optimistic-lock conflicts, surfaces typed `MergeConflictError` (raw `VersionConflictError` from Foundation §7 is logged but never propagated) | Concurrent: read existing, then mutate it from another client across all 3 internal retry cycles of the wrapper | Merge call | `MergeConflictError` raised after 3 retries; caller can decide whether to retry externally |
| T-CONTACT-MERGE-014 | After version conflict, retrying with fresh read succeeds                                                            | Trigger 013                                                                            | Catch, re-read, retry                                          | Merge succeeds; one final doc                                                                   |
| T-CONTACT-MERGE-015 | Refresh contract: merge update path uses `refresh="wait_for"` so a follow-up read sees the change                     | Existing contact; trigger merge                                                        | Immediately `repo.get_by_id`                                   | Merged fields visible; no `client.indices.refresh()` call needed (covered also in slice 07)   |

### Import idempotency token

| ID                  | Asserts                                                                                                          | Setup                                          | Trigger                                                              | Expected                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| T-CONTACT-MERGE-020 | Same `import_idempotency_token` submitted twice produces exactly one merge_audit entry                           | None                                           | Call `import_contact(payload, token="T-1")` twice                     | Audit length == 1                                                              |
| T-CONTACT-MERGE-021 | Same token but different payload still treated as duplicate (token-as-dedup-key, not payload-hash)                | None                                           | Two calls, same token, different name                                 | Audit length == 1; second call returns the result of the first (no overwrite) |
| T-CONTACT-MERGE-022 | Different tokens with same payload produce two audit entries (or two contacts depending on identity resolution)  | None                                           | Two calls, different tokens, same payload                            | Either two distinct contacts or one with two audit entries (per spec)         |
| T-CONTACT-MERGE-023 | Token is per-import-source-scoped (token only collides within the same source namespace)                         | None                                           | Two calls, same token, different `source` field                       | Two contacts (no false-collision across sources)                               |

---

Pairs with `02-contacts-spec.md`.
