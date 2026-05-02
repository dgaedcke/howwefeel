# PRD: MoodMap — Local-First Emotion Log (Experiment)

> **Status:** Consolidated scope — human answers to 19 critical PRD questions integrated.
> **Context:** This is a LOCAL EXPERIMENT to test Gas Town pipeline throughput, not a
> production app. Single developer, single device, single user. No deploy target, no app
> store submission, no real users. Goal: see how fast Gas Town can execute a full
> implementation across client + minimal backend tiers.

---

## Problem Statement

Build a local-first mobile app (iOS + Android via Expo) and minimal Node.js backend
that helps a single user develop **emotional granularity** — the ability to identify,
name, and distinguish their feelings with precision. The app is modeled on the original
How We Feel app, which uses the **Mood Meter**: a 2D grid where the x-axis is **valence**
(unpleasant ↔ pleasant) and the y-axis is **energy** (low ↔ high).

**Core concept:** The Mood Meter is a 10×10 grid. The x-axis is **valence**
(unpleasant ↔ pleasant); the y-axis is **energy** (low ↔ high). Each cell carries
its own emotion label, sourced from the Russell circumplex (a public-domain
2D affect model). Users tap a cell, optionally add a journal note, and save in
under 30 seconds.

**Scope note:** Russell circumplex replaces the Plutchik wheel from initial-spec.md.
No sub-tiering (quadrant → sub-region → emotion) in v1; each cell is atomic.
No intensity slider; intensity is implicit in the choice of cell.

---

## Goals

### Core product goals

1. **Time-to-log under 30 seconds** — Mood Meter tap → save. No friction.
2. **Build emotional granularity.** Move beyond "fine" toward specific named
   emotions indexed in the Mood Meter.
3. **Basic insights.** Show check-in frequency (e.g., "14 check-ins this month")
   and mood distribution by grid region (no advanced analytics in v1).
4. **Offline-first, local-only.** v1 has no sync. All data stays on device.
   Optional sync endpoints exist for future phases.
5. **Developer ergonomics.** Typed, testable, reproducible. Single-device exp.

### Experiment goals

6. **Test Gas Town pipeline throughput.** See how fast polecats can span
   client + server tiers with parallel dispatch and realistic integration
   challenges.

---

## Explicitly Out of Scope

This is a single-device, single-user local experiment. The following are OUT:

- **Multi-device sync** (v1 is local-only).
- **User accounts** (hardcoded dev account for backend endpoints only).
- **OAuth / Apple Sign-In / Google Sign-In** (no real auth in v1).
- **Photos, photo attachments** (text journal notes only).
- **Streaks** (replaced with simple "X check-ins this month" stat).
- **Crisis safeguards / intervention surfaces** (appropriate only for reviewed,
  deployed apps — skip for experiment).
- **Gamification** (no leaderboards, badges, points, XP).
- **Therapist / clinical integrations** (this is not a medical device).
- **Real-time collaboration, presence, or social features**.
- **AI / LLM features** (no prompts, summarization, classification in v1).
- **Encryption beyond OS file protection** (plain expo-sqlite, no SQLCipher).
- **GDPR / CCPA tooling** (no compliance requirements for local experiment).
- **Internationalization** (English-only; i18n scaffolding can wait).
- **App store submission** (local dev build only).
- **Production hosting / deploy** (server runs on dev machine).

---

## User Story

**The Single User's Day:**

1. Opens app, taps the 10×10 Mood Meter, lands on a cell (e.g., row 3, col 7).
2. Cell label reads (e.g.) "content" — confirms, optionally adds a journal note.
3. Save. Timestamp recorded. Done in <30 seconds.
4. Later, opens Insights: sees "14 check-ins this month" and a heatmap showing
   which regions of the grid they visited most.
5. Can browse past logs by date and re-read journal notes.
6. Can schedule a daily 9am reminder via local notification.
7. If they wish, can send a "sync now" to a server (opt-in, future phase).

**No user accounts, no sync by default, no crisis intervention, no multilingual UI.**

---

## Tech Stack

### Client (iOS + Android)

- **Framework:** React Native via Expo managed workflow.
- **Language:** TypeScript (strict mode).
- **Local storage:** expo-sqlite (plain, no encryption layer; rely on OS file protection).
- **Notifications:** expo-notifications (local scheduling only; no FCM/APNs in v1).
- **State management:** TBD (Zustand, Context, or minimal Redux).

### Server (Optional / Phase 2+)

- **Runtime:** Node.js with TypeScript.
- **Framework:** Express or Fastify (polecat's choice).
- **Database:** SQLite (not Postgres; keep migrations lightweight).
- **Auth:** Simple JWT; single hardcoded dev account for v1.
- **API style:** REST + JSON.
- **Sync endpoints (future):** `/auth/login`, `/sync/pull`, `/sync/push`, `/journal` CRUD.
- **Sync model (when built):** Pull-then-push on app open + manual "Sync Now" button.
  Last-write-wins by client-set `updated_at`. No HLC, no CRDT, no audit replication.
- **Hosting:** Dev machine only (no deploy target, no production).

### Development

- **Language & tooling:** TypeScript end-to-end, ESLint, Prettier, Jest.
- **Source:** GitHub (branch-per-polecat model via Gas Town).
- **CI/CD:** GitHub Actions for linting, type-check, unit tests.
- **No:** observability vendors, analytics SDKs, third-party integrations,
  compliance automation, app store CI/CD.

---

## Remaining Design Questions

Minimal unknowns, deferred to design legs.

1. **Mood Meter cell labels.** How are the 10×10 grid cells labeled? Sample from
   Russell circumplex? Hand-curated? What tool / reference?
2. **Journal UI.** Inline text input vs. separate editor view? Character limits?
   Past journal retrieval / search?
3. **Insights heatmap.** How to visually represent which grid regions the user
   visited most? Color intensity, frequency bars, or simple counts?
4. **Reminder UX.** How to schedule daily notifications via expo-notifications?
   UI for time-of-day config? Does reminder fire on app start or scheduled?
5. **Backend server setup.** If polecats build server tier: Express or Fastify?
   Local SQLite or in-memory? Session storage (file-based or memory)?
   How to seed / reset dev data?

---

## Architecture (Phase 1 + Early Backend)

### Phase 1: Local-only mobile

```
┌───────────────────────────────────────┐
│  Mobile App (React Native, Expo)      │
│   ├─ Mood Meter UI (10×10 grid)       │
│   ├─ Journal editor                   │
│   ├─ Insights view (heatmap + stat)   │
│   ├─ Local SQLite DB                  │
│   ├─ Local notifications (reminders)  │
│   └─ Settings (time, permissions)     │
└───────────────────────────────────────┘
```

### Phase 2+: Optional backend (for testing Gas Town)

Once Phase 1 is solid, add optional backend for sync:

```
Mobile (Phase 1) <--opt-in REST + JWT--> Backend (Node.js)
                                          ├─ Express or Fastify
                                          ├─ SQLite (local dev)
                                          └─ Hardcoded dev account
```

**Sync model:** Pull-then-push on app open + manual "Sync Now" button.
Last-write-wins by client `updated_at`. Single hardcoded user.
No production hosting; server runs on dev machine.

### Client data model (local SQLite)

```
emotion_logs(
  id TEXT PRIMARY KEY,
  grid_row INT,          -- 0–9
  grid_col INT,          -- 0–9
  cell_label TEXT,       -- e.g., "content", "anxious"
  journal_id TEXT,       -- optional FK
  logged_at DATETIME,    -- when the feeling occurred (for display)
  created_at DATETIME,   -- when the log was created
  updated_at DATETIME,   -- for future sync conflict resolution
  synced BOOL DEFAULT 0  -- tracks whether sent to server
)

journals(
  id TEXT PRIMARY KEY,
  body TEXT,
  created_at DATETIME,
  updated_at DATETIME
)
```

### Server data model (optional, Phase 2+)

```
users(id, device_id, created_at)

emotion_logs(
  id, user_id, grid_row, grid_col, cell_label, journal_id,
  logged_at, created_at, updated_at, deleted_at
)

journals(id, user_id, body, created_at, updated_at, deleted_at)
```

Soft deletes via `deleted_at`. `updated_at` key for LWW sync.

### Future sync sketch (when built)

When backend is added (Phase 2+), sync works as follows:

- **Pull on app open.** Client requests `GET /sync/pull?since=<cursor>`, server
  returns all rows with `updated_at > cursor`.
- **Push on manual action.** User taps "Sync Now" or equivalent. Client sends
  `POST /sync/push` with all local rows.
- **Conflict resolution.** Server keeps the row with the larger `updated_at`.
  For equal timestamps, larger `(updated_at, device_id)` wins.
- **Deletes.** Soft delete via `deleted_at` tombstone. Tombstone beats a same-or-older
  non-deleted version.
- **No real accounts.** Hardcoded dev account (e.g., device_id) for v1.

### Phased rollout

| Phase | Scope | Notes |
|-------|-------|-------|
| 1 | Local-only: Mood Meter, log, journal, insights | No sync, no backend. Mobile only. |
| 2+ | Optional backend + sync | If polecats want to test Gas Town cross-tier work. |

Phase 1 is the experiment target. Phase 2+ is stretch for Gas Town pipeline reps.

### Quality bar

- **Typing:** TypeScript (strict mode) across mobile and server.
- **Testing:** Unit tests for state logic (Jest); integration tests for API
  endpoints; manual smoke test of the golden path (log → save → insights view).
- **Linting:** ESLint + Prettier. Pre-commit hook via Husky.
- **CI/CD:** GitHub Actions on PR: lint, typecheck, unit tests. Manual test
  before merge.
- **No:** observability vendors, error reporting, dashboards, accessibility
  audit (v1 scope). Emoji support, animations, advanced visuals deferred.

---

## Scope Consolidation Summary

This PRD replaces the initial-spec.md entirely. Key consolidations based on
human PRD review answers:

### Removed (per hwf-ip9 consolidation)

- Multi-device sync (v1 is local-only)
- User accounts / OAuth (hardcoded dev account only)
- Photos, photo attachments
- Streaks (replaced with simple "X check-ins this month")
- Crisis intervention surfaces (skip for experiment)
- Gamification, leaderboards, badges
- Therapist / clinical claims
- AI / LLM features
- Encryption beyond OS file protection
- GDPR / CCPA tooling
- Internationalization
- App store CI/CD, submission
- Production hosting

### Kept (core to experiment)

- 10×10 Mood Meter (Russell circumplex labels)
- Emotion log with optional journal note
- Basic insights (frequency, heatmap)
- Local storage (expo-sqlite)
- Local notifications (reminders)
- Simple backend scaffolding (Express or Fastify with hardcoded auth)
- Optional sync (pull-then-push, LWW on `updated_at`)

### Experiment goal

Test how fast Gas Town can take a 2-tier app (client + server) from PRD
consolidation → design → implementation across parallel polecat dispatch.

---

*PRD consolidated 2026-05-02. Ready for design legs.*
