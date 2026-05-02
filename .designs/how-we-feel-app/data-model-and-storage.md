# How We Feel — Data Model & Storage Design

**Bead:** `hwf-gap` · **Author:** how-we-feel/furiosa · **Date:** 2026-05-02
**Inputs:** `.prd-reviews/how-we-feel-app/prd-draft.md`,
`.prd-reviews/how-we-feel-app/prd-review.md`, coherence review (`hwf-ln34`)
**Scope:** Client (mobile) + server data models, SQLite schema,
migrations, schema evolution, last-write-wins conflict resolution, soft
deletes.

---

## Executive Summary

This document specifies the persistence layer for *How We Feel* under
the working assumption that **v1 is offline-only on the device** and
**multi-device sync is a v1.x deliverable** (per PRD review Tier-1 Q3,
recommended cut). Every entity is, however, designed *sync-ready* from
day one — universal `created_at` / `updated_at` / `deleted_at`
timestamps, client-generated UUID v7 primary keys, monotonic schema
versioning, and a tombstone-based soft-delete model. The cost of
sync-readiness is small (three columns and a discipline); the cost of
retrofitting it after launch is a forced migration of every row a user
has ever logged.

**Key decisions, summarized:**

| # | Decision | Rationale |
|---|---|---|
| D1 | Client-generated **UUID v7** for every row | Offline-first; sortable; embeds creation time; idempotent server upserts |
| D2 | **`updated_at` is the LWW timestamp**, device-assigned with skew clamping | PRD Open Q9 explicitly rules out `logged_at` (felt time ≠ write time) |
| D3 | **Soft delete via `deleted_at`** on every entity, hard purge after 30-day grace | Sync correctness + GDPR Art. 17 ≤ 30-day deadline |
| D4 | **SQLCipher** for at-rest encryption; key in Expo SecureStore | PRD Constraints; mental-health data = GDPR Art. 9 special category |
| D5 | **Schema_versions table + numbered, monotonic migrations** with fixture-DB tests | PRD review §"Schema migration framework on device"; silent-data-loss prevention |
| D6 | **Mood Meter cell stored as `(valence, arousal)` integer coordinates + label_id** | Survives both UX outcomes (10×10 grid OR quadrant+intensity); pure data, not UI |
| D7 | **No photo attachments in v1 schema** (deferred to v1.x migration) | PRD review Tier-2 Q8 recommendation |
| D8 | **Edit-trail kept as a separate table** (`emotion_log_edits`), opt-in via setting | Resolves PRD Story 8 contradiction (hidden audit ≠ acceptable per scope leg) |
| D9 | **Streak fields are derived, not stored** | Allows PRD Tier-2 Q9 "drop streaks" to be a pure UI change |
| D10 | **Crisis resources bundled as JSON asset** in v1; remote-config in v1.x | PRD review Tier-1 Q4 "static link" recommendation |

The schema is **not gated on Tier-1 Q3 (sync v1 vs. v1.x)** — both
outcomes use the same client schema. The server schema mirrors the
client schema and adds identity / deletion-queue / sync-cursor
infrastructure; if sync ships in v1.x, only the server is added later.

---

## 1. Design Principles

1. **Local-first.** Every entity can be created, read, updated, and
   deleted entirely on-device with no network. The DB is the source of
   truth for the client UI; the server (if/when present) is a
   replication target.
2. **Sync-ready from day one.** Universal timestamps, client-generated
   IDs, soft-delete tombstones, and a deterministic LWW rule are
   present *in v1* even with no server. This is cheap and avoids a
   forced migration of every existing log when sync ships.
3. **Privacy by construction.** Schema, encryption, and indexing decisions
   assume the data is GDPR Art. 9 special category. Journal text never
   appears in non-encrypted columns, never in metrics, never in error
   payloads.
4. **Forward-compatible schema evolution.** Migrations are additive by
   default, tested against fixture DBs from each prior version, and
   gated by a `schema_versions` table that the app refuses to start if
   it can't reconcile.
5. **Determinism over heuristics.** Conflict resolution is a single
   rule (LWW on `updated_at`) with explicit tie-breakers. No "merge
   strategies" for free-text — last write wins entirely; the optional
   audit trail preserves the prior text if the user opts in.
6. **Decouple data from UI.** The data model survives multiple UX
   outcomes (PRD Open Q1: 10×10 grid vs. quadrant+intensity vs.
   hybrid). Mood Meter selection is stored as `(valence, arousal,
   label_id)` — pure coordinates and a label key, not a "cell index"
   that bakes the UI into rows.

---

## 2. Entity Inventory

| Entity | Layer | Purpose |
|---|---|---|
| `users` | Client (synthetic) + Server | Identity. In account-less mode the client maintains a synthetic local user row so all foreign keys remain stable when an account is later linked. |
| `devices` | Client (self-row) + Server | Device identity. One row per install per device. Stable across re-launches; *not* across re-installs without explicit re-link. |
| `emotion_logs` | Client + Server | The core entity: one row per check-in. |
| `context_tags` | Client (seed) + Server (seed) | Predefined tag taxonomy (Work, Family, etc.) plus user-created tags. |
| `emotion_log_context_tags` | Client + Server | Junction table (logs ↔ tags). |
| `emotion_log_edits` | Client + Server | Append-only edit history (opt-in; see §8). |
| `reminder_schedules` | Client (only) | Local notification schedules; never synced (per PRD Constraints "Local-scheduled only v1"). |
| `coping_activity_favorites` | Client + Server | User favorites for the bundled coping activity library. |
| `app_settings` | Client (only) | Key-value store for per-device preferences (theme, biometric lock, etc.). |
| `sync_cursors` | Client (only) | Per-entity replication cursors (only relevant when sync is enabled). |
| `schema_versions` | Client + Server | Migration bookkeeping (current version + history). |
| `crisis_resources` | Bundled JSON (read-only) | Locale-keyed list of hotlines / urls / coping links. |
| `emotion_taxonomy` | Bundled JSON + DB-resolvable | Versioned label set; see §6. |

**Out of scope for v1 schema** (per PRD review): `photo_attachments`,
`streak_events`, `entitlements` / billing tables, multi-tenant /
B2B2C scopes.

---

## 3. Universal Row Conventions

Every replicable entity (`emotion_logs`, `context_tags`, `emotion_log_context_tags`,
`emotion_log_edits`, `coping_activity_favorites`, `users`, `devices`)
**MUST** carry the following columns:

```sql
id           TEXT PRIMARY KEY,        -- UUID v7, client-generated
user_id      TEXT NOT NULL,           -- FK to users(id) (synthetic in account-less mode)
created_at   INTEGER NOT NULL,        -- UTC, ms since epoch, set on insert, immutable
updated_at   INTEGER NOT NULL,        -- UTC, ms since epoch, mutated on every write, LWW key
deleted_at   INTEGER,                 -- UTC, ms since epoch; NULL = live, non-NULL = tombstone
schema_version INTEGER NOT NULL,      -- snapshot of schema_versions.current at write time
device_id    TEXT NOT NULL            -- writer's device_id (LWW tie-breaker)
```

Notes on each:

- **`id` (UUID v7).** RFC 9562 v7 — first 48 bits are a UNIX-ms
  timestamp, remaining bits are random. Sortable by creation time
  without needing `created_at`. Client-generated so offline writes
  don't await a server round-trip. Server respects client IDs
  (idempotent `INSERT ... ON CONFLICT DO UPDATE`); IDs collide with
  cosmologically negligible probability.
- **`created_at` vs. `updated_at`.** Both are device-assigned UTC
  milliseconds. `created_at` is set once at insert and never modified.
  `updated_at` is set to `now()` on every mutation and is the
  authoritative LWW key (D2). Storing both as `INTEGER` ms (not
  TEXT/ISO) makes range scans cheap and avoids timezone parsing bugs.
- **`deleted_at`.** Soft-delete tombstone. Replicates like any other
  field. UI hides rows where `deleted_at IS NOT NULL`. Hard purge job
  removes rows older than the grace window (§7).
- **`schema_version`.** Stamps the writer's schema knowledge into
  every row. Lets readers detect "this row was written by a newer
  version" and decide to refuse / soft-degrade / migrate. Cheap
  insurance for an offline-first app where the user can stay on an old
  version for months.
- **`device_id`.** The writing device's stable id (FK to `devices`).
  Used as the deterministic LWW tie-breaker when two devices write at
  the same `updated_at` ms.

For reference-data tables (`context_tags`, `crisis_resources`,
`emotion_taxonomy`), the universal columns simplify: no `device_id` is
required for *system* seed rows (use `'__system__'` as a sentinel),
but user-created `context_tags` carry the same shape as a user-owned
row.

---

## 4. Client SQLite Schema (DDL)

The schema is expressed as SQLite 3 DDL, using SQLCipher for at-rest
encryption (see §11). All tables use `STRICT` mode (SQLite 3.37+) for
column-type enforcement.

### 4.1 Bookkeeping

```sql
CREATE TABLE schema_versions (
  version       INTEGER PRIMARY KEY,
  applied_at    INTEGER NOT NULL,
  description   TEXT NOT NULL,
  app_version   TEXT NOT NULL                -- e.g. "1.0.3"
) STRICT;

CREATE TABLE app_settings (
  key           TEXT PRIMARY KEY,
  value         TEXT NOT NULL,               -- JSON-encoded; readers parse per-key
  updated_at    INTEGER NOT NULL
) STRICT;
```

### 4.2 Identity

```sql
CREATE TABLE users (
  id              TEXT PRIMARY KEY,          -- UUID v7
  account_state   TEXT NOT NULL              -- 'local_only' | 'linked_apple' | 'linked_google'
                  CHECK (account_state IN ('local_only','linked_apple','linked_google')),
  external_id     TEXT,                      -- Apple sub / Google sub when linked; NULL in local mode
  display_name    TEXT,                      -- optional, user-entered
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  device_id       TEXT NOT NULL              -- creating device
) STRICT;

CREATE TABLE devices (
  id              TEXT PRIMARY KEY,          -- UUID v7
  user_id         TEXT NOT NULL,
  platform        TEXT NOT NULL              -- 'ios' | 'android'
                  CHECK (platform IN ('ios','android')),
  os_version      TEXT NOT NULL,             -- e.g. "iOS 17.4.1"
  app_version     TEXT NOT NULL,
  device_label    TEXT,                      -- user-friendly name in Settings ("My iPhone")
  installed_at    INTEGER NOT NULL,
  last_active_at  INTEGER NOT NULL,
  push_token      TEXT,                      -- Expo Push token, or NULL if not granted
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE
) STRICT;

CREATE INDEX idx_devices_user ON devices(user_id);
```

### 4.3 Core: Emotion Logs

```sql
CREATE TABLE emotion_logs (
  id                      TEXT PRIMARY KEY,  -- UUID v7
  user_id                 TEXT NOT NULL,     -- FK users(id)

  -- Mood Meter selection (D6: pure coordinates + label key)
  valence                 INTEGER NOT NULL   -- -50..+50 (pleasantness axis); 0 = neutral
                          CHECK (valence BETWEEN -50 AND 50),
  arousal                 INTEGER NOT NULL   -- -50..+50 (energy axis); 0 = neutral
                          CHECK (arousal BETWEEN -50 AND 50),
  emotion_label_id        TEXT NOT NULL,     -- references emotion_taxonomy.label_id
  emotion_taxonomy_version TEXT NOT NULL,    -- "1.0", "1.1", ... — pins label semantics
  intensity               INTEGER,           -- nullable for "implicit" UX (D6 hybrid)
                          -- if non-null: 1..5
  -- Time
  logged_at               INTEGER NOT NULL,  -- felt time, UTC ms; CAN be backdated by user
  logged_at_tz            TEXT NOT NULL,     -- IANA tz at logging moment, e.g. "America/Los_Angeles"

  -- Context
  journal_note            TEXT,              -- nullable; stored encrypted-at-rest by SQLCipher
                                             -- (see §11 for server-side encryption)

  -- Lifecycle / sync
  created_at              INTEGER NOT NULL,
  updated_at              INTEGER NOT NULL,  -- LWW key
  deleted_at              INTEGER,           -- soft delete
  schema_version          INTEGER NOT NULL,
  device_id               TEXT NOT NULL,

  FOREIGN KEY (user_id)   REFERENCES users(id) ON UPDATE CASCADE,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON UPDATE CASCADE
) STRICT;

-- Hot path: render Today / Insights for current user
CREATE INDEX idx_logs_user_logged
  ON emotion_logs(user_id, logged_at DESC)
  WHERE deleted_at IS NULL;

-- Sync cursor scans (only used when sync is enabled)
CREATE INDEX idx_logs_user_updated
  ON emotion_logs(user_id, updated_at);

-- Tombstone purge job
CREATE INDEX idx_logs_deleted
  ON emotion_logs(deleted_at)
  WHERE deleted_at IS NOT NULL;

-- Insights aggregations: counts per quadrant per day
-- (no separate index — the user_logged composite serves these via filter scan
--  at v1 row counts; revisit when row count crosses ~50k per user)
```

### 4.4 Tags & Junction

```sql
CREATE TABLE context_tags (
  id              TEXT PRIMARY KEY,           -- UUID v7
  user_id         TEXT NOT NULL,              -- '__system__' for seed rows; else user's id
                                              -- (NOT a FK: '__system__' would orphan)
  label           TEXT NOT NULL,              -- e.g. "Work", "Family"
  origin          TEXT NOT NULL               -- 'system' | 'user'
                  CHECK (origin IN ('system','user')),
  sort_order      INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  device_id       TEXT NOT NULL               -- '__system__' for seed; else FK devices(id)
) STRICT;

-- Partial unique index: a deleted tag's label is re-usable. Re-adding "Work"
-- after deletion creates a new row (with a new id); the old tombstone lingers
-- until the 30-day purge.
CREATE UNIQUE INDEX uq_context_tags_user_label
  ON context_tags(user_id, label)
  WHERE deleted_at IS NULL;

CREATE TABLE emotion_log_context_tags (
  id              TEXT PRIMARY KEY,           -- UUID v7 (replicable)
  log_id          TEXT NOT NULL,              -- FK emotion_logs(id)
  tag_id          TEXT NOT NULL,              -- FK context_tags(id)
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  device_id       TEXT NOT NULL,
  FOREIGN KEY (log_id) REFERENCES emotion_logs(id) ON UPDATE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES context_tags(id) ON UPDATE CASCADE
) STRICT;

-- Partial unique: removing then re-adding a tag-on-log creates a new junction row
CREATE UNIQUE INDEX uq_log_tags_log_tag
  ON emotion_log_context_tags(log_id, tag_id)
  WHERE deleted_at IS NULL;
CREATE INDEX idx_log_tags_log ON emotion_log_context_tags(log_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_log_tags_tag ON emotion_log_context_tags(tag_id) WHERE deleted_at IS NULL;
```

### 4.5 Edit Trail (Opt-in)

```sql
CREATE TABLE emotion_log_edits (
  id                  TEXT PRIMARY KEY,       -- UUID v7
  log_id              TEXT NOT NULL,          -- FK emotion_logs(id)
  user_id             TEXT NOT NULL,
  -- Snapshot of the prior values (before the edit that created this row)
  prior_valence       INTEGER NOT NULL,
  prior_arousal       INTEGER NOT NULL,
  prior_emotion_label_id TEXT NOT NULL,
  prior_emotion_taxonomy_version TEXT NOT NULL,
  prior_intensity     INTEGER,
  prior_logged_at     INTEGER NOT NULL,
  prior_journal_note  TEXT,                   -- nullable; encrypted same as live
  -- Bookkeeping (no updated_at — edit rows are immutable)
  created_at          INTEGER NOT NULL,
  deleted_at          INTEGER,                -- only used to satisfy GDPR delete cascades
  schema_version      INTEGER NOT NULL,
  device_id           TEXT NOT NULL,
  FOREIGN KEY (log_id) REFERENCES emotion_logs(id) ON UPDATE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON UPDATE CASCADE
) STRICT;

CREATE INDEX idx_log_edits_log ON emotion_log_edits(log_id);
```

The edit trail is **only written** when the `app_settings` key
`audit_trail_enabled` is `true`. Default in v1: **false** (per PRD
review §"Story 8's audit trail is hidden data collection"). User opts
in via Settings; opt-out wipes existing edit rows synchronously.

### 4.6 Reminders (Local-only)

```sql
CREATE TABLE reminder_schedules (
  id              TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  enabled         INTEGER NOT NULL DEFAULT 1, -- 0 | 1
  -- A schedule is a set of (day_of_week, time_local, jitter_minutes) tuples
  -- stored as a JSON blob to avoid N×M tables; reminder count is small (≤ ~20)
  rules_json      TEXT NOT NULL,
  quiet_hours_json TEXT NOT NULL,             -- {start_local: "22:00", end_local: "07:00"}
  -- Lifecycle (NOT replicated; schedules are per-device)
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  -- no device_id: this row IS device-local
  FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE
) STRICT;

CREATE INDEX idx_reminders_user ON reminder_schedules(user_id) WHERE deleted_at IS NULL;
```

Reminders **never replicate** (per PRD: "Local-scheduled only v1"). Storing
them in the DB rather than `app_settings` keeps schema-evolution discipline
consistent and lets future server-side reminders (post v1) ship without a
data move.

### 4.7 Coping Activity Favorites

```sql
CREATE TABLE coping_activity_favorites (
  id              TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  activity_id     TEXT NOT NULL,              -- references bundled activities JSON
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  deleted_at      INTEGER,
  schema_version  INTEGER NOT NULL,
  device_id       TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON UPDATE CASCADE
) STRICT;

-- Partial unique: un-favoriting then re-favoriting creates a new live row
CREATE UNIQUE INDEX uq_coping_favs_user_activity
  ON coping_activity_favorites(user_id, activity_id)
  WHERE deleted_at IS NULL;
```

### 4.8 Sync Cursors (only used when sync is enabled)

```sql
CREATE TABLE sync_cursors (
  entity              TEXT PRIMARY KEY,        -- 'emotion_logs', 'context_tags', etc.
  last_pulled_updated_at INTEGER NOT NULL DEFAULT 0,  -- max updated_at seen from server
  last_push_at        INTEGER,                 -- when we last sent local changes
  last_error          TEXT,                    -- nullable; surfaced in Settings → Sync state
  updated_at          INTEGER NOT NULL
) STRICT;
```

### 4.9 Full-text Search (Phase 4 — Journal)

When the Journal feature ships, add a contentless FTS5 virtual table.
`contentless` keeps the FTS index small and prevents SQLite from
storing a *second* copy of journal text outside SQLCipher's
encryption page boundary.

```sql
CREATE VIRTUAL TABLE journal_fts USING fts5(
  journal_note,
  content='',                                  -- contentless: rowid-based join to emotion_logs
  tokenize='unicode61 remove_diacritics 2'
);

-- Triggers (added with the journal feature) keep journal_fts in sync with
-- emotion_logs. Insert/update/delete on emotion_logs.journal_note → mirror
-- write into journal_fts (rowid = emotion_logs.id hashed to int64).
-- Detail intentionally omitted here; specified in the Phase 4 implementation bead.
```

---

## 5. Server Postgres Schema (DDL)

The server schema mirrors the client and adds identity, sync, and
deletion-queue infrastructure. Even if **sync is cut from v1** (Tier-1
recommendation), the server schema is documented here so the v1.x
addition is a deploy, not a redesign.

```sql
-- Identity
CREATE TABLE users (
  id              UUID PRIMARY KEY,                   -- echoes client id when account is linked
  external_id     TEXT UNIQUE NOT NULL,               -- Apple sub or Google sub
  external_provider TEXT NOT NULL CHECK (external_provider IN ('apple','google')),
  display_name    TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ,
  schema_version  INTEGER NOT NULL
);

CREATE TABLE devices (
  id              UUID PRIMARY KEY,                   -- echoes client id
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  platform        TEXT NOT NULL CHECK (platform IN ('ios','android')),
  os_version      TEXT NOT NULL,
  app_version     TEXT NOT NULL,
  device_label    TEXT,
  installed_at    TIMESTAMPTZ NOT NULL,
  last_active_at  TIMESTAMPTZ NOT NULL,
  push_token      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ,
  schema_version  INTEGER NOT NULL
);

CREATE INDEX idx_devices_user ON devices(user_id);

-- Emotion logs
CREATE TABLE emotion_logs (
  id                      UUID PRIMARY KEY,           -- client-generated UUID v7
  user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  valence                 SMALLINT NOT NULL CHECK (valence BETWEEN -50 AND 50),
  arousal                 SMALLINT NOT NULL CHECK (arousal BETWEEN -50 AND 50),
  emotion_label_id        TEXT NOT NULL,
  emotion_taxonomy_version TEXT NOT NULL,
  intensity               SMALLINT,
  logged_at               TIMESTAMPTZ NOT NULL,
  logged_at_tz            TEXT NOT NULL,
  -- Encrypted column: see §11 for envelope-encryption choice
  journal_note_ciphertext BYTEA,
  journal_note_nonce      BYTEA,
  journal_note_kek_id     TEXT,                       -- KMS key id used for the per-user envelope
  created_at              TIMESTAMPTZ NOT NULL,
  updated_at              TIMESTAMPTZ NOT NULL,
  deleted_at              TIMESTAMPTZ,
  schema_version          INTEGER NOT NULL,
  device_id               UUID NOT NULL REFERENCES devices(id)
);

-- Sync cursor lookups: pull rows updated since a given timestamp
CREATE INDEX idx_logs_user_updated ON emotion_logs(user_id, updated_at);
-- Tombstone hard-purge job
CREATE INDEX idx_logs_deleted_at ON emotion_logs(deleted_at) WHERE deleted_at IS NOT NULL;

-- Tags + junction
CREATE TABLE context_tags (
  id              UUID PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label           TEXT NOT NULL,
  origin          TEXT NOT NULL CHECK (origin IN ('system','user')),
  sort_order      INTEGER NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL,
  deleted_at      TIMESTAMPTZ,
  schema_version  INTEGER NOT NULL,
  device_id       UUID REFERENCES devices(id)        -- NULL for system seeds
);

CREATE TABLE emotion_log_context_tags (
  id              UUID PRIMARY KEY,
  log_id          UUID NOT NULL REFERENCES emotion_logs(id) ON DELETE CASCADE,
  tag_id          UUID NOT NULL REFERENCES context_tags(id) ON DELETE CASCADE,
  created_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL,
  deleted_at      TIMESTAMPTZ,
  schema_version  INTEGER NOT NULL,
  device_id       UUID NOT NULL REFERENCES devices(id),
  UNIQUE (log_id, tag_id)
);

-- Edit trail (opt-in)
CREATE TABLE emotion_log_edits (
  id                  UUID PRIMARY KEY,
  log_id              UUID NOT NULL REFERENCES emotion_logs(id) ON DELETE CASCADE,
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  prior_valence       SMALLINT NOT NULL,
  prior_arousal       SMALLINT NOT NULL,
  prior_emotion_label_id TEXT NOT NULL,
  prior_emotion_taxonomy_version TEXT NOT NULL,
  prior_intensity     SMALLINT,
  prior_logged_at     TIMESTAMPTZ NOT NULL,
  prior_journal_note_ciphertext BYTEA,
  prior_journal_note_nonce      BYTEA,
  prior_journal_note_kek_id     TEXT,
  created_at          TIMESTAMPTZ NOT NULL,
  deleted_at          TIMESTAMPTZ,
  schema_version      INTEGER NOT NULL,
  device_id           UUID REFERENCES devices(id)
);

-- Coping activity favorites
CREATE TABLE coping_activity_favorites (
  id              UUID PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  activity_id     TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL,
  deleted_at      TIMESTAMPTZ,
  schema_version  INTEGER NOT NULL,
  device_id       UUID REFERENCES devices(id),
  UNIQUE (user_id, activity_id)
);

-- Deletion queue (GDPR Art. 17 enforcement)
CREATE TABLE deletion_jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL,                      -- not a FK: user row may already be gone
  requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  hard_delete_deadline TIMESTAMPTZ NOT NULL,          -- requested_at + 30 days
  status          TEXT NOT NULL CHECK (status IN ('pending','running','complete','failed')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,
  completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_deletion_jobs_pending ON deletion_jobs(status, hard_delete_deadline)
  WHERE status IN ('pending','running');

-- Schema versions
CREATE TABLE schema_versions (
  version       INTEGER PRIMARY KEY,
  applied_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  description   TEXT NOT NULL
);
```

Notes:

- **`ON DELETE CASCADE`** on the `users(id)` FK is intentional: GDPR
  Art. 17 hard delete is a SQL `DELETE FROM users WHERE id = $1`
  followed by the queue marking complete. The cascade ensures no
  orphaned rows survive in `emotion_logs`, `emotion_log_edits`,
  `context_tags`, `coping_activity_favorites`, `devices`, or
  `emotion_log_context_tags`.
- **`UUID` columns store binary 16-byte UUIDs**; client UUID v7 strings
  are parsed at the API edge.
- **`TIMESTAMPTZ`** chosen for server time columns to make timezone
  errors loud at write time. The wire format is still ISO-8601 UTC; the
  client's millisecond integers are parsed at the edge.
- **`journal_note_*` columns** carry ciphertext, nonce, and KEK id for
  envelope encryption (§11). No plaintext column exists, even for
  admin/debug.

---

## 6. Mood Meter Encoding (D6, Open Q1 reconciliation)

PRD Open Q1 leaves the Mood Meter UX undecided: 10×10 grid (cell ==
emotion) vs. quadrant + emotion + intensity vs. hybrid. The schema
**does not pick a winner.** Instead, every emotion log carries:

- `valence` ∈ [−50, +50] — pleasantness axis
- `arousal` ∈ [−50, +50] — energy axis
- `emotion_label_id` — opaque label key (e.g. `"frustrated"`)
- `emotion_taxonomy_version` — pins the meaning of the label key
- `intensity` ∈ {1..5} or `NULL` — explicit intensity, or implicit if
  the cell encodes it

Mapping rules:

| UX choice (Open Q1) | How the row is populated |
|---|---|
| **(a) 10×10 grid, cell-as-emotion** | `valence` = cell column center (e.g. `-45..+45` in steps of 10), `arousal` = cell row center, `emotion_label_id` = the label of that cell, `intensity = NULL` (the cell encodes intensity) |
| **(b) Quadrant + label + 1..5 intensity** | `valence` = sign of pleasantness (`+25` or `-25`), `arousal` = sign of energy, `emotion_label_id` = chosen label, `intensity` = 1..5 |
| **(c) Hybrid** | Cell pick stamps `(valence, arousal, emotion_label_id)`; an optional intensity slider stamps `intensity` |

This decoupling means the Phase 1 UX can ship one model, the Phase 1.x
UX can iterate to another, and **no migration of existing log rows is
required** — only the *interpretation* in queries / Insights changes.
Insights queries that aggregate by quadrant use `sign(valence) ×
sign(arousal)`; queries that aggregate by label use
`emotion_label_id`; queries that bucket by intensity use a fallback
chain `COALESCE(intensity, abs(valence) + abs(arousal))`.

### Emotion taxonomy versioning

Stored as a **bundled JSON asset** plus an in-DB lookup that's
populated from the asset on app start:

```json
{
  "taxonomy_version": "1.0",
  "labels": [
    {"id": "frustrated", "display_en": "Frustrated", "default_valence": -30, "default_arousal": +30, "quadrant": "high_energy_unpleasant"},
    {"id": "serene",     "display_en": "Serene",     "default_valence": +35, "default_arousal": -25, "quadrant": "low_energy_pleasant"},
    ...
  ],
  "quadrants": [
    {"id": "high_energy_unpleasant", "display_en": "High Energy / Unpleasant", "color_hex": "#E94E1B"},
    ...
  ]
}
```

Each `emotion_logs` row carries the taxonomy version it was written
against. If the taxonomy changes (new labels, renamed labels, removed
labels), historical rows still resolve via the bundled JSON for older
versions, which **must be retained in the bundle** — at most a few KB
each.

This satisfies the PRD review's "Emotion-taxonomy versioning" gap.

---

## 7. Soft Deletes & Hard-Delete Lifecycle (D3)

### Soft delete

A delete is a write of `deleted_at = now()` and `updated_at = now()`
on the row, plus its dependent rows where applicable:

```sql
-- Logical delete of a single emotion log
UPDATE emotion_logs
SET deleted_at = ?, updated_at = ?, schema_version = ?, device_id = ?
WHERE id = ? AND deleted_at IS NULL;

UPDATE emotion_log_context_tags
SET deleted_at = ?, updated_at = ?, schema_version = ?, device_id = ?
WHERE log_id = ? AND deleted_at IS NULL;
```

The UI hides rows where `deleted_at IS NOT NULL`. Sync replicates
tombstones the same as live rows.

### Hard purge (client)

A periodic job (run on app foreground, throttled to ≤ once per day)
hard-deletes:

- Rows where `deleted_at IS NOT NULL AND deleted_at < now() - 30 days`
  (tombstone grace period — matches GDPR Art. 17 deadline)

This bounds local DB growth from accumulated tombstones and prevents
"deleted" data from lingering on the device past the policy promise.

### Hard purge (server)

A BullMQ scheduled job runs every hour:

1. Selects rows from `deletion_jobs` where `status = 'pending' AND
   hard_delete_deadline <= NOW()`.
2. For each, executes `DELETE FROM users WHERE id = $1` (cascades).
3. Marks the job `complete` with `completed_at`.
4. Logs (audit log; not journal text) the deletion completion.

The `deletion_jobs` table itself is **never deleted** — it is the
GDPR audit record that the deletion happened. It contains no PII
(only the user's UUID, which has no inherent meaning post-delete).

### GDPR Article 17 (right to erasure)

Triggered by the user via Settings → Account → Delete Account, or
post-hoc via the support workflow:

1. **Immediately:** mark the user's row `deleted_at = now()` (server),
   wipe local SQLite contents (client: drop and recreate the DB),
   revoke active session tokens.
2. **Queue the hard-delete:** enqueue a `deletion_jobs` row with
   `hard_delete_deadline = now() + 30 days`. The grace period exists
   to absorb cross-region replication lag and to give support a
   window to reverse a mistaken request (the user can re-auth within
   30 days and the row is marked `cancelled`).
3. **At deadline:** the BullMQ job hard-deletes (cascades).

The 30-day deadline matches the PRD review's "≤ 30 days" GDPR
constraint and is also a defensible support window.

---

## 8. Last-Write-Wins Conflict Resolution (D2)

Conflict resolution is a **single deterministic rule**: the row with
the larger `(updated_at, device_id)` tuple wins. The server applies
this rule on receipt of every push; the client applies the same rule
on every pull. Both sides reach the same answer regardless of arrival
order.

### The rule

For two candidate row-states A and B with the same `id`:

```
A wins iff (A.updated_at, A.device_id) > (B.updated_at, B.device_id)
where ms timestamps are numeric and device_id is lexicographic.
```

Tie on `(updated_at, device_id)` means the same write — keep either.

### Edit-vs-delete precedence

**Whichever has the larger `updated_at` wins** — same rule. A delete
*is* an update of `deleted_at`. Concretely:

| Scenario | Result |
|---|---|
| Device A edits at t=100; device B deletes at t=110 | Delete wins (B's `updated_at = 110 > 100`). |
| Device A deletes at t=100; device B edits at t=110 | **Edit wins, but** the row's `deleted_at` is overwritten to NULL by the edit (the edit was made on a row B believed live). |
| Same-ms tie | `device_id` lex order tie-break. |

This is intentional: "last write wins" applies to the *intent* of the
writer, including the intent to revive a deleted row. If the product
later wants "delete is sticky" (a death certificate), introduce a
`tombstoned_at` column that, once non-null, blocks further mutation —
this is an additive migration. We deliberately do not introduce it in
v1; the product behavior should fall out of user testing.

### Free-text (journal_note) merge strategy

**LWW entirely.** No CRDT, no diff merge. If two devices edit the
journal text simultaneously, one edit's text replaces the other.
Acceptance: this is acceptable for v1 because:

- The "feeling logged 30 seconds apart" case is rare in single-user
  multi-device usage.
- The optional **edit trail** (§4.5, opt-in) preserves the dropped
  text on the losing-side device until the next sync, at which point
  the loser is replaced. If the user has the edit trail enabled, the
  prior text appears in their history; if not, it is silently
  overwritten — which is the explicit cost of the privacy posture
  ("no hidden audit"). PRD review §"Audit-trail replication semantics"
  resolved.

If product later wants per-field merge, the upgrade path is to add
per-field `*_updated_at` columns and per-field LWW (additive
migration). v1 keeps a single `updated_at` for simplicity.

### Skew tolerance (server-side validation)

The server **clamps absurd device clocks** rather than trust them
blindly:

| Condition on incoming row | Server action |
|---|---|
| `updated_at > now() + 5 min` | Reject the row (`409 ClockSkew`). Client retries after correcting clock. |
| `updated_at < now() - 365 days` AND row didn't already exist | Accept but log anomaly. |
| Anything else | Accept. |

This bounds the worst-case clock-skew attack ("write a row from year
2999 so it always wins") without coupling sync to NTP availability on
the device. The 5-minute future window is large enough to absorb
legitimate skew (e.g., DST transitions on misconfigured devices) and
small enough to bound the damage.

### Hybrid Logical Clock — explicitly *not* in v1

PRD Open Q9 mentions HLC. We decline:

- HLC adds complexity (per-row clock tracking, correct merging on
  every read) and v1's single-user-multi-device traffic is too low
  to justify it.
- The skew-clamped LWW described above gives equivalent end-state
  convergence for the workload.
- HLC is reachable as an additive migration if traffic patterns later
  demand it: each row gains `hlc_l`, `hlc_c`, `hlc_node`; old rows
  are interpreted as `(updated_at, 0, device_id)`.

### Tag junction merges

`emotion_log_context_tags` carries `(log_id, tag_id)` UNIQUE. A user
adding the same tag on two devices generates two rows with different
`id`s but the same `(log_id, tag_id)` tuple. Server-side
`INSERT ... ON CONFLICT (log_id, tag_id) DO UPDATE` collapses them
to one row, taking the LWW winner. Client merge does the same.

---

## 9. Schema Migration Strategy (D5)

### Numbered, monotonic, forward-only

Migrations are numbered files: `001_initial.sql`, `002_add_intensity.sql`,
... checked into the client repo. Bundled with the app binary.

At app start:

```
SELECT MAX(version) FROM schema_versions;  -- e.g., 4
For each migration N where N > current AND N <= bundled_max:
  BEGIN;
  apply migration N;
  INSERT INTO schema_versions (version, applied_at, description, app_version) VALUES (...);
  COMMIT;
```

Each migration is wrapped in a transaction. A crash mid-migration
leaves the DB in the prior version (transaction rolls back). The app
re-attempts on next launch.

### No down migrations

Forward-only. SQLite has no DDL transactions for some operations
(`ALTER TABLE DROP COLUMN` is supported in 3.35+ but DROP TABLE inside
multi-statement migrations needs care). A botched migration is
recovered by:

1. Bundling a fixed `00X_repair.sql` migration in the next app version.
2. Pushing a hot-update.

There is no user-facing rollback. The `schema_version` column on each
row makes a *future* version aware of "this row was written by an
older format" so it can read it correctly even after the migration.

### Migration tests with fixture DBs (mandatory CI gate)

For each migration `N`:

1. Take a fixture DB at version `N-1` (curated representative data
   plus stress data: 10k logs, all-NULL fields, max-length journal
   notes, multi-device device_id mix).
2. Apply migration `N`.
3. Assert: row count preserved, no orphaned FKs, no NULL violations,
   all indexes valid (`PRAGMA integrity_check`).

Fixture DBs are checked in as binary blobs (small — ≤ 100 KB each
encrypted). New fixtures are minted from the fixture-builder script
when a new migration lands. PRD review §"Schema migration framework
on device" gap closed.

### Schema evolution patterns

| Change | Migration shape | Notes |
|---|---|---|
| **Add NULL-able column** | `ALTER TABLE x ADD COLUMN c TYPE` | Trivially compatible. New rows write the column; old code reads NULL gracefully. |
| **Add NOT NULL column** | Add NULL-able + backfill in same migration + (optional) future tightening | SQLite can't add NOT NULL with no default in one shot; use a default or backfill in the same migration. |
| **Rename column** | Add new + copy + drop old + reference-update | Three migrations to stay safe across in-flight clients (see "Multi-version coexistence"). |
| **Change column type** | Add new typed column + backfill + drop old | Same. |
| **Drop column** | Stop writing it (one app version) → drop the column (next app version) | Multi-version coexistence: never drop a column that an in-flight client still reads. |
| **Drop table** | Same: stop writing it → drop the table next version | Same. |
| **Reshape data (denormalize, normalize)** | Add new tables/columns + backfill + dual-write + cutover read + drop old | Multi-stage; each stage is a separately-shippable migration. |

### Multi-version coexistence (offline app reality)

Users can stay on an old app version for months. Migrations must
**survive a user upgrading directly from v1.0 to v1.7** without
seeing any of the intermediate versions live data in their DB. This
is the default if migrations are pure (no external network calls)
and idempotent on re-run.

### Server-side migrations

Standard tool: **node-pg-migrate** (or Knex). Same forward-only
discipline. Server is single-version per deploy; multi-version
coexistence is not a server concern, but **rolling deploys** are: any
migration must be safe for the prior server version to read the
post-migration schema. Practical rules:

- Add columns and tables: compatible.
- Drop columns: ship one release that stops reading the column, then
  another that drops it.
- Rename columns: same (add+copy+stop reading old+drop old over four
  releases). Long-tail problem worth being explicit about.

### Schema version advertisement on sync

Every sync request includes the client's `schema_version` (highest
applied). The server returns its own `schema_version` and a hint in
the response if an upgrade is recommended. If the client is too old to
parse the server's response, it surfaces a forced-upgrade UX rather
than corrupting data.

---

## 10. Indexing & Query Patterns

### Client (SQLite)

Hot-path queries:

| Query | Index used |
|---|---|
| Today view: logs by user, ordered by `logged_at DESC` | `idx_logs_user_logged` (partial: `WHERE deleted_at IS NULL`) |
| Insights heatmap: logs by user across a date range | `idx_logs_user_logged` |
| Journal search: FTS5 on `journal_note` | `journal_fts` virtual table |
| Sync push (only when sync is enabled): rows changed since last cursor | `idx_logs_user_updated` |
| Tombstone purge | `idx_logs_deleted` (partial: `WHERE deleted_at IS NOT NULL`) |

Index bloat:

- All sync-only indexes (`*_user_updated`) are included even when sync
  is disabled. Their cost on insert (~10% per index) is negligible at
  v1 row counts (~1825 rows after 5 years of daily logs); their
  presence makes enabling sync a config flip, not a schema change.
- Partial indexes on `deleted_at` keep tombstones from inflating the
  hot-path indexes.

Estimated storage at scale (single user, 5 years of daily logs):

- ~1825 rows in `emotion_logs` × ~500 bytes/row (with a typical
  journal note) = ~1 MB raw
- Indexes: ~250 KB
- Tombstones (assuming ~5% deletion) before 30-day purge: ~50 KB
- **Total: well under 2 MB.** SQLite scales to millions of rows on
  mobile; v1 is nowhere near a bottleneck.

### Server (Postgres)

| Query | Index used |
|---|---|
| Sync pull: `WHERE user_id = $1 AND updated_at > $2` | `idx_logs_user_updated` |
| Hard-purge job: `WHERE deleted_at < $1` | `idx_logs_deleted_at` |
| Account deletion: `DELETE FROM users WHERE id = $1` | PK |
| Identity lookup: `WHERE external_id = $1` | UNIQUE on `users.external_id` |

At scale (assume 100k users × 1825 logs each ≈ 180M rows):

- `emotion_logs` table: ~180 GB raw. Postgres handles this with
  partitioning by `user_id` hash (16 partitions) — to be added when
  the row count reaches ~50M, not in v1. Single-table is fine until
  then.
- `idx_logs_user_updated`: ~9 GB.
- Sync queries are point-query-then-range-scan within a single user;
  latency is bounded by per-user log count (~bytes), not by total
  row count.

---

## 11. Encryption Strategy (D4)

### Client (at-rest)

**SQLCipher** wraps the entire SQLite database file. The encryption
key is derived from a device-side secret stored in **Expo SecureStore**
(iOS Keychain / Android Keystore). On first launch the app:

1. Generates a random 256-bit secret.
2. Stores it in SecureStore with `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`
   (iOS — prevents iCloud Keychain sync) and equivalent flags on Android.
3. Derives the SQLCipher key via PBKDF2 (SQLCipher's default).
4. Opens the DB.

**Key loss policy:** the key is **device-only**. Loss of the device or
the keystore means loss of the local DB. The user-facing UX must say
this plainly during onboarding (PRD Tier-2 Q6 sub-question). When sync
is enabled, the server is the recovery path; in account-less local
mode, there is no recovery. *We deliberately do not implement
user-passphrase escrow in v1* — it adds support burden and a
forgotten-passphrase failure class.

### iOS / Android backup exclusion

Per PRD review §"Lock-screen notification leakage and OS-level backup
leakage": SQLite file location must be excluded from automatic
backups.

- **iOS:** set `NSURLIsExcludedFromBackupKey` on the DB file URL at
  open time. CI test asserts the exclusion bit.
- **Android:** declare the DB path in `data_extraction_rules.xml`
  with `<exclude .../>` for both auto-backup and device-transfer.
  CI test asserts the manifest contains the exclusion.

### Server (at-rest)

Journal text is the only PRD-classified-sensitive payload that must
be encrypted at the column level. The PRD draft says "row-level
encryption for `journal_note` server-side"; Postgres has no native
row-level encryption (the PRD review correctly flags this as an
under-specified term). We pick:

**Per-user envelope encryption with KMS-managed KEKs.**

- Each user has a Data Encryption Key (DEK), generated at sign-up,
  wrapped by a Key Encryption Key (KEK) held in AWS KMS / GCP KMS /
  equivalent. The wrapped DEK is stored on the user row; the KEK
  never leaves KMS.
- On write: the API server fetches the wrapped DEK, asks KMS to
  unwrap it (cached for ≤ 5 min in process), encrypts the plaintext
  with `AES-256-GCM` using a fresh nonce, stores `(ciphertext,
  nonce, kek_id)` in the row.
- On read: same in reverse.
- `kek_id` lets us rotate KEKs by re-wrapping DEKs (cheap) without
  re-encrypting rows (expensive).

This is materially stronger than per-row keys (each user is a
crypto-bounded blast radius) and materially cheaper than per-row
KEKs (the KMS call cost is once per user per cache window, not once
per row). PRD review §"Row-level encryption needs a real definition"
gap closed.

### In-transit

TLS 1.2+ everywhere. Client pins the server cert in app store builds
(via `react-native-ssl-pinning` or equivalent); pin rotation
ships in app updates with overlapping validity. PRD review notes
this; not a schema concern but listed for completeness.

### What is *not* encrypted at the column level on the server

Most columns: `valence`, `arousal`, `emotion_label_id`, `intensity`,
`logged_at`, timestamps. Rationale:

- These fields are necessary for sync cursor queries and aggregates.
  Encrypted columns can't be range-scanned without server-side
  decryption per row, defeating sync efficiency.
- They are sensitive but not as load-bearing as the free-text journal:
  an exfiltration of just (valence, arousal, label) without journal
  is a partial-but-real privacy harm — but encrypting them all forces
  the privacy threat model to assume the database file itself is
  hostile, which moves the problem to disk encryption + access
  controls (correct posture for an Art. 9 workload).

The trade-off is documented and revisitable — if the threat model
later requires per-column encryption everywhere, the schema migration
is `ADD COLUMN x_ciphertext, BACKFILL, DROP COLUMN x` per column;
schema-version-stamped rows make this clean.

---

## 12. Sync Engine (v1.x or v2)

This section is **conditional on Tier-1 Q3 = "sync in v1" or v1.x**.
The schema and conflict-resolution rules above are sufficient; the
engine is an implementation of them.

### Wire protocol (REST)

```
GET  /api/v1/sync/{entity}?since={updated_at_ms}&limit=500
     -> 200 { rows: [...], server_max_updated_at: 1730000000123 }

POST /api/v1/sync/{entity}
     body: { rows: [...] }
     -> 200 { accepted: 487, rejected: [{id, reason}] }
```

Per-entity calls (rather than a single bulk endpoint) keep the
request size bounded and let independent entity types fail
independently.

### Pull algorithm

```
cursor = sync_cursors[entity].last_pulled_updated_at
loop:
  resp = GET /sync/entity?since=cursor
  for row in resp.rows:
    apply LWW vs. local row
  cursor = max(cursor, resp.server_max_updated_at)
  sync_cursors[entity] = cursor
  if len(resp.rows) < 500: break  // drained
```

### Push algorithm

```
batch = SELECT * FROM entity WHERE updated_at > sync_cursors[entity].last_push_at LIMIT 500
POST /sync/entity { rows: batch }
sync_cursors[entity].last_push_at = max(batch.updated_at)
for each rejection: surface in Settings → Sync state, retry with backoff
```

### Conflict resolution

Server-side: on POST, for each incoming row, fetch current row,
compare `(updated_at, device_id)`, take winner. Atomic via Postgres
`INSERT ... ON CONFLICT (id) DO UPDATE WHERE
EXCLUDED.updated_at > emotion_logs.updated_at OR
(EXCLUDED.updated_at = emotion_logs.updated_at AND
EXCLUDED.device_id > emotion_logs.device_id)`.

Client-side: same rule on apply.

### Test matrix (CI gate, owned by sync engine bead)

| Scenario | Expected outcome |
|---|---|
| Two devices write same row, different times | Later `updated_at` wins on both. |
| Two devices write same row, same `updated_at` | Higher lex `device_id` wins on both. |
| Device A deletes; device B edits offline; reconnect | Edit wins, `deleted_at` cleared. |
| Device A edits; device B deletes offline; reconnect | Delete wins, edit's text is in trail (if enabled). |
| Tag added on two devices simultaneously | One row in junction table; LWW. |
| Skewed device clock: row with `updated_at = year 2999` | Server rejects; client retries after clock fix. |
| Device disconnected for 90 days; ~500 new rows on each side | Convergence in ≤ 2 sync cycles. |

---

## 13. Account-less Local Mode (PRD Constraint)

PRD: "account-less local mode also supported." Schema implications:

- The client maintains a synthetic `users` row with
  `account_state = 'local_only'`, `external_id = NULL`, and a
  self-generated UUID v7 `id` (call it `local_id`).
- All foreign keys reference `local_id`.
- **`local_id` is the canonical user id forever** — even after the
  user signs in with Apple/Google. The link flow does **not** renumber
  the id; it adopts the local id on the server side.

Linking flow (user picks Sign in with Apple / Google):

1. Client obtains OAuth identity token.
2. Client calls `POST /auth/link` with the identity token *and* its
   `local_id`.
3. Server:
   - If no row exists for the OAuth `external_id`: creates a new
     `users` row using the client-supplied `local_id` as the primary
     key and the OAuth sub as `external_id`.
   - If a row exists for the OAuth `external_id` (e.g., the user has
     a different device already linked): the server's existing
     `users.id` wins. The client receives the canonical id and
     performs a *one-time* migration of its local FKs (cascade-update
     via SQL, in a single transaction; see below). This case is rare
     but real — only triggered when a user has previously signed in
     on another device.
4. Client sets `account_state = 'linked_apple'` or `'linked_google'`,
   stores `external_id`, enables sync, replicates pending local rows
   up to the server.

This sidesteps the FK-renumber as the *common* case. The rare
"server already has a row" case is handled by the same renumber,
backed by `PRAGMA foreign_keys = ON` and **explicit
`ON UPDATE CASCADE`** on every FK that references `users(id)`. (See
§4: each FK declaration includes `ON UPDATE CASCADE`. SQLite does
*not* cascade UPDATE by default; declaration is mandatory.)

A single transaction wraps the renumber. On failure, the rollback
leaves the user in local-only mode with no orphaning. On retry, the
sequence is idempotent (the local_id is still the local_id; the
server will return the same canonical id).

Choosing "use locally without account" is a permanent decision until
the user actively signs in. The PRD review's Tier-2 Q11 (account
recovery policy) drives the in-app disclosure but does not affect the
schema.

---

## 14. Edit-Past-Log Audit Trail (D8, opt-in)

PRD Story 8 states the app can keep an audit trail of edits "not
exposed in the UI by default." Scope review §3 flags this as hidden
data collection — a subpoena / breach / "show me the history"
liability. We resolve by making the audit trail **opt-in** via
`app_settings.audit_trail_enabled`:

- Default: **off**. Edits overwrite in place; no `emotion_log_edits`
  rows are written.
- User toggles on (Settings → Privacy → Edit history): future edits
  write a snapshot to `emotion_log_edits`.
- User toggles off: existing `emotion_log_edits` rows are
  *immediately and synchronously hard-deleted* (not soft-deleted).

The setting is a per-device boolean (not replicated). On sign-in to a
new device, the user starts with the default (off) and must opt in
again. This intentionally biases toward "fewer audit rows in
existence," consistent with the privacy posture.

If the audit trail is enabled, edit rows replicate via sync and
appear in the GDPR export; if disabled, neither place sees them.

---

## 15. Crisis Resources Storage (D10, PRD Tier-1 Q4 "static link")

Per PRD review recommendation, v1 ships a **static "Get Support"
link surface** with no automated detection. Storage:

- **Bundled JSON asset** in the app binary: `assets/crisis_resources.json`
- Schema:

```json
{
  "version": "1.0",
  "default_locale": "en-US",
  "resources": {
    "en-US": [
      {
        "kind": "hotline",
        "name": "988 Suicide & Crisis Lifeline",
        "phone": "988",
        "sms": "988",
        "url": "https://988lifeline.org",
        "available": "24/7",
        "owner": "SAMHSA"
      },
      ...
    ],
    "en-GB": [...],
    ...
  }
}
```

- No DB rows in v1. The Settings → Get Support screen reads from the
  bundle.
- v1.x: add a remote config fetch (signed JSON, ETag-cached) that
  overrides the bundle. Schema for the remote-config side is added
  then; v1 schema is unaffected.

This sidesteps the need for a `crisis_resources` DB table in v1
entirely. PRD Open Q5–7 (heuristics, vetting, free-text scanning) are
**out-of-scope for v1 storage** under the recommended cut.

---

## 16. Reference Data Seeding

System seed rows are inserted at **app first-launch** (after running
all migrations) and verified at every launch:

| Table | Seed contents | Refresh policy |
|---|---|---|
| `context_tags` | `Work, Family, Health, Social, Money, Relationship, Other` (7 system rows, `origin='system'`) | If a new app version adds a tag, insert with `ON CONFLICT (user_id, label) DO NOTHING` |
| `emotion_taxonomy` (read-only, JSON) | Bundled per `emotion_taxonomy_version`; older versions retained | New labels = new version; never mutate existing labels (would silently change historical row meanings) |
| `crisis_resources` (read-only, JSON) | Bundled per locale | App version bump = bundle update |

System-seed `context_tags` use `user_id = '__system__'` and
`device_id = '__system__'` as sentinel values. They never sync (the
server has its own seed of the same labels). User-created tags
(`origin = 'user'`) sync normally.

---

## 17. GDPR Export (PRD Constraint)

Every row in every table is exportable. The GDPR export endpoint
returns a JSON document:

```json
{
  "export_version": "1.0",
  "exported_at": "2026-05-02T15:00:00Z",
  "user": { ... },
  "devices": [ ... ],
  "emotion_logs": [
    { "id": "...", "valence": -30, "arousal": 25,
      "emotion_label_id": "frustrated", "emotion_taxonomy_version": "1.0",
      "intensity": null, "logged_at": "2026-05-01T18:30:00Z",
      "logged_at_tz": "America/Los_Angeles",
      "journal_note": "decrypted plaintext here",
      "created_at": "...", "updated_at": "...", "deleted_at": null,
      "schema_version": 1, "device_id": "..."
    },
    ...
  ],
  "context_tags": [ ... ],
  "emotion_log_context_tags": [ ... ],
  "emotion_log_edits": [ ... ],   // included even when audit is off (would be empty array)
  "coping_activity_favorites": [ ... ],
  "reminder_schedules": [ ... ],   // local only — exported from device, not server
  "app_settings": [ ... ]
}
```

**The journal_note appears decrypted** in the export — the user is
the data subject and is entitled to plaintext.

Export generation is a BullMQ job server-side (heavy users have
~10k logs); the user receives a download link via email / Apple
Sign-in relay. The export package is itself encrypted (zip + AES
password emailed separately) per PRD review §"Apple Sensitive Health
Information specifics" defensibility.

CI test: the export round-trips — exporting a fixture user,
re-importing into a fresh DB, asserting bytes-equal modulo
`exported_at`.

---

## 18. Open Decisions / Dependencies on Other Beads

| # | Decision | Owner | Blocker for |
|---|---|---|---|
| O1 | Sync in v1 vs. v1.x (PRD Tier-1 Q3) | Product owner | Server schema deploy timing; otherwise no-op for client schema |
| O2 | Mood Meter UX (Open Q1: 10×10 / quadrant+intensity / hybrid) | UX leg (`hwf-6lx`) | UI implementation — schema accommodates all three (D6) |
| O3 | Multi-emotion logging (Open Q4) | UX leg | If yes: add `emotion_log_components` child table; current schema assumes one emotion per log |
| O4 | Photo attachments (Tier-2 Q8) | Product owner | If "yes in v1": add `photo_attachments` table now rather than later (cheaper migration) |
| O5 | Streaks (Tier-2 Q9) | Product owner | If "drop": no schema impact (streaks are derived). If "keep": no schema impact — streaks compute from `emotion_logs` |
| O6 | Audit trail default (D8) | Product + privacy owner | Recommended off; opt-in is the schema's only commitment |
| O7 | Encryption key escrow policy (PRD Tier-2 Q6 sub) | Security owner | Default no-escrow in v1; if "yes": add `users.kek_recovery_blob` |
| O8 | Sync schema version negotiation (multi-version coexistence) | Sync engine bead (post-Tier-1 Q3) | Only if sync in v1 |
| O9 | `context_tags` user-tag length / count cap | UX leg | Reasonable defaults: 30 chars, 50 tags per user |
| O10 | Locale list for `crisis_resources` bundle | Localization owner | Per-locale content; not a schema concern, but blocks store submission |

---

## 19. Verification & Testing (CI Gates)

Mandatory tests, owned by future implementation beads but specified here:

1. **Migration tests** (per §9): every migration applied to fixture DBs
   from each prior version; integrity check; row count and FK preservation.
2. **LWW conflict-resolution tests** (per §8): the test matrix above —
   pure-function tests on the resolver, plus integration tests against
   the SQLite/Postgres implementations.
3. **GDPR export round-trip** (per §17): export → re-import → bytes-equal.
4. **Encryption tests** (per §11): SQLCipher handle open/write/close;
   server envelope encryption with KMS mock; key rotation re-wraps DEKs
   without re-encrypting rows; `kek_id` tracks correctly per row.
5. **Backup-exclusion tests** (per §11): iOS `NSURLIsExcludedFromBackupKey`
   set; Android `data_extraction_rules.xml` excludes the DB path.
6. **No-egress test** (PRD review §"No-egress acceptance test"): an
   instrumented build performs every documented flow; CI fails on any
   unexpected outbound traffic.
7. **Schema-version regression**: changing a column type without
   bumping the schema version fails CI.
8. **Soft-delete cascade**: deleting an `emotion_log` soft-deletes its
   `emotion_log_context_tags`; deleting a `context_tag` soft-deletes
   its junction rows but does **not** delete the logs themselves.
9. **Hard-purge job**: tombstones older than 30 days are removed;
   newer tombstones survive.
10. **Account-deletion deadline**: GDPR `deletion_jobs` rows mature
    at exactly `requested_at + 30 days`; the BullMQ scheduler
    triggers the cascade; the audit row remains.
11. **Account-less → linked transition**: synthetic user's id is
    renumbered; FKs cascade in a single transaction; rollback on
    failure leaves user in local-only mode.

Each test is a separately-failing CI assertion (no compound green-only
results).

---

## 20. Summary of Departures from PRD Draft / Initial Spec

| Item | PRD draft / initial-spec | This design |
|---|---|---|
| `updated_at` field | Implied universal but not consistently in initial spec | Universal, mandatory, the LWW key |
| LWW timestamp | Initial spec: `logged_at` | `updated_at` (PRD Open Q9 confirms `logged_at` is wrong) |
| Mood Meter cell encoding | PRD: ambiguous (Open Q1) | `(valence, arousal, label_id, intensity?)` tuple — survives all three UX outcomes |
| Audit trail | PRD Story 8: kept but hidden | Opt-in only; default off; on toggle-off, hard-deleted (resolves "hidden audit" concern) |
| Photo attachments | Initial spec: `photo_uri` column | Not in v1 schema (PRD review Tier-2 Q8) |
| Server-side row-level encryption | PRD: "row-level encryption for journal_note" | Per-user envelope encryption with KMS-managed KEKs (PRD review §"row-level encryption needs definition") |
| Streaks | PRD Goal: streaks (only loop) | Schema-agnostic; derive from `emotion_logs` if kept |
| Sync timestamp HLC | PRD Open Q9 mentions HLC | Skew-clamped LWW; HLC migration path documented but not in v1 |
| Crisis resources | PRD Goal + initial spec | Bundled JSON asset; no DB table in v1 |
| Schema version on every row | Not in initial spec | Mandatory `schema_version` column on every replicable row (multi-version coexistence) |

---

## Appendix A: Comparison to PRD Open Questions

| Open Q | This design's position |
|---|---|
| Q1 (Mood Meter taxonomy) | Versioned bundled JSON; `(valence, arousal, label_id)` decouples data from UI |
| Q2 (Intensity model) | Nullable `intensity` column accommodates implicit (cell encodes it) or explicit (1..5) |
| Q3 (Quadrant edge cases) | `valence`/`arousal` allow exact-axis values (0); UX picks snap policy |
| Q4 (Multi-emotion) | Open (O3); current schema = one emotion per log |
| Q5–8 (Crisis) | Out-of-scope for v1 storage (Tier-1 Q4 "static link" recommendation) |
| Q9 (LWW timestamp) | `updated_at`, device-assigned, server-clamped for skew |
| Q10 (Universal `updated_at`) | Yes, mandatory on every replicable entity |
| Q11 (Edit past logs reconciliation) | Edit is just a write; LWW; optional audit trail (opt-in) |
| Q12 (Soft vs. hard delete) | Soft delete + 30-day grace + hard purge |
| Q13 (Per-device dedup) | `device_id` is stable per install; re-install = new id |
| Q14–16 (Streaks) | Streaks are derived; schema is agnostic |
| Q17 (Local-only mode lifetime) | Indefinite (synthetic user_id; renumber on link) |
| Q18 (Photo attachments) | Out for v1 |
| Q19 (Biometric lock) | Schema-agnostic; controlled via `app_settings` |
| Q20 (Data residency) | Region-pinned by deployment; schema unaffected |
| Q21 (Reminder model) | Local-only; `reminder_schedules` table device-local |
| Q22 (Coping activities content) | Bundled JSON; remote-config in v1.x |
| Q23 (Admin tooling) | Out of scope |
| Q24 (Launch timeline) | N/A (data model) |
| Q25 (Telemetry minimum) | App Store / Play Console only; no embedded SDK; no schema impact |

---

## Appendix B: References

- PRD draft: `.prd-reviews/how-we-feel-app/prd-draft.md`
- PRD review (synthesized): `.prd-reviews/how-we-feel-app/prd-review.md`
- Coherence review (Round 3 leg 2): bead `hwf-ln34`
- UX design (companion leg): bead `hwf-6lx`
- Scale & performance (companion leg): bead `hwf-qu7`

---

*End of report.*
