# Design: MoodMap — Local-First Emotion Log (React Native + Node.js)

> **Status:** Under PRD alignment review (Round 1)
> **Last Updated:** 2026-05-02
> **Current Phase:** Requirements coverage + goals alignment reviews

## Executive Summary

**MoodMap** is a React Native (Expo) + Node.js implementation of a local-first emotion-tracking application. Users log their emotional state using a **Mood Meter** — a 10×10 grid representing the Russell circumplex (2D affect model: valence × energy). The app prioritizes:

- **Offline-first:** All data stays on device (SQLite)
- **Speed:** Core logging loop completes in <30 seconds
- **Simplicity:** Single device, single user, no sync in v1
- **Gas Town alignment:** Supports parallel polecat dispatch

---

## Problem Statement

Build a **local-first mobile app** (iOS + Android via Expo) that helps a single user develop **emotional granularity** — the ability to identify, name, and distinguish feelings with precision. The Mood Meter provides a structured interface for rapid emotion selection and optional journaling.

**Key insight:** Emotions exist in 2D space (valence × energy). The Mood Meter maps this as a 10×10 grid where each cell is a specific emotion label.

---

## Requirements & Constraints

### Client (React Native / Expo)
- TypeScript strict mode, testable architecture
- SQLite for local persistence (no encryption beyond OS defaults)
- React Navigation for routing
- Emotion Meter: 10×10 tappable grid with emotion labels
- Local notification scheduling (no FCM/APNs in v1)

### Server (Node.js, optional for v2)
- Express or Fastify REST API
- PostgreSQL schema for future sync (not active in v1)
- Hardcoded dev credentials for testing endpoints
- Health check endpoint

### Constraints
- Single device, single user
- No user accounts (v1)
- No multi-device sync (v1)
- No encryption beyond OS file protection
- Local-only notifications
- No third-party integrations

---

## Architecture

### Client Architecture (React Native)

```
src/
├─ components/              # Reusable UI
│  ├─ MoodMeter.tsx        # 10×10 grid, selection, haptics
│  ├─ LogEntry.tsx         # Display a single log
│  ├─ InsightCard.tsx      # Chart/stat display
│  └─ ...
├─ screens/                # Screen containers
│  ├─ HomeScreen.tsx       # Today's logs, streak, CTA
│  ├─ InsightsScreen.tsx   # Charts: calendar, frequency, trends
│  ├─ JournalScreen.tsx    # List + search journal notes
│  ├─ SettingsScreen.tsx   # Preferences, export, deletion
│  └─ OnboardingScreen.tsx # First launch
├─ services/               # Business logic (DB, sync, notifications)
│  ├─ database.ts          # SQLite queries
│  ├─ mood-meter.ts        # Mood Meter grid, labels, cells
│  ├─ sync.ts              # Background sync (v2+)
│  ├─ notifications.ts     # Schedule/cancel notifications
│  ├─ export.ts            # JSON export
│  └─ ...
├─ store/                  # State (Zustand)
│  ├─ app.store.ts         # Global app state
│  ├─ logs.store.ts        # Current logs
│  ├─ settings.store.ts    # User settings
│  └─ ...
├─ types/                  # TypeScript types
│  ├─ mood.ts              # Mood/emotion types
│  ├─ log.ts               # Log entry schema
│  └─ ...
├─ utils/                  # Helpers
│  ├─ date.ts
│  ├─ validation.ts
│  └─ ...
└─ App.tsx                 # Root navigator
```

### Key Design Decisions

#### 1. Mood Meter Implementation
- **Grid:** 10×10 cells (0-9 on each axis)
- **Mapping:** Russell circumplex (x=valence, y=energy)
- **Labels:** 100 emotion names (e.g., "content", "excited", "anxious")
- **Colors:** Gradient from cool (unpleasant) to warm (pleasant)
- **Selection:** Tap a cell, haptic feedback, confirm dialog

#### 2. Data Model (Local)

```typescript
interface LogEntry {
  id: string;              // UUID
  moodGridX: number;       // 0-9
  moodGridY: number;       // 0-9
  moodLabel: string;       // e.g., "content"
  journalNote?: string;    // Optional freetext, max 1000 chars
  loggedAt: Date;          // User's timestamp
  createdAt: Date;         // System timestamp
  deviceId: string;        // Device fingerprint (for v2 sync)
}

interface MoodCell {
  x: number;
  y: number;
  label: string;           // Emotion name
  color: string;           // RGB/hex
  description?: string;    // Tooltip text
}
```

#### 3. State Management (Zustand)
- **Logs Store:** In-memory list of current session logs; queries delegate to DB for historical
- **Settings Store:** Notification schedule, theme, language
- **UI Store:** Current screen, sheet modals, toasts
- **Sync Store (v2 placeholder):** Pending syncs, conflict queue

#### 4. Database Schema (SQLite, v1)

```sql
CREATE TABLE logs (
  id TEXT PRIMARY KEY,
  mood_grid_x INTEGER CHECK (mood_grid_x >= 0 AND mood_grid_x < 10),
  mood_grid_y INTEGER CHECK (mood_grid_y >= 0 AND mood_grid_y < 10),
  mood_label TEXT NOT NULL,
  journal_note TEXT,
  logged_at DATETIME NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  device_id TEXT
);

CREATE INDEX idx_logs_logged_at ON logs(logged_at DESC);
CREATE INDEX idx_logs_mood ON logs(mood_label);
```

#### 5. API (v2 placeholder)

```
POST   /auth/dev-login          Hardcoded dev auth (v1)
GET    /health                  Uptime check

# Future (v2):
POST   /logs                    Bulk upsert
GET    /logs?since=<cursor>     Incremental fetch
DELETE /logs/:id                Soft delete
GET    /users/me/export         Full data export
```

---

## Key Services

### 1. Database Service
- **Init:** Migrate schema on first app launch
- **Queries:** Insert log, list by date range, search by note, stats aggregation
- **Transaction handling:** Ensure atomicity of multi-row writes
- **Cleanup:** Optional log deletion/archival (v2)

### 2. Mood Meter Service
- **Grid generation:** Russell circumplex → 10×10 emotions
- **Label mapping:** Consistent cell → emotion assignment
- **Color mapping:** Valence/energy → HSL gradient
- **Accessibility:** Voice-over labels for each cell

### 3. Notifications Service
- **Schedule:** Parse flexible schedule (e.g., 9am, Mon-Fri, 2x/day)
- **Cancel:** Clear pending notifications
- **Deep links:** Tap notification → opens logging screen
- **Quiet hours:** Respect do-not-disturb settings

### 4. Sync Service (v2 preparation)
- **Conflict resolution:** Last-write-wins by `loggedAt` timestamp
- **Incremental sync:** Fetch logs since last sync cursor
- **Retry logic:** Exponential backoff on network errors
- **User notification:** "Synced 5 minutes ago" status display

---

## Server Architecture (Node.js, v2+)

```
src/
├─ routes/                 # Route handlers
│  ├─ auth.ts             # Auth endpoints
│  ├─ logs.ts             # Log CRUD + sync
│  ├─ users.ts            # Profile, export, deletion
│  ├─ health.ts           # Uptime check
│  └─ ...
├─ services/              # Business logic
│  ├─ sync.ts             # Incremental sync + conflict resolution
│  ├─ export.ts           # Data export generation
│  ├─ queue.ts            # Bull job processor
│  └─ ...
├─ db/                    # Database layer
│  ├─ schema.sql          # PostgreSQL schema
│  ├─ migrations/         # Schema versions
│  └─ ...
├─ middleware/            # Express middleware
│  ├─ auth.ts             # JWT verification
│  ├─ rate-limit.ts       # Rate limiting
│  └─ ...
├─ types/
└─ index.ts               # Express app setup
```

### Server Data Model (PostgreSQL, v2)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  auth_provider VARCHAR,      -- 'dev', 'apple', 'google'
  provider_id VARCHAR,
  created_at TIMESTAMP DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE emotion_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  mood_grid_x INTEGER,
  mood_grid_y INTEGER,
  mood_label VARCHAR,
  journal_note TEXT,          -- Optionally encrypted v2+
  logged_at TIMESTAMP NOT NULL,
  device_id VARCHAR,
  synced_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE INDEX idx_logs_user_logged ON emotion_logs(user_id, logged_at DESC);
CREATE INDEX idx_logs_synced ON emotion_logs(user_id, synced_at);
```

---

## Testing Strategy

### Client Testing
- **Unit tests:** Services (mood-meter, notifications, export) with Jest
- **Integration tests:** Database with SQLite fixtures (PRAGMA foreign_keys)
- **Component tests:** React Navigation + components (React Native Testing Library)
- **E2E tests:** Detox for iOS/Android (onboard → log → view insights)

### Server Testing (v2)
- **Unit tests:** Route handlers with mocked DB
- **Integration tests:** Real PostgreSQL test DB with migrations
- **Contract tests:** OpenAPI schema validation
- **Load tests:** k6 for sync endpoint throughput

---

## Rollout Plan

### Phase 0: Foundation
1. Scaffold Expo + TypeScript + React Navigation
2. SQLite schema + initial migration
3. Basic component library + Storybook

### Phase 1: Core Loop
1. Mood Meter component (10×10 grid, tap detection, haptics)
2. Log creation + SQLite insert
3. Home screen (today's logs, streak count, quick stats)
4. Settings screen (theme, notifications, export)

### Phase 2: Insights (v1.1)
1. Calendar heatmap (emotion frequency by date)
2. Frequency chart (which emotions most logged)
3. Intensity heatmap (grid showing most-visited cells)
4. Time-of-day pattern (when do specific emotions occur)

### Phase 3: Journal & Polish
1. Journal list (all logs with notes)
2. Search + filter (by date, mood, text)
3. Edit/delete logs
4. Dark mode, accessibility (WCAG AA)

### Phase 4: Backend & Sync (v2)
1. PostgreSQL schema + migrations
2. Auth endpoints (dev account, future OAuth)
3. Sync endpoints (upsert, incremental pull, delete)
4. Export endpoint (full JSON export with metadata)

### Phase 5: Hardening
1. Performance profiling (Mood Meter render, sync speed)
2. Error monitoring (Sentry/similar)
3. Build for iOS/Android
4. Release to beta testers

---

## Success Criteria

✓ Core logging loop < 30 seconds (tap → save)
✓ All PRD requirements explicitly addressed (Round 1 validation)
✓ All PRD goals demonstrably achieved (Round 1 validation)
✓ No scope creep into non-goals (Round 2 validation)
✓ All user stories mapped to design elements (Round 3 validation)
✓ Code: TypeScript strict, well-tested, documented
✓ Supports Gas Town polecat dispatch (clear module boundaries)

---

## Open Questions

_To be resolved by PRD alignment reviews:_

1. **Emotion labels:** Exact 100-word set from Russell circumplex?
2. **Color scheme:** Specific gradient for valence/energy?
3. **Journal character limit:** 1000 chars, or variable?
4. **Stats granularity:** Count, frequency, heatmap, or all?
5. **Notification UI:** Scheduled time (24h clock), or range (morning, evening)?
6. **Export schema:** What metadata included in JSON export?
7. **Log retention:** Unlimited history, or prune after X months?
8. **Device ID:** Hardware fingerprint or user-settable?

---

## Next Steps

1. **PRD Alignment Round 1 (this phase):**
   - `requirements-coverage`: Every PRD requirement is designed
   - `goals-alignment`: Design achieves every stated goal

2. **PRD Alignment Round 2:**
   - Constraints compliance (no scope creep)
   - Non-goals enforcement

3. **PRD Alignment Round 3:**
   - User story mapping
   - Open questions clarification

4. **Bead Creation:** Convert design into implementation beads with dependencies

5. **Implementation:** Begin Phase 0 (foundation)
