# Design Report: How We Feel — Integration and Rollout Strategy

## Executive Summary

This design integrates the MoodMap PRD into a production-grade, full-stack architecture spanning React Native (Expo) client, Node.js backend, and PostgreSQL persistence. The architecture prioritizes:

1. **Offline-first mobile design** with local SQLite + SQLCipher encryption
2. **Scalable backend** on Node.js with Redis, Bull queues, and Row-Level Encryption (RLE)
3. **Type-safe development** via TypeScript across both tiers
4. **Modular boundaries** enabling parallel polecat dispatch during implementation
5. **Progressive rollout** from foundation → core loop → sync → insights → polish → hardening

---

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Client Layer: React Native (Expo) + Local Data             │
│ ├─ UI State: Zustand                                       │
│ ├─ Server Sync: React Query + custom sync engine           │
│ ├─ Local Data: SQLite + SQLCipher                          │
│ ├─ Navigation: React Navigation (stack + tabs)             │
│ ├─ Animations: Reanimated 3                                │
│ └─ Notifications: Expo Notifications                       │
├─────────────────────────────────────────────────────────────┤
│ Network Layer: HTTPS + JWT Authentication                  │
├─────────────────────────────────────────────────────────────┤
│ Server Layer: Node.js + Express/Fastify                    │
│ ├─ API routes: auth, logs, users, health                   │
│ ├─ Session store: Redis                                    │
│ ├─ Job queue: Bull                                         │
│ ├─ Data encryption: Row-level (journal notes)              │
│ └─ Database: PostgreSQL                                    │
├─────────────────────────────────────────────────────────────┤
│ Data Layer: PostgreSQL + Redis                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Client-Side Codebase Structure (React Native / Expo)

### Directory Layout

```
how-we-feel-app/
├── app.json                           # Expo config
├── tsconfig.json                      # TypeScript config
├── package.json                       # Dependencies
├── .env.example                       # Environment template
├── jest.config.js                     # Test config
│
├── src/
│   ├── __tests__/                     # Shared test utilities
│   │   ├── setup.ts                   # Jest setup, mocks
│   │   └── fixtures/                  # Test data generators
│   │
│   ├── api/                           # Server communication
│   │   ├── client.ts                  # Axios/fetch client setup
│   │   ├── auth.ts                    # Auth endpoints (apple, google, refresh)
│   │   ├── logs.ts                    # Emotion log endpoints
│   │   ├── users.ts                   # User profile, export, delete
│   │   └── types.ts                   # API response/request types
│   │
│   ├── db/                            # Local SQLite + encryption
│   │   ├── sqlite.ts                  # SQLite setup, encryption init
│   │   ├── migrations/
│   │   │   ├── 001_initial.sql        # Schema: emotion_logs, devices, etc.
│   │   │   └── 002_...sql             # Future migrations
│   │   ├── schema.ts                  # TypeScript schema interfaces
│   │   └── queries/
│   │       ├── logs.ts                # CRUD operations for emotion logs
│   │       ├── devices.ts             # Device registration/tracking
│   │       └── index.ts               # Barrel export
│   │
│   ├── sync/                          # Offline sync engine
│   │   ├── syncEngine.ts              # Core sync orchestration
│   │   ├── conflict.ts                # Conflict resolution (last-write-wins)
│   │   ├── queue.ts                   # Sync queue / state machine
│   │   └── types.ts                   # Sync state, metadata
│   │
│   ├── state/                         # Zustand store
│   │   ├── auth.ts                    # Auth state, JWT refresh
│   │   ├── logs.ts                    # Emotion log state
│   │   ├── ui.ts                      # UI state (modal visibility, etc.)
│   │   ├── sync.ts                    # Sync status (last_synced, errors)
│   │   └── index.ts                   # Combined store
│   │
│   ├── hooks/                         # Custom React hooks
│   │   ├── useAuth.ts                 # Auth helpers
│   │   ├── useSync.ts                 # Sync orchestration
│   │   ├── useLogs.ts                 # Emotion log queries
│   │   └── useNotifications.ts        # Notification handling
│   │
│   ├── screens/                       # Navigation screens
│   │   ├── onboarding/
│   │   │   ├── SplashScreen.tsx       # Splash + intro
│   │   │   ├── AuthScreen.tsx         # Apple/Google sign-in options
│   │   │   └── NotificationPerms.tsx  # Notification request
│   │   │
│   │   ├── home/
│   │   │   ├── HomeScreen.tsx         # Dashboard
│   │   │   ├── LogCard.tsx            # Today's log card
│   │   │   └── StreakDisplay.tsx      # Streak counter
│   │   │
│   │   ├── logging/
│   │   │   ├── EmotionWheelScreen.tsx # 3-tier wheel + intensity
│   │   │   ├── EmotionWheel.tsx       # Reanimated wheel component
│   │   │   ├── ContextTagsScreen.tsx  # Context chip selector
│   │   │   ├── JournalScreen.tsx      # Journal note text input
│   │   │   └── LogPreview.tsx         # Confirm before save
│   │   │
│   │   ├── insights/
│   │   │   ├── InsightsScreen.tsx     # Tab navigator
│   │   │   ├── CalendarHeatmap.tsx    # Color-coded day view
│   │   │   ├── FrequencyChart.tsx     # Bar chart (7d/30d/90d/all)
│   │   │   ├── IntensityTrends.tsx    # Line chart
│   │   │   ├── TimeOfDayPattern.tsx   # When user logs emotions
│   │   │   └── ContextCorrelation.tsx # Emotion x context
│   │   │
│   │   ├── journal/
│   │   │   ├── JournalScreen.tsx      # List of entries with notes
│   │   │   ├── JournalEntry.tsx       # Single entry detail
│   │   │   ├── SearchFilter.tsx       # Full-text + emotion/tag/date filter
│   │   │   └── EditEntry.tsx          # Edit/delete flow
│   │   │
│   │   ├── activities/
│   │   │   ├── ActivityLibrary.tsx    # Browse/favorite activities
│   │   │   ├── ActivityDetail.tsx     # Full activity content
│   │   │   ├── SuggestModal.tsx       # Contextual suggestion modal
│   │   │   └── activities.data.ts     # Activity library (bundled)
│   │   │
│   │   └── settings/
│   │       ├── SettingsScreen.tsx     # Settings root
│   │       ├── AccountTab.tsx         # Profile, sign out, delete
│   │       ├── DataTab.tsx            # Export, sync toggle
│   │       ├── NotificationsTab.tsx   # Reminder schedule config
│   │       ├── DisplayTab.tsx         # Theme, language
│   │       └── PrivacyTab.tsx         # Privacy policy, biometric lock
│   │
│   ├── navigation/
│   │   ├── RootNavigator.tsx          # Root stack (onboarding vs. authenticated)
│   │   ├── AuthNavigator.tsx          # Auth-only stack
│   │   ├── AppNavigator.tsx           # Post-auth bottom tabs + stack
│   │   ├── types.ts                   # Navigation param types
│   │   └── linking.ts                 # Deep linking config
│   │
│   ├── components/                    # Reusable UI components
│   │   ├── theme/
│   │   │   ├── colors.ts              # Color palette
│   │   │   ├── typography.ts          # Font sizes, weights
│   │   │   ├── spacing.ts             # Margin/padding scale
│   │   │   └── useTheme.ts            # Theme hook
│   │   │
│   │   ├── common/
│   │   │   ├── Button.tsx             # Primary, secondary, danger buttons
│   │   │   ├── Input.tsx              # Text input wrapper
│   │   │   ├── Card.tsx               # Card container
│   │   │   ├── Chip.tsx               # Context tag chip
│   │   │   ├── Modal.tsx              # Modal wrapper
│   │   │   └── Spinner.tsx            # Loading spinner
│   │   │
│   │   └── charts/
│   │       ├── BarChart.tsx           # Emotion frequency
│   │       ├── LineChart.tsx          # Intensity trends
│   │       └── CalendarDot.ts         # Heatmap dot
│   │
│   ├── utils/
│   │   ├── dates.ts                   # Date formatting, ranges
│   │   ├── emotions.ts                # Plutchik wheel, emotion families
│   │   ├── validation.ts              # Form validation
│   │   ├── encryption.ts              # Local encryption helpers
│   │   ├── logger.ts                  # Console + file logging
│   │   └── constants.ts               # App constants (emotion list, contexts)
│   │
│   └── App.tsx                        # Root component, store setup
│
└── e2e/                               # E2E test suite (Detox)
    ├── config.json
    ├── firstLogin.e2e.js              # Onboarding E2E
    ├── emotionLogging.e2e.js          # Log creation E2E
    ├── insights.e2e.js                # Insights E2E
    └── sync.e2e.js                    # Offline/online sync E2E
```

### Key Modules & Boundaries

#### 1. **API Layer** (`src/api/`)
- **Responsibility**: Client-server communication (auth, logs, user data)
- **Interface**: TypeScript types for all requests/responses
- **Isolation**: No direct DB access; routes through Zustand store
- **Testing**: Mock API via MSW (Mock Service Worker) in unit tests; real server in E2E

#### 2. **Database Layer** (`src/db/`)
- **Responsibility**: SQLite CRUD, schema versioning, local encryption
- **Interface**: Query functions (e.g., `getLogs(userId)`, `insertLog(entry)`)
- **Isolation**: No API calls; pure data persistence
- **Encryption**: SQLCipher for journal notes + full-DB encryption option
- **Testing**: In-memory SQLite for unit tests; real DB for integration tests

#### 3. **Sync Engine** (`src/sync/`)
- **Responsibility**: Offline queue management, background sync, conflict resolution
- **Interface**: `syncEngine.start()`, `syncEngine.stop()`, `addToQueue(entry)`
- **Isolation**: Uses both API and DB layers; stateful with event emitters
- **Testing**: Mock network conditions (offline/online transitions)

#### 4. **State Management** (`src/state/`)
- **Responsibility**: Zustand stores for UI, auth, logs, sync status
- **Interface**: Store hooks exposed via `useStore()`
- **Isolation**: No direct DB/API calls; dispatches to other layers
- **Testing**: Snapshot tests, mutation tests

#### 5. **Screens & Navigation** (`src/screens/`, `src/navigation/`)
- **Responsibility**: UI presentation, user interaction, deep linking
- **Interface**: React Navigation params, screen props
- **Isolation**: Consume hooks (useAuth, useLogs, useSync); call stores
- **Testing**: Unit tests for logic; E2E for navigation flow

---

## Server-Side Codebase Structure (Node.js)

### Directory Layout

```
how-we-feel-api/
├── package.json
├── tsconfig.json
├── .env.example
├── .gitignore
│
├── src/
│   ├── __tests__/                     # Shared test utilities
│   │   ├── setup.ts                   # Jest setup, mock DB/Redis
│   │   ├── fixtures/
│   │   │   ├── users.ts               # User factory
│   │   │   ├── logs.ts                # Emotion log factory
│   │   │   └── index.ts               # Barrel export
│   │   └── helpers.ts                 # Test request/response builders
│   │
│   ├── config/
│   │   ├── env.ts                     # Environment validation
│   │   ├── db.ts                      # Postgres connection pool
│   │   ├── redis.ts                   # Redis client
│   │   └── queue.ts                   # Bull job queue setup
│   │
│   ├── db/
│   │   ├── migrations/
│   │   │   ├── 001_initial.sql        # Schema: users, emotion_logs, devices, etc.
│   │   │   └── 002_...sql
│   │   ├── seeds/
│   │   │   └── dev.sql                # Development seed data
│   │   ├── queries/
│   │   │   ├── users.ts               # User CRUD + auth metadata
│   │   │   ├── logs.ts                # Emotion log CRUD + pagination
│   │   │   ├── devices.ts             # Device tracking
│   │   │   └── index.ts               # Barrel export
│   │   └── schema.ts                  # TypeScript DB schema interfaces
│   │
│   ├── auth/
│   │   ├── strategies/
│   │   │   ├── apple.ts               # Apple Sign-In token validation
│   │   │   ├── google.ts              # Google OAuth token validation
│   │   │   └── jwt.ts                 # JWT generation/refresh
│   │   ├── middleware.ts              # Express auth middleware
│   │   └── types.ts                   # Auth request/response types
│   │
│   ├── routes/
│   │   ├── auth.ts                    # POST /auth/apple, /auth/google, /auth/refresh, DELETE /auth/session
│   │   ├── logs.ts                    # GET /logs, POST /logs, DELETE /logs/:id
│   │   ├── users.ts                   # GET /users/me, DELETE /users/me, GET /users/me/export
│   │   ├── health.ts                  # GET /health
│   │   └── index.ts                   # Mount all routes
│   │
│   ├── jobs/
│   │   ├── deleteAccount.ts           # Account deletion job (cascade delete)
│   │   ├── exportData.ts              # Data export job (async generation)
│   │   ├── syncNotifications.ts       # Notification scheduling (v2+)
│   │   └── index.ts                   # Register all job handlers
│   │
│   ├── middleware/
│   │   ├── auth.ts                    # JWT verification, role checks
│   │   ├── errorHandler.ts            # Global error handler
│   │   ├── validator.ts               # Input validation (Joi/Zod)
│   │   ├── rateLimit.ts               # Rate limiting via Redis
│   │   └── logger.ts                  # Request/response logging
│   │
│   ├── services/
│   │   ├── encryption.ts              # Row-level encryption helpers
│   │   ├── sync.ts                    # Sync logic (upsert, conflict resolution)
│   │   ├── export.ts                  # Data export formatting
│   │   └── index.ts                   # Barrel export
│   │
│   ├── utils/
│   │   ├── logger.ts                  # Winston/Pino logger setup
│   │   ├── errors.ts                  # Custom error classes (ValidationError, AuthError, etc.)
│   │   ├── validators.ts              # Reusable validation rules
│   │   └── constants.ts               # App constants
│   │
│   └── app.ts                         # Express app setup (middleware, routes, error handling)
│
├── server.ts                          # Entry point (start server, migrations)
│
└── __tests__/                         # Integration & E2E tests
    ├── auth.integration.test.ts       # Auth endpoint tests
    ├── logs.integration.test.ts       # Log CRUD + sync tests
    ├── sync.integration.test.ts       # Conflict resolution tests
    └── export.integration.test.ts     # Data export tests
```

### Key Modules & Boundaries

#### 1. **Auth Layer** (`src/auth/`)
- **Responsibility**: Third-party token validation (Apple, Google), JWT issuance
- **Interface**: `validateAppleToken()`, `validateGoogleToken()`, `issueJWT()`, `refreshJWT()`
- **Isolation**: Reads from DB (users); writes session to Redis
- **Testing**: Mock Apple/Google token responses; validate JWT claims

#### 2. **Database Layer** (`src/db/`)
- **Responsibility**: Postgres CRUD, schema versioning, migrations
- **Interface**: Query functions (`getUserById()`, `insertLog()`, `updateLog()`, etc.)
- **Isolation**: No API calls; pure data persistence
- **Encryption**: Row-level encryption for journal_note column
- **Testing**: Test DB (separate Postgres instance for CI)

#### 3. **Routes / Handlers** (`src/routes/`)
- **Responsibility**: HTTP endpoint definitions, request validation, response serialization
- **Interface**: Express route handlers
- **Isolation**: Use auth middleware, call services and queries
- **Testing**: Integration tests with real/mock DB

#### 4. **Services** (`src/services/`)
- **Responsibility**: Business logic (sync upsert, encryption, export formatting)
- **Interface**: `syncUpsert(logs)`, `encryptNote(text)`, `formatExport(user)`
- **Isolation**: Call queries; no direct HTTP handling
- **Testing**: Unit tests with mocked queries

#### 5. **Jobs / Queue** (`src/jobs/`)
- **Responsibility**: Async tasks (account deletion, data export, future notifications)
- **Interface**: Bull job definitions, handlers
- **Isolation**: Read/write DB; no HTTP
- **Testing**: Unit tests with mocked DB; integration tests with real queue

---

## Module Boundaries & Dependencies

### Dependency Graph

```
┌──────────────────────────────────────────────────────────┐
│ CLIENT SIDE                                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Screens/Navigation ──────┐                             │
│                          ↓                              │
│  Hooks (useAuth, useLogs, useSync) ─┐                   │
│                                    ↓                    │
│  Zustand Store (auth, logs, ui, sync) ──┐              │
│                                         ↓               │
│  API Layer (client.ts, auth, logs, users)              │
│  Sync Engine (syncEngine, conflict, queue)             │
│  DB Layer (sqlite, queries)                            │
│                                                        │
├──────────────────────────────────────────────────────────┤
│ SERVER SIDE                                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  HTTP Routes (auth, logs, users, health) ──┐           │
│                                            ↓            │
│  Middleware (auth, errorHandler, validator)            │
│  Auth Layer (apple, google, jwt) ──┐                   │
│  DB Queries (users, logs, devices) │                   │
│  Services (encryption, sync, export) ──↓               │
│  Jobs (deleteAccount, exportData)                      │
│                                                        │
│  Config (env, db, redis, queue)                        │
│  Utils (logger, errors, validators)                    │
│                                                        │
└──────────────────────────────────────────────────────────┘
```

### Allowed Boundaries

1. **Screens → Hooks → Store** (unidirectional)
2. **Store → API + DB + Sync** (unidirectional)
3. **Sync → API + DB** (bidirectional; drives both)
4. **Routes → Services → Queries** (unidirectional)
5. **Middleware can wrap Routes** (horizontal)
6. **Jobs can call Queries** (unidirectional)

### Disallowed (Tightly Coupled)

- ❌ Screens directly calling API (use hooks)
- ❌ Sync directly calling Screens
- ❌ Services directly calling Routes
- ❌ Circular: A → B → A

---

## Rollout Strategy (6 Phases)

### Phase 0: Foundation (Weeks 1–2)
**Parallel Polecat Tasks:**
- **P0.1**: Expo scaffold, navigation shell, design system (colors, typography, spacing)
- **P0.2**: Local SQLite setup, migrations, encryption init (SQLCipher)
- **P0.3**: Node.js scaffold, Postgres schema, auth endpoints (stubs)
- **P0.4**: TypeScript config, linting, testing infrastructure (Jest, detox)

**Deliverables**: 
- Runnable Expo app (navigation working)
- Runnable Node.js API (health endpoint)
- Local DB schema
- CI/CD pipeline

**Acceptance Criteria**:
- Expo app starts without errors
- API responds to `GET /health`
- SQLite initialized with schema

---

### Phase 1: Core Loop (Weeks 3–4)
**Parallel Polecat Tasks:**
- **P1.1**: Emotion wheel UI (3-tier, Reanimated 3)
- **P1.2**: Log entry CRUD (client: SQLite; server: Postgres)
- **P1.3**: Home dashboard (today's logs, streak, weekly sparkline)
- **P1.4**: Emotion log API endpoints (POST, GET, DELETE)

**Deliverables**:
- User can log an emotion locally in under 60 seconds
- Logs persist to SQLite
- Dashboard displays today's logs

**Acceptance Criteria**:
- E2E test: Create emotion log in under 90 seconds
- Server stores logs in Postgres
- Home screen updates after log creation

---

### Phase 2: Sync (Weeks 5–6)
**Parallel Polecat Tasks:**
- **P2.1**: JWT auth (Apple + Google token validation)
- **P2.2**: Sync engine (queue, background sync, conflict resolution)
- **P2.3**: Sync middleware, routes, DB user tracking
- **P2.4**: Offline/online state management, error recovery

**Deliverables**:
- User can authenticate via Apple or Google
- Emotion logs sync to server when online
- Offline-created logs queue and sync on reconnect

**Acceptance Criteria**:
- E2E: Create log offline, go online, verify sync
- Conflict resolved (last-write-wins by `logged_at`)
- Sync status visible in Settings

---

### Phase 3: Insights (Weeks 7–8)
**Parallel Polecat Tasks:**
- **P3.1**: Calendar heatmap (color by emotion family per day)
- **P3.2**: Frequency + intensity charts (bar + line, local rendering)
- **P3.3**: Time-of-day pattern + context correlation
- **P3.4**: Insights API aggregation (future: precompute on server)

**Deliverables**:
- User can view 7d/30d/90d emotion patterns
- Charts render from local SQLite (no backend call)
- Context correlation visible

**Acceptance Criteria**:
- Heatmap renders in <300ms with 1000 logs
- Charts render offline
- Insights reflect actual data

---

### Phase 4: Journal & Activities (Weeks 9–10)
**Parallel Polecat Tasks:**
- **P4.1**: Journal list, search, filter (full-text + metadata)
- **P4.2**: Edit/delete journal entries with confirmation
- **P4.3**: Activity library (bundled asset, no network)
- **P4.4**: Contextual activity suggestion modal (trigger on fear/anger/sadness ≥4)

**Deliverables**:
- User can search journal entries locally
- User can favorite activities; favorites surface first
- Triggered activity suggestions after logging high-intensity negative emotion

**Acceptance Criteria**:
- Journal search <100ms on 1000 entries
- Activity bundle <500KB
- Activity suggestion triggers correctly

---

### Phase 5: Notifications & Polish (Weeks 11–12)
**Parallel Polecat Tasks:**
- **P5.1**: Configurable reminders (frequency, time windows, quiet hours)
- **P5.2**: Deep-linking from notification → log flow
- **P5.3**: Onboarding flow (splash + auth + notification perms)
- **P5.4**: Dark mode, accessibility audit, performance profiling

**Deliverables**:
- User receives push notifications on schedule
- Notification deep-link works
- Onboarding completes in <3 minutes
- App meets WCAG 2.1 AA accessibility

**Acceptance Criteria**:
- Reminders fire at correct times (test with mock date)
- Deep-link launches log screen
- Onboarding E2E test passes
- Lighthouse accessibility score > 95

---

### Phase 6: Production Hardening (Weeks 13–14)
**Parallel Polecat Tasks:**
- **P6.1**: GDPR export (full JSON) + account deletion (cascade, async)
- **P6.2**: Rate limiting, abuse protection, input validation
- **P6.3**: Performance profiling (wheel render, sync speed, memory)
- **P6.4**: App Store submission prep (screenshots, privacy policy, signing)

**Deliverables**:
- User can export all data as JSON
- User can delete account (all data cascade-deleted)
- Rate limits enforced (auth: 5 req/min per IP; logs: 100 req/min per user)
- App ready for App Store submission

**Acceptance Criteria**:
- Export completes in <10s for 10k logs
- Account deletion job completes in <60s
- No sensitive data in logs (PII redaction)
- App signing works (development, ad-hoc, App Store profiles)

---

## Testing Approach

### Client (React Native / Expo)

#### Unit Tests (`jest`)
- **Coverage target**: 75%
- **Test files**: `src/**/__tests__/**/*.test.ts(x)`
- **Scope**: Hooks, utils, services, store logic
- **Tools**: Jest, React Testing Library, MSW for API mocks

**Example test suite structure:**
```
src/
├── hooks/
│   ├── useAuth.ts
│   └── useAuth.test.ts          # Mock API, store
├── state/
│   ├── logs.ts
│   └── logs.test.ts             # Snapshot + mutation tests
├── utils/
│   ├── emotions.ts
│   └── emotions.test.ts         # Pure function tests
└── db/
    ├── queries/
    │   ├── logs.ts
    │   └── logs.test.ts         # In-memory SQLite
```

**Key tests:**
- Auth flow (token refresh, JWT decode)
- Zustand store mutations (adding log, syncing status)
- Sync engine state machine (offline → online → conflict)
- Emotion wheel calculation (tier navigation, intensity)
- Local DB queries (insert, update, delete)

#### Integration Tests (`jest + real SQLite`)
- **Scope**: Database persistence + queries + sync engine together
- **Setup**: Temporary in-memory SQLite per test
- **Test**: Insert log → Update status → Query with filters

#### E2E Tests (`detox`)
- **Coverage target**: Critical user flows
- **Test files**: `e2e/**/*.e2e.js`
- **Scope**: Onboarding, emotion logging, sync, insights

**Key E2E tests:**
1. `firstLogin.e2e.js`: Splash → auth → first emotion log
2. `emotionLogging.e2e.js`: Create log with context + journal
3. `insights.e2e.js`: Navigate insights, verify heatmap renders
4. `sync.e2e.js`: Create offline → go online → verify sync
5. `journal.e2e.js`: Search, filter, edit entries

**Test matrix:**
- iPhone 14 Pro (latest iOS)
- Pixel 6 (latest Android)
- Offline mode (mock network)
- Low memory (stress test SQLite)

---

### Server (Node.js)

#### Unit Tests (`jest`)
- **Coverage target**: 80%
- **Test files**: `src/**/__tests__/**/*.test.ts`
- **Scope**: Services, utils, middleware (mocked DB/Redis)
- **Tools**: Jest, Supertest for HTTP assertions

**Example test suite:**
```
src/
├── auth/
│   ├── strategies/
│   │   ├── apple.ts
│   │   └── apple.test.ts       # Mock Apple API
│   ├── middleware.ts
│   └── middleware.test.ts      # JWT validation
├── services/
│   ├── sync.ts
│   └── sync.test.ts            # Conflict resolution logic
└── utils/
    ├── errors.ts
    └── errors.test.ts          # Error class tests
```

**Key tests:**
- Apple/Google token validation (mock responses)
- JWT generation + refresh (signed tokens)
- Sync upsert logic (last-write-wins)
- Error handling (validation, auth, DB)
- Rate limiter (Redis mock)

#### Integration Tests (`jest + test DB`)
- **Scope**: Routes + DB together
- **Setup**: Separate Postgres instance (spun up in CI)
- **Test**: POST /auth/apple → JWT → GET /logs with JWT

**Key integration tests:**
1. Auth flow: Apple token → JWT issuance → refresh
2. Log creation: POST /logs with JWT → Postgres insert → GET /logs verify
3. Sync: Multiple logs upserted → conflicts resolved
4. Data export: Async job queued → JSON generated
5. Account deletion: Cascade deletes all related data

#### End-to-End Tests (Client ↔ Server)
- **Scope**: Full flow (Expo → Node.js → Postgres)
- **Setup**: Local dev server + test DB
- **Test**: Create account → Log emotion → Export data

**Key E2E tests:**
1. Register with Apple → Sync offline logs → Export data
2. Login on new device → Sync historical logs
3. Delete account → Verify cascade deletion

---

### CI/CD Pipeline

```yaml
# GitHub Actions / GitLab CI

On push to feature branches:
  1. Lint (ESLint + Prettier)
  2. Type check (TypeScript)
  3. Unit tests (client + server)
  4. Integration tests (server + test DB)
  5. Build Expo app (EAS if available)
  6. Detox E2E (snapshot)

On merge to main:
  1. All above
  2. Build production Expo app
  3. Deploy server to staging
  4. Full E2E on staging
  5. Generate coverage reports
```

---

## Compatibility Considerations

### Client (React Native / Expo)

#### iOS Compatibility
- **Min OS**: iOS 13 (App Store requirement)
- **Max OS**: Latest (test on iOS 18)
- **Apple Sign-In**: Required for App Store (iOS 13+)
- **Face ID / Touch ID**: Biometric lock optional (iOS 11+)
- **Notifications**: APNs (required for push)

#### Android Compatibility
- **Min SDK**: 24 (Android 7.0)
- **Target SDK**: Latest (36+)
- **Google OAuth**: Required alternative to Apple Sign-In
- **Notifications**: FCM (required for push)
- **Encryption**: Android Keystore for key material

#### Expo Compatibility
- **Managed workflow**: No native modules (unless via plugins)
- **OTA updates**: Expo Updates for rapid iteration
- **Prebuild**: For custom native code (if needed post-v1)

#### Device & Network Resilience
- **Offline support**: Full local-first operation, sync on reconnect
- **Poor network**: Graceful degradation; queue operations locally
- **Battery**: Background sync respects battery limits (no aggressive polling)
- **Storage**: App size <100MB (images/charts optimized)

---

### Server (Node.js)

#### Node.js Version
- **Min**: 18 LTS
- **Target**: 20 LTS
- **Testing**: 18, 20, 22

#### Database Compatibility
- **Postgres**: 13+
- **Migrations**: Versioned, reversible
- **Row-level encryption**: pgcrypto extension required

#### Third-Party Services
- **Apple Sign-In**: Direct token validation (no intermediate)
- **Google OAuth**: Direct token validation (no intermediate)
- **Expo Push Notifications**: Push token validation (future v2)
- **Redis**: Required for sessions + rate limiting (can be optional in v1 with in-memory store)

#### Backwards Compatibility
- **API versioning**: No `/v1/` prefix initially; if needed, route via `Accept: application/vnd.howwefeel.v2+json`
- **Schema migrations**: All migrations have down steps
- **JWT claims**: Can add fields without breaking old tokens (ignore unknown claims)

---

## Gas Town Integration & Polecat Dispatch

### Parallelization Strategy

Each phase decomposes into independent polecat tasks (P0.1, P0.2, P0.3, P0.4). Polecats work in parallel:

- **P0.1 (Expo Frontend)** and **P0.2 (SQLite)** can run in parallel (different repos/modules)
- **P0.3 (Node.js API)** and **P0.4 (CI/CD)** can run in parallel
- Dependencies emerge only when integration is tested (E2E phase)

### Bead Structure

Each phase creates sub-beads for individual polecat work:

```
Phase 0 (Foundation)
├─ hwf-p01-expo-scaffold      # Navigation, design system (frontend polecat)
├─ hwf-p02-sqlite-setup        # Local DB + encryption (mobile-db polecat)
├─ hwf-p03-api-scaffold        # Node.js + Postgres schema (backend polecat)
├─ hwf-p04-ci-pipeline         # GitHub Actions setup (devops polecat)
└─ hwf-p00-integration         # Test phase 0 integration (review polecat)

Phase 1 (Core Loop)
├─ hwf-p11-emotion-wheel       # Reanimated wheel (frontend polecat)
├─ hwf-p12-log-crud-client     # SQLite CRUD + Zustand (mobile-db polecat)
├─ hwf-p13-log-crud-server     # Postgres CRUD + API routes (backend polecat)
├─ hwf-p14-home-dashboard      # Dashboard screen (frontend polecat)
└─ hwf-p10-integration         # E2E: full logging flow (review polecat)
```

### Metadata for Dispatch

Each work bead carries metadata for the Refinery:

```json
{
  "work_bead": "hwf-p01-expo-scaffold",
  "metadata": {
    "phase": 0,
    "domain": "frontend",
    "dependencies": [],
    "expected_duration_hours": 8,
    "gc.routed_to": "how-we-feel/polecat"
  }
}
```

### Merge Strategy

- **Branch per bead**: Each polecat works on feature branch `gc-hwf-p01-expo-scaffold`
- **Refinery merges**: Refinery agent validates tests, reviews, merges to main
- **Dependency handling**: If P0.1 depends on P0.2, Refinery waits for P0.2's PR before merging P0.1

---

## Detailed Component Breakdown

### Client: Emotion Wheel Component

**Purpose**: Multi-tier emotion selector with haptic feedback

**Implementation** (Reanimated 3):
```typescript
// EmotionWheel.tsx
type TierType = 'family' | 'emotion' | 'intensity';
interface WheelState {
  tier: TierType;
  selected: { family?: string; emotion?: string; intensity?: number };
}

export const EmotionWheel = ({ onSelect }: Props) => {
  const [state, setState] = useState<WheelState>({
    tier: 'family',
    selected: {}
  });

  const handleTierSelect = (tier: TierType, value: string | number) => {
    // Haptic feedback
    Haptics.impact('Medium');
    
    // Advance tier or confirm
    if (tier === 'intensity') {
      onSelect(state.selected as SelectedEmotion);
    } else {
      setState(prev => ({
        ...prev,
        selected: { ...prev.selected, [tier]: value },
        tier: nextTier(tier)
      }));
    }
  };

  return (
    <Animated.View style={animatedStyle}>
      {state.tier === 'family' && <TierOne onSelect={handleTierSelect} />}
      {state.tier === 'emotion' && <TierTwo family={state.selected.family} onSelect={handleTierSelect} />}
      {state.tier === 'intensity' && <IntensitySlider onSelect={handleTierSelect} />}
    </Animated.View>
  );
};
```

**Testing**:
- Unit: Tier navigation logic, selection flow
- E2E: User navigates all tiers, selects emotion, sees intensity slider

---

### Server: Sync Upsert Endpoint

**Purpose**: Bulk upsert emotion logs with conflict resolution

**Implementation**:
```typescript
// routes/logs.ts
export const bulkUpsertLogs = async (req: Request, res: Response) => {
  const userId = req.user.id;
  const incoming: EmotionLog[] = req.body.logs;

  // Fetch existing logs for this user
  const existing = await db.getLogs({ userId });

  // Merge with conflict resolution (last-write-wins)
  const merged = incoming.map(log => {
    const prior = existing.find(e => e.id === log.id);
    if (prior && prior.logged_at > log.logged_at) {
      return prior; // Keep server version (newer)
    }
    return log; // Accept client version
  });

  // Upsert all
  await db.upsertLogs(userId, merged);

  // Return server state
  res.json({
    upserted: merged.length,
    serverLogs: merged
  });
};
```

**Testing**:
- Unit: Conflict resolution logic (last-write-wins, timestamp comparison)
- Integration: Create log on server → Update on client → Upsert → Verify server state
- E2E: Offline create → Online sync → Verify in Insights

---

### Database Schema (Postgres)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  provider VARCHAR(50) NOT NULL, -- 'apple' | 'google'
  provider_id VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  deleted_at TIMESTAMP
);

CREATE TABLE emotion_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  emotion_family VARCHAR(50) NOT NULL, -- 'joy', 'sadness', etc.
  emotion_label VARCHAR(100) NOT NULL, -- 'elated', 'melancholy', etc.
  intensity SMALLINT CHECK (intensity >= 1 AND intensity <= 5),
  context_tags TEXT[], -- ['work', 'family', ...]
  journal_note_encrypted BYTEA, -- Encrypted via pgcrypto
  logged_at TIMESTAMP NOT NULL, -- Client timestamp
  synced_at TIMESTAMP DEFAULT NOW(), -- Server receive time
  device_id UUID,
  deleted_at TIMESTAMP,
  UNIQUE(user_id, logged_at) -- Prevent duplicates
);

CREATE TABLE devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  device_name VARCHAR(255),
  last_seen_at TIMESTAMP DEFAULT NOW()
);

-- Indices for common queries
CREATE INDEX idx_emotion_logs_user_logged_at ON emotion_logs(user_id, logged_at DESC);
CREATE INDEX idx_emotion_logs_synced_at ON emotion_logs(synced_at DESC);
```

---

## Open Design Questions

1. **Notification delivery in v2**: Local scheduling (v1) vs. push notifications (v2)?
   - V1: Expo Notifications local scheduling (no server required)
   - V2: Add push token sync + server-side scheduling for cross-device reminders

2. **Photo attachments**: Store locally in v1; sync option in v2?
   - V1: Photos stored in app sandbox, not synced
   - V2: Optional encrypted photo sync via S3 + presigned URLs

3. **Analytics**: Privacy-respecting event logging?
   - V1: No third-party analytics
   - V2: First-party event stream (emotional patterns anonymized for research)

4. **Web admin panel**: Support in v1?
   - V1: No web admin; v1 ops handled via direct DB access
   - V2: Internal admin panel for support (GDPR export, account lookup)

---

## Summary

This design delivers a **modular, type-safe, offline-first** emotional wellness app with:

- **Client**: React Native (Expo) + SQLite local-first + Zustand state
- **Server**: Node.js + Postgres + Row-level encryption
- **Testing**: Unit + integration + E2E across both tiers
- **Rollout**: 6 phases with parallel polecat dispatch
- **Compatibility**: iOS 13+, Android 7.0+, offline support, GDPR-compliant

Key architecture decisions enable **independent polecat work** through clear module boundaries and **progressive delivery** through phased rollout.
