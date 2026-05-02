# Plan Review Manifest

| Field             | Value                                                              |
|-------------------|--------------------------------------------------------------------|
| Review ID         | `how-we-feel-app`                                                  |
| Repo root         | `/Users/defidavid/gc/.gc/worktrees/how-we-feel/polecats/furiosa`   |
| Coordinator agent | `how-we-feel/furiosa`                                              |
| Review target     | `how-we-feel/polecat`                                              |

## Problem Statement

Build a production-grade React Native + Node.js implementation of How We Feel
— an emotional wellness mobile app based on Marc Brackett's Yale RULER
framework and **Mood Meter** (2D valence × energy quadrants: red, yellow,
blue, green). The app helps users build emotional granularity through daily
check-ins, journaling, and pattern insights. Targets iOS and Android via
Expo, with offline-first SQLite, secure cloud sync, OAuth (Apple/Google),
push reminders, and full GDPR compliance.

A starting-point sketch exists at `initial-spec.md`. It is **not** ground
truth — it has known gaps the review legs are expected to surface and
address, including:

1. Incorrectly describes the emotion model as a Plutchik-style wheel
   (actual: Mood Meter, 4 colored quadrants by valence × energy).
2. Emotion taxonomy is hand-waved (~48 emotions but no list).
3. Crisis / self-harm safeguards are missing.
4. Sync conflict resolution is wrong: last-write-wins by `logged_at`, but
   `logged_at` is the time of the feeling, not the time of the write.
5. Streak logic is undefined.
6. No testing / CI/CD / observability / feature-flag strategy.
7. No accessibility specs.
8. No i18n or timezone handling.
9. Data model lacks `updated_at`.
10. Photo / biometric / edit-past-log features mentioned but not specified.

Privacy considerations: mental-health data sensitivity; no third-party
analytics SDKs that exfiltrate user content.

The PRD draft is at `.prd-reviews/how-we-feel-app/prd-draft.md`.
