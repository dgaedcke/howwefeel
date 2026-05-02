# PRD: How We Feel — React Native + Node Implementation

> **Status:** Draft. Breadth over polish. Many open questions are intentional —
> downstream review legs are expected to surface and resolve them. Where the
> initial-spec.md is known to be wrong, this PRD calls it out rather than papering
> over it.

---

## Problem Statement

Build a production-grade, privacy-first mobile app (iOS + Android via Expo) and
accompanying Node.js backend that helps people develop **emotional granularity**
— the ability to identify, name, and distinguish their feelings with precision.

The app is modeled on the original How We Feel app, which is built on Marc
Brackett's Yale RULER framework and the **Mood Meter**: a 2D grid where the
x-axis is **valence** (unpleasant ↔ pleasant) and the y-axis is **energy**
(low ↔ high). The grid is divided into four colored quadrants:

| Quadrant     | Energy | Valence    | Example feelings                      |
|--------------|--------|------------|---------------------------------------|
| Red          | High   | Unpleasant | Angry, anxious, frustrated, stressed  |
| Yellow       | High   | Pleasant   | Excited, joyful, hopeful, energized   |
| Blue         | Low    | Unpleasant | Sad, lonely, disappointed, bored      |
| Green        | Low    | Pleasant   | Calm, content, relaxed, peaceful      |

Within each quadrant, users zoom into a finer-grained taxonomy of named
emotions. The taxonomy size in the reference app is on the order of ~100 named
emotions; the exact list and tiering is an open question for review (see Open
Questions §1).

**This is mental-health-adjacent data.** It is highly sensitive. Failure modes
include: leaking emotional history, mishandling a user in crisis, breaking sync
in a way that loses logs, and surveillance-by-default analytics. Trust is the
product.

> **Note on initial-spec.md:** The starting-point sketch describes a
> Plutchik-style emotion wheel with 8 core families (Joy, Sadness, Fear,
> Anger, Disgust, Surprise, Trust, Anticipation). That model is **wrong** for
> this product. This PRD replaces it with the Mood Meter (valence × energy).

---

## Goals

### Product goals

1. **Time-to-log under 30 seconds** for the common case (Mood Meter tap → emotion
   pick → save). Fast enough that users actually do it multiple times a day.
2. **Build emotional granularity over time.** Encourage users to move past
   "fine" / "bad" toward specific named emotions.
3. **Surface meaningful patterns** — what times of day, contexts, and activities
   correlate with which emotional states.
4. **Offline-first.** Logging, browsing history, and viewing insights all work
   with no network. Sync is opportunistic.
5. **Privacy by default.** No third-party analytics SDKs that exfiltrate user
   content. Journals encrypted at rest. Account deletion fully cascades.
6. **Safe handling of distress.** When a user logs signals consistent with
   crisis (suicidal ideation, self-harm intent), surface region-appropriate
   resources without being pushy or paternalistic in normal use.

### Engineering goals

7. **Production-grade quality bar:** typed code, tests at multiple levels,
   CI/CD, observability, feature flags, error budgets.
8. **GDPR + CCPA compliance:** data export, right to deletion, clear consent
   for any optional data sharing.
9. **Two-platform parity** (iOS and Android) with one shared React Native
   codebase, shipped via Expo's managed workflow.
10. **Reasonable cost envelope** for a v1: single-region backend, no exotic
    infrastructure.

---

## Non-Goals

The following are explicitly **out of scope for v1.** Some may return in later
phases; calling them out here keeps scope honest.

- **Web app** (mobile only).
- **Wearable / HealthKit / Google Fit integration.** No biometric ingestion.
- **Therapist / clinical integrations.** This is not a medical device. We will
  not claim diagnostic or therapeutic efficacy.
- **Social features.** No public profile, no feed, no sharing emotion logs to
  contacts. (Anonymous, opt-in research aggregates may be considered later;
  not v1.)
- **Real-time multi-device collaboration.** Sync is eventually consistent.
- **Gamification beyond simple streaks.** No leaderboards, badges, points,
  XP. Streaks themselves are tentative — see Open Questions §5.
- **AI-generated journal prompts or summarization in v1.** (LLM features are
  appealing but introduce data-handling complexity that needs its own design
  pass.)
- **Admin / ops web panel** in v1. Operate via CLI + database access until
  load justifies a UI.

---

## User Stories / Scenarios

### Core loop

1. **First-time user** opens the app, completes onboarding (≤3 screens), grants
   notification permission (or skips), and logs their first emotion in under 60
   seconds.
2. **Daily user** receives a check-in push at a configured time, taps it,
   lands directly in the Mood Meter, picks a quadrant → an emotion → optionally
   adds a journal note → saves. End-to-end under 30 seconds.
3. **Reflective user** opens Insights and reviews their last 30 days: dominant
   quadrant by week, time-of-day patterns, top contexts (work, sleep, family).
4. **Journaling user** scrolls a date and writes a longer reflection attached
   to a previous emotion log.

### Edge / sensitive cases

5. **User in distress** logs a high-energy unpleasant emotion (Red quadrant)
   and selects an emotion label like "hopeless" or writes a journal note
   matching crisis indicators. The app surfaces a non-blocking, region-aware
   resource card (e.g., 988 in the US, Samaritans in the UK) and a one-tap
   "talk to someone" affordance. **Never blocks the user from saving the log.**
6. **Privacy-conscious user** signs up without OAuth ("local-only"), uses the
   app entirely offline, and never has data leave the device. Later they may
   opt into sync without losing history.
7. **Multi-device user** signs in on a new phone. All historical logs sync
   down. Local edits made offline on either device merge cleanly.
8. **Late logger** opens the app at 9pm to log how they felt this morning at
   8am (`logged_at` ≠ `created_at`). The app supports backdating and shows
   the entry on the morning's timeline, not the evening's.
9. **GDPR user** requests data export and gets a downloadable JSON within 24
   hours. Requests deletion and all PII is purged within the legal window.
10. **Accessibility user** with VoiceOver / TalkBack can navigate the Mood
    Meter, log an emotion, and review insights without sighted use. Dynamic
    type and high-contrast variants supported.
11. **Non-English user** uses the app in their language; emotion labels,
    insights, and notifications are localized; timestamps respect their
    timezone and DST.
12. **Account-deleting user** taps "delete my account" and is shown what will
    be erased, when, and any data that will be retained (e.g., aggregated
    anonymous metrics, if any). Confirms with re-auth.

---

## Constraints

### Technical

- **Mobile:** React Native via **Expo managed workflow** (or Expo "prebuild"
  if a custom native module becomes necessary — flag for review).
- **Backend:** Node.js (Fastify or Express — open question §6), PostgreSQL,
  Redis, deployed single-region for v1.
- **Local storage:** SQLite, encrypted at rest (SQLCipher or platform-keyed
  equivalent). Note: SQLCipher with Expo managed workflow may require Expo
  prebuild — needs verification (Open Question §3).
- **Network:** REST + JSON over HTTPS with JWT bearer tokens. (gRPC and
  websockets are not justified in v1.)
- **Auth:** Apple Sign-In **(required for App Store given any social login
  presence)**, Google OAuth, plus a passwordless local-only mode that does
  not register a server-side identity.
- **Push:** Expo Push Service in front of APNs/FCM.
- **CI/CD:** GitHub Actions (assumed); EAS Build for app binaries.
- **Observability:** Backend traces + structured logs (vendor TBD — see Open
  Questions §11). On-device error reporting that scrubs PII before send;
  vendor TBD and must satisfy "no user-content exfiltration" rule.

### Privacy / compliance

- **No third-party analytics SDKs that exfiltrate user content.** First-party
  event metrics only, scrubbed of any free-text journal content and any
  emotion labels at user-identifiable granularity. Aggregate counts only.
- **GDPR / CCPA:** export, deletion, consent records, DPA-able sub-processors.
- **At-rest encryption:** journal notes encrypted at rest server-side
  (per-user key managed via KMS, exact scheme TBD).
- **In-transit encryption:** TLS 1.2+ everywhere; cert pinning is an open
  question for v1 vs. v1.x.
- **No background tracking** (location, contacts, calendar) unless an explicit
  feature requests it with separate consent.
- **Children:** age-gate at signup. Under-13 (US) / under-16 (EU) handling
  needs legal input — possibly blocked from cloud sync, possibly blocked
  outright for v1.

### Operational

- **Cost ceiling for v1:** order-of-magnitude $X/month for first 10k MAU
  (concrete number TBD, but the architecture must not require a fleet).
- **On-call:** single engineer for v1; alerts must be actionable, not noisy.
- **Region:** single primary region (US-East assumed); multi-region is a v2+
  concern.

---

## Open Questions

Numbered for traceability so review legs can reference them.

### Product / model

1. **Emotion taxonomy.** What is the canonical list of named emotions per
   quadrant, and how many tiers does the Mood Meter expose (quadrant → emotion,
   or quadrant → sub-region → emotion)? Need a defensible source list.
2. **Intensity.** Does each log carry an intensity score on top of the named
   emotion (1–5? continuous?), or is intensity *implicit* in the choice of
   emotion ("annoyed" vs "furious")? The reference app does not appear to use
   a separate intensity slider — needs confirmation.
3. **Backdating.** Can users edit `logged_at` to record past feelings? How far
   back? What happens to streak / insights if they backdate?
4. **Crisis safeguards — design.** What heuristics trigger the resources
   surface? Keyword scan of journal text? Specific emotion labels? Both? How
   do we avoid both false negatives (missing real distress) and false positives
   (paternalistic spam after one bad day)? Is there a settings opt-out?
5. **Streaks.** Are streaks daily? "At least one log per day in user's
   timezone"? What about timezone changes, travel, DST? Does a missed day
   reset, or do we offer a grace period? Are streaks visible at all in v1, or
   does that introduce unhealthy compulsion?
6. **Photo attachments.** The initial sketch mentions photos. What's the use
   case — does a photo attach to an emotion log? Is it ever synced (PHI
   implications)? Or is it strictly local? Recommend deferring out of v1
   unless there's a strong reason.
7. **Activities (coping suggestions).** Bundle in v1, or defer? If included,
   how is the library curated and by whom? Evidence basis?

### Engineering / architecture

8. **Sync conflict resolution.** Last-write-wins keyed on what?
   - `logged_at` is **the time of the feeling**, not the time of the write,
     so it is the wrong key for conflict resolution.
   - Need a separate `updated_at` on every mutable row, set by the device at
     mutation time. Server resolves conflicts by `updated_at`. Add `updated_at`
     to all mutable entities.
   - For deletes, soft-delete with a `deleted_at` tombstone that wins over
     equal-or-older `updated_at` on other replicas.
   - Open: do we need vector clocks or HLC for true causal ordering, or is
     wall-clock `updated_at` "good enough"? (Probably good enough for v1
     given the data shape — single-user, low write rate.)
9. **Local DB encryption mechanism.** SQLCipher requires native modules. With
   Expo managed workflow, the alternatives are `op-sqlite` + SQLCipher (needs
   prebuild) or platform-keyed file-level encryption + plain SQLite. Pick one,
   know the tradeoff.
10. **Backend framework.** Fastify vs Express. Fastify is faster and has
    better schema validation; Express has the ecosystem. Either works. Pick
    one.
11. **Observability vendor.** Datadog, Honeycomb, OpenTelemetry-only? Must
    not require shipping user content. Cost vs. ergonomics tradeoff.
12. **Feature flags.** GrowthBook (self-hosted), LaunchDarkly (paid), or
    config-file flags? Need a way to dark-launch risky changes (esp. sync
    engine, crisis surfaces).
13. **Testing layers.** Unit (Jest), integration (Supertest for API), E2E
    (Detox or Maestro for app), contract tests between app and API, visual
    regression for the Mood Meter? Define minimum bar.
14. **Migration strategy.** SQLite schema migrations on the device need to
    handle very-old client versions. Postgres migrations need a forward-only
    strategy. Pick tools (e.g., Drizzle / Knex / Prisma) and document.
15. **Internationalization.** What languages at launch? English-only v1 with
    i18n scaffolding from day one is the safe answer, but confirm.
16. **Timezones.** All timestamps stored UTC + an `original_tz` field, or
    local-civil-time strings for `logged_at`? Affects insights ("what time of
    day do I feel X") materially.
17. **Push permission strategy.** Hard-ask up-front, soft-ask after first
    log, or not until user enables reminders? Affects long-term retention.

### Compliance / safety

18. **Crisis content storage.** Do we ever process journal text on the
    server (for crisis detection, or anything else)? If yes, how is that
    bounded and disclosed? If we keep all NLP on-device, what's the model
    size and quality tradeoff?
19. **Account-recovery without sync.** A local-only user who loses their
    device loses their data. Is that the contract, or do we offer optional
    encrypted backup with a user-managed key?
20. **Sub-processors list.** Hosting (Fly.io / Railway / AWS?), push
    (Expo / direct APNs/FCM), email (Postmark / SES?), error reporting,
    KMS — each is a sub-processor for GDPR purposes. Needs compiling.

---

## Rough Approach

This is the **shape** of the system, not the design. The 6 design legs that
follow this PRD will produce the actual design document.

### Architecture sketch

```
┌──────────────────────────────────────────────────────────────┐
│  Mobile App (React Native, Expo)                             │
│   ├─ UI layer (Mood Meter, Insights, Journal, Settings)      │
│   ├─ State (Zustand or Redux Toolkit; TBD)                   │
│   ├─ Local DB (SQLite, encrypted at rest)                    │
│   ├─ Sync engine (background, idempotent, resumable)         │
│   ├─ Notifications (Expo Notifications, locally scheduled)   │
│   └─ Crisis-safety surfaces (on-device heuristic)            │
└────────────┬─────────────────────────────────────────────────┘
             │ HTTPS + JWT
┌────────────▼─────────────────────────────────────────────────┐
│  API (Node.js, Fastify-or-Express)                           │
│   ├─ Auth (Apple, Google, refresh tokens)                    │
│   ├─ Sync endpoints (upsert + cursor-based pull)             │
│   ├─ Account / GDPR (export, delete, consent log)            │
│   ├─ Push registration                                       │
│   └─ Health, metrics, structured logs                        │
├──────────────────────────────────────────────────────────────┤
│  Postgres   │  Redis (sessions, rate limit)  │  Job queue    │
│  (users,    │                                │  (BullMQ for  │
│  emotion_   │                                │  exports,     │
│  logs,      │                                │  deletions)   │
│  journals,  │                                │               │
│  devices,   │                                │               │
│  consent)   │                                │               │
└──────────────────────────────────────────────────────────────┘
```

### Data model sketch (server)

All mutable rows carry **`created_at`, `updated_at`, and `deleted_at`** (soft
delete). `updated_at` drives sync conflict resolution; `logged_at` is the
*time the feeling occurred* and is purely a domain field.

```
users(id, auth_provider, provider_user_id, email_hash,
      created_at, updated_at, deleted_at, gdpr_consent_at, locale, tz)

emotion_logs(id, user_id,
             quadrant /* enum: red|yellow|blue|green */,
             emotion_label /* canonical string */,
             intensity /* nullable until §1, §2 resolved */,
             context_tags[], journal_id /* nullable */,
             logged_at /* time of feeling */,
             created_at, updated_at, deleted_at,
             origin_device_id, schema_version)

journals(id, user_id, body_encrypted, created_at, updated_at, deleted_at)

devices(id, user_id, platform, push_token_encrypted,
        last_seen_at, created_at, updated_at, deleted_at)

consents(id, user_id, kind /* sync, analytics, research */,
         granted_at, revoked_at)
```

Schema is illustrative; final shape is for the design legs.

### Sync engine sketch

- Each device assigns a UUID `id` to new rows on creation.
- Each mutation updates `updated_at = device-local-now`.
- Push: device sends rows where `local_updated_at > last_push_synced_at`.
- Pull: device requests `?since=<server-cursor>`, gets all rows with
  `server_updated_at > cursor`.
- Conflict: server keeps the row with the larger `updated_at`. Tie → larger
  `(updated_at, device_id)` deterministically.
- Tombstones: a row with `deleted_at != NULL` wins over a same-or-older
  `updated_at` non-deleted version.
- Hard delete (account purge) is a separate, server-initiated event.

### Phased rollout

| Phase | Scope                                                         |
|-------|---------------------------------------------------------------|
| 0     | Repo skeletons, CI, design system, lint/type/test baselines  |
| 1     | Local-only flow: Mood Meter, log, history, basic insights    |
| 2     | Auth + sync (cloud, multi-device)                            |
| 3     | Journal full-text, insights expansion, contextual safety     |
| 4     | Notifications + reminders                                    |
| 5     | GDPR tooling, deletion pipeline, polish, accessibility audit |
| 6     | i18n, app store hardening, crisis-resource regional packs    |

Each phase ships behind feature flags where it touches existing surfaces.

### Quality bar

- Typed: TypeScript end-to-end (strict).
- Tests: unit for pure logic, integration for API + DB, E2E (Detox/Maestro)
  for the golden logging path, contract tests for the sync schema.
- CI/CD: PR gates (lint, typecheck, unit, integration); main deploys
  backend; tagged releases trigger EAS Build for app binaries.
- Observability: structured logs, traces, RED metrics on the API; on-device
  error reporting (PII-scrubbed); a dashboard showing sync success rate,
  crash-free sessions, and time-to-log p50/p95.
- Accessibility: meets WCAG 2.1 AA equivalents for mobile; Mood Meter
  navigable by VoiceOver/TalkBack with semantic labels; respects Dynamic
  Type / Font Scale; tested with system-level color filters.

---

## Known gaps from the initial-spec.md sketch

For the review legs' awareness, this draft *intentionally* corrects or flags
the following errors in `initial-spec.md`:

- **Plutchik wheel → Mood Meter.** Replaced.
- **Emotion taxonomy.** Promoted to Open Question §1 instead of hand-waving "~48".
- **Crisis safeguards.** New goal + user story #5 + Open Questions §4, §18.
- **Sync conflict resolution.** Replaced LWW-on-`logged_at` with LWW-on-`updated_at`.
- **Streak logic.** Open Question §5; treated as tentative.
- **Testing / CI / observability / feature flags.** New constraints + Open
  Questions §11, §12, §13.
- **Accessibility.** New user story #10; quality-bar entry; needs a leg.
- **i18n + timezones.** Open Questions §15, §16; user story #11.
- **Data model — `updated_at`.** Added explicitly; sync depends on it.
- **Photo / biometric / edit-past-log.** Photos → Open Question §6.
  Biometric lock → settings concern, not a v1 spec gap. Edit-past-log →
  Open Question §3.

---

*End of draft.*
