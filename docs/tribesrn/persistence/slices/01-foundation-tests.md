# Slice 1 — Foundation: Tests

> **Read `00-shared-context.md` FIRST.** This slice assumes the V1 decisions, vector inventory, refresh contract, perf baselines, naming conventions, and glossary are already in context. Do not re-state them here.

## Related slices

This is the prerequisite slice for everything else. The mapping tests, V1 vector-absence guard, and migration-smoke tests defined here must pass before any later slice runs in CI.

---

## Conventions referenced

The full conventions block (test ID scheme, file naming, fixture setup, real-ES integration rule, pytest markers) lives in the test plan preamble. Each slice file copies in only what's load-bearing for its own tests; slices 02–08 reference these conventions by ID without restating.

### Test ID Scheme

`T-<AREA>-<NNN>`. Areas used in this slice: `MAP` (index mappings & schema, Section 2 of the source plan).

### Markers

- `@pytest.mark.integration` — hits ephemeral Docker ES.
- `@pytest.mark.regression_guard` — asserts a V1 boundary that must not silently regress.

### Fixture setup (load-bearing for Foundation)

- Session-scoped `es_container` boots ES once per test session.
- Function-scoped `clean_indices` deletes and re-creates the V1 indices with the canonical mappings before each test. **All Foundation tests use `clean_indices`** unless explicitly noted (e.g., the migration-smoke tests in this slice mutate the index lifecycle and manage their own fixture).

---

## Section 2: Index Mappings & Schema

`@pytest.mark.integration`. Each test uses the `clean_indices` fixture. Spec sections validated: index mappings for `tribes_contacts`, `tribes_bins`, `tribes_assignments`, `tribes_tribes`, plus `tribes_pending_jobs`.

**Note on vector fields:** V1 has zero `dense_vector` fields. T-MAP tests assert this absence — see T-MAP-V1-VEC-NONE below. V2 vector field tests live in a separate V2 test plan, not this document.

### `tribes_contacts` mapping

| ID        | Asserts                                                                                                       | Setup                                | Trigger                                  | Expected                                                            |
| --------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------- | ------------------------------------------------------------------- |
| T-MAP-001 | Index exists with the canonical name `tribes_contacts` after wrapper init                                     | None                                 | Call wrapper bootstrap                   | `client.indices.exists("tribes_contacts")` returns True             |
| T-MAP-002 | `phone_numbers` is a `nested` field with `value`, `value_hash`, `country_code`, `extension` properties         | Boot complete                        | `client.indices.get_mapping`             | Mapping matches spec exactly                                        |
| T-MAP-003 | `email_addresses` is a `nested` field with `value`, `value_hash`, `local_part_normalized`, `domain` props      | Boot complete                        | `client.indices.get_mapping`             | Mapping matches spec exactly                                        |
| T-MAP-004 | `blocking_keys` is a `keyword` array (not `text`)                                                              | Boot complete                        | `client.indices.get_mapping`             | Type is `keyword`                                                   |
| T-MAP-005 | `family_name` and `given_name` are `text` with `keyword` sub-field for sorting                                 | Boot complete                        | Inspect mapping                          | `fields.keyword` present                                            |
| T-MAP-006 | `display_name` uses the project's `tribes_name` analyzer with edge_ngram for prefix search                     | Boot complete                        | Inspect mapping                          | Analyzer name matches; tokenizer/filter chain matches               |
| T-MAP-007 | `canonical_id` is `keyword`, immutable (mapping `index: true`, no analyzer)                                    | Boot complete                        | Inspect mapping                          | Type `keyword`                                                      |
| T-MAP-008 | `merge_audit` is `nested` with `merged_from`, `merged_at`, `score`, `reason`                                   | Boot complete                        | Inspect mapping                          | All four fields present, types correct                              |
| T-MAP-009 | `import_idempotency_token` is `keyword`                                                                        | Boot complete                        | Inspect mapping                          | Type `keyword`                                                      |
| T-MAP-010 | Custom analyzer `tribes_name` defined at index level (not type level)                                          | Boot complete                        | `client.indices.get_settings`            | `analysis.analyzer.tribes_name` present                             |
| T-MAP-011 | Mapping is idempotent: running boot twice does not error and does not alter the mapping                        | Boot once                            | Boot again                               | Second call no-op; mapping unchanged                                |

### `tribes_bins` mapping

| ID        | Asserts                                                                                                | Setup         | Trigger                | Expected                                            |
| --------- | ------------------------------------------------------------------------------------------------------ | ------------- | ---------------------- | --------------------------------------------------- |
| T-MAP-020 | Index `tribes_bins` exists                                                                             | None          | Wrapper boot           | Exists                                              |
| T-MAP-021 | `name` is `text` with `keyword` sub-field                                                              | Boot complete | Inspect mapping        | Both present                                        |
| T-MAP-022 | `normalized_name` is `keyword` (NOT `text`); enables exact-match aggregations                          | Boot complete | Inspect mapping        | Type `keyword`                                      |
| T-MAP-023 | `owner_user_id` is `keyword`                                                                           | Boot complete | Inspect mapping        | Type `keyword`                                      |
| T-MAP-024 | `assignment_count` is `long`                                                                           | Boot complete | Inspect mapping        | Type `long`                                         |
| T-MAP-025 | `color_hex` is `keyword`                                                                               | Boot complete | Inspect mapping        | Type `keyword`                                      |
| T-MAP-026 | `domain` is `keyword` (controlled vocabulary)                                                          | Boot complete | Inspect mapping        | Type `keyword`                                      |
| T-MAP-027 | Number of primary shards equals 3 (Foundation locks `tribes_bins` shards at 3 to keep slice 08 distribution tests valid) | Boot complete | `get_settings`         | `index.number_of_shards == "3"`                     |

### `tribes_assignments` mapping

| ID        | Asserts                                                                                                                | Setup         | Trigger         | Expected                                          |
| --------- | ---------------------------------------------------------------------------------------------------------------------- | ------------- | --------------- | ------------------------------------------------- |
| T-MAP-040 | Index `tribes_assignments` exists                                                                                      | None          | Boot            | Exists                                            |
| T-MAP-041 | `is_active` is `boolean`                                                                                               | Boot complete | Inspect mapping | Boolean                                           |
| T-MAP-042 | `affinity_weight` is `float` (or `half_float`); document the choice                                                    | Boot complete | Inspect mapping | Numeric type matches spec                         |
| T-MAP-043 | `flick_velocity` is `float`                                                                                            | Boot complete | Inspect mapping | Numeric type matches spec                         |
| T-MAP-044 | Denormalized fields `bin_name`, `bin_domain`, `bin_color_hex` present and are `keyword`                                | Boot complete | Inspect mapping | All three present, all `keyword`                  |
| T-MAP-045 | `owner_user_id`, `contact_id`, `bin_id` are `keyword`                                                                  | Boot complete | Inspect mapping | All three are keyword                             |
| T-MAP-046 | Number of primary shards equals 3 (slice 08 distribution test depends on this)                                         | Boot complete | `get_settings`  | `index.number_of_shards == "3"`                   |

### `tribes_tribes` mapping

| ID        | Asserts                                                                          | Setup         | Trigger         | Expected                                       |
| --------- | -------------------------------------------------------------------------------- | ------------- | --------------- | ---------------------------------------------- |
| T-MAP-060 | Index `tribes_tribes` exists                                                     | None          | Boot            | Exists                                         |
| T-MAP-061 | `tribe_type` is `keyword` (values: `"static"`, `"dynamic"`)                      | Boot complete | Inspect mapping | Type `keyword`                                 |
| T-MAP-062 | `member_user_ids` is `keyword` array                                             | Boot complete | Inspect mapping | Array of keyword                               |
| T-MAP-063 | `query_bin_ids` is `keyword` array (used by dynamic tribes)                      | Boot complete | Inspect mapping | Array of keyword                               |
| T-MAP-064 | `query_operator` is `keyword` (values: `"any"`, `"all"`)                         | Boot complete | Inspect mapping | Type `keyword`                                 |
| T-MAP-065 | `query_city_filter` and `query_domain_filter` are `keyword` arrays               | Boot complete | Inspect mapping | Both arrays                                    |
| T-MAP-066 | `member_count_cached` is `long`                                                  | Boot complete | Inspect mapping | Type `long`                                    |

> Note: spec §3.4 names this field `member_contact_ids` while the test plan names it `member_user_ids`. Foundation epic locks one name (recommendation: `member_contact_ids` — matches the spec and the domain-model naming in slice 05).

### `tribes_pending_jobs` mapping

| ID        | Asserts                                                                                                          | Setup         | Trigger         | Expected                                                  |
| --------- | ---------------------------------------------------------------------------------------------------------------- | ------------- | --------------- | --------------------------------------------------------- |
| T-MAP-080 | Index `tribes_pending_jobs` exists                                                                               | None          | Boot            | Exists                                                    |
| T-MAP-081 | `job_id` is the document `_id`; not stored as a separate field                                                   | Boot complete | Inspect mapping | No `job_id` property; `_id` policy in spec                |
| T-MAP-082 | `op_type` is `keyword`                                                                                           | Boot complete | Inspect mapping | Type `keyword`                                            |
| T-MAP-083 | `primary_id` is `keyword`                                                                                        | Boot complete | Inspect mapping | Type `keyword`                                            |
| T-MAP-084 | `query_dsl` is `object` with `enabled: false` (opaque blob, not searched)                                        | Boot complete | Inspect mapping | `enabled: false`                                          |
| T-MAP-085 | `status` is `keyword` (values: `"pending"`, `"succeeded"`, `"failed_permanent"`)                                 | Boot complete | Inspect mapping | Type `keyword`                                            |
| T-MAP-086 | `retry_count` is `integer`                                                                                       | Boot complete | Inspect mapping | Type `integer`                                            |
| T-MAP-087 | `created_at`, `last_attempt_at`, `next_attempt_at` are `date` with strict ISO-8601                               | Boot complete | Inspect mapping | All three are dates                                       |
| T-MAP-088 | `last_error` is `text` (free-form ES error message)                                                              | Boot complete | Inspect mapping | Type `text`                                               |

### V1 vector-field absence

**T-MAP-V1-VEC-NONE** — `@pytest.mark.regression_guard`. Inspect every V1 index mapping (`tribes_contacts`, `tribes_bins`, `tribes_assignments`, `tribes_tribes`, `tribes_pending_jobs`) and assert that no field has type `dense_vector`. Setup: index creation via repository setup. Trigger: `GET /<index>/_mapping`. Expected: traverse the mapping tree and assert no leaf has `"type": "dense_vector"`. Validates: V1 Vector Field Inventory (shared-context section "V1 Vector Field Inventory: NONE").

This test is the canary for the V1 boundary. A future contributor who introduces a `dense_vector` field for vector search must explicitly amend this test, the spec, and the shared-context doc — silent introduction is impossible.

### Mapping migration smoke

| ID        | Asserts                                                                                                  | Setup                              | Trigger                          | Expected                                      |
| --------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------- | --------------------------------------------- |
| T-MAP-100 | Applying canonical mappings to a fresh empty cluster succeeds                                            | Empty ES                           | Wrapper boot                     | All five indices present                      |
| T-MAP-101 | Re-applying mappings is a no-op (no exception, no `IllegalArgumentException`)                            | Already-booted cluster             | Wrapper boot a second time       | No exception                                  |
| T-MAP-102 | Adding a new field to an existing index via the wrapper's mapping-update path succeeds                   | Booted cluster                     | Wrapper applies updated mapping  | New field present                             |
| T-MAP-103 | Attempt to change an existing field's type raises `MappingMigrationConflictError` (typed exception)       | Booted cluster                     | Wrapper applies incompatible map | Typed exception, no silent index corruption   |

---

Pairs with `01-foundation-spec.md`.
