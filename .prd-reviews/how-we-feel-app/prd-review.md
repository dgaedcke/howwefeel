# PRD Review: Build a production-grade React Native + Node.js implementation of How We Feel — an emotional wellness mobile app based on Marc Brackett's Yale RULER framework and Mood Meter (2D valence x energy quadrants). The app helps users build emotional granularity through daily check-ins, journaling, and pattern insights. Targets iOS and Android via Expo, with offline-first SQLite, secure cloud sync, OAuth (Apple/Google), push reminders, and full GDPR compliance.

> **Source legs** (reports on bead notes): requirements (`hwf-13q`), gaps
> (`hwf-a4f`), ambiguity (`hwf-6a4`), feasibility (`hwf-57i`), scope
> (`hwf-9yc`), stakeholders (`hwf-bfd`).
> **PRD draft reviewed:** `.prd-reviews/how-we-feel-app/prd-draft.md`.

## Executive Summary

The PRD is an unusually self-aware draft — the author surfaces most known
weak spots as Open Questions and the appendix gap-table maps cleanly to
review-leg findings. The legs converge on three structural conclusions:

1. **One latent legal gate must be promoted from "Open Question 1" to a
   Phase 0 entry condition.** The Mood Meter is Marc Brackett's published
   work tied to Yale's RULER program, and "How We Feel" is the literal name
   of an existing app already licensed from Yale. The draft treats this as
   a UX taxonomy choice; multiple legs (feasibility C1, stakeholders §11,
   requirements observation, gaps §37) flag it as a trademark + IP gate
   that can block submission, force a late-stage rename, and invalidate
   significant Phase 1–4 UX work. **Resolve before any Phase 0
   implementation starts.**

2. **v1 is too large to be a credible MVP for the privacy-first thesis.**
   The single biggest cut is multi-device sync — the PRD itself names sync
   as the "dominant complexity," and 5 of the 25 Open Questions are
   sync-driven. Cutting sync removes ~30–50% of v1 engineering effort,
   removes most of the GDPR-Art.9-server-side surface, simplifies the
   privacy story from "encrypted then synced" to "never leaves the
   device," and dissolves the most acute Constraints↔Open-Questions
   contradictions (the `updated_at` ownership issue alone has three
   conflicting positions in the draft). Three further cuts (collapse
   Insights to one chart, defer heuristic crisis detection to a static
   "Get Support" link, drop streaks) shave more weeks without weakening
   the spine. With these cuts, v1 becomes a single sentence: *"An
   offline-only iOS+Android Mood Meter check-in app with journaling, daily
   reminders, a 30-day calendar heatmap, full GDPR export, and a static
   crisis-support link."*

3. **Several "v1 product" decisions are actually non-engineering
   decisions in disguise** and the team cannot unblock itself on them.
   Crisis-aware surfacing requires legal + clinical sign-off; the launch
   market choice (US-only vs. US+EU) drives DPIA / GDPR-K parental
   consent / Art. 9 lawful basis work; the business model (paid /
   freemium / B2B2C / grant-funded) determines whether the architecture
   needs entitlement checks and tenant data isolation from day one. Six
   stakeholder roles are implied by the PRD but not assigned to humans:
   **clinical advisor, security/threat-model owner, support persona,
   localization owner, accessibility owner, product/business owner**.
   Without those names, "Safe handling of distress," "GDPR-grade,"
   "WCAG 2.1 AA," and "transparent privacy posture" are marketing copy.

A consequence worth saying out loud: realistic time-to-App-Store-submission
for a 2–3 senior-engineer team is **9–14 months** (per feasibility leg
O9), not the multi-phase rough-approach implies. Phase 0 alone is **6–10
weeks** of real work once the Yale licensing question is resolved. A
single full-stack engineer is closer to **15–24 months**.

The PRD's strongest acceptance criteria are quantitative (60s/30s/90s
time-to-log; ≤30-day deletion deadline; standards bindings WCAG 2.1 AA,
GDPR Art. 9, TLS 1.2+). The weakest are the qualitative goals
("Granularity," "Trust," "Operationally honest") — currently
unfalsifiable, with no measurement path that doesn't conflict with the
no-content-analytics constraint.

## Before You Build: Critical Questions

These are the questions that should drive the human-clarification gate.
Each lists options and (where the legs converge) a recommended default.
Tiered by what gates the most downstream work.

### Tier 1 — answer before any Phase 0 implementation begins

**Q1. Yale Mood Meter / "How We Feel" IP and naming.**
The PRD's Open Q1 reads as a UX taxonomy choice; it is in fact a
trademark + IP gate (feasibility C1; stakeholders §11). Pick one path:

- (a) Commercial license from Yale RULER for the taxonomy *and* a
  rename to avoid the existing app's mark.
- (b) Different name + Yale-derived taxonomy under license.
- (c) Different name + clean-room substitute taxonomy (Russell
  circumplex, Plutchik-derived, or custom — needs UX + clinical input;
  feasibility C5 budgets 2–4 weeks for a defensible substitute set).
- (d) Different name + different emotion model entirely.

**Recommendation:** decide in week 1; do not start Phase 0 until a
written legal opinion is in hand. The cost of resolving this in month 1
is small; the cost of resolving it in month 6 is a near-total restart.

**Q2. Launch market and business model.**
Drives compliance scope and architecture (stakeholders §4; gaps §16, §30).
State explicitly:

- **Launch market:** US-only? US+EU? Global? *EU-from-day-one materially
  raises the bar* — DPIA (Art. 35), explicit-consent flow (Art. 9), DPO,
  Art. 8 child-data rules, sub-processor DPAs, EU residency questions.
- **Business model:** paid app / freemium / B2B2C (employer-sponsored,
  introduces a third stakeholder who must never see individual data) /
  grant-funded. Some monetization paths (ad targeting, data sales) are
  foreclosed by the privacy posture and worth acknowledging.
- **Acquisition stance:** any acquirer who would re-target user data is
  precluded by the posture; explicit?

**Recommendation:** answer before any data-model work; bake into
Constraints rather than leaving in Open Questions.

**Q3. Is multi-device sync in v1, or v1.x?**
The single highest-leverage scope question (scope Critical §1; feasibility
C3; ambiguity §1–2; gaps §11, §19–21).

- **Sync in v1:** retain auth, server, sync engine, audit-trail
  replication, server-side deletion infra, server observability, on-call.
  Add ~30–50% engineering effort; resolve `updated_at` ownership
  (device / server / HLC), edit-vs-delete precedence, audit-trail
  replication, free-text merge strategy (LWW silently drops one edit).
- **Sync in v1.x:** local-only v1, accounts deferred. Phase 0 collapses
  to mobile-only scaffold + SQLite/SQLCipher + Mood Meter + privacy/a11y
  checklists; Phase 2/6 server work moves out; the privacy story becomes
  "data never leaves the device" instead of a multi-clause statement.

**Recommendation (legs converge):** cut sync from v1. The v1 sentence
becomes legible, the Open Questions about conflict resolution become
moot, and the privacy thesis strengthens.

**Q4. What is the v1 crisis surface?**
The PRD lists this as a Goal, a Phase 4 deliverable, *and* "feature flagged
for staged rollout" — three statuses (scope Critical §2; stakeholders §1;
requirements §3; ambiguity §3; feasibility I6).

- (a) Heuristic detection (quadrant + intensity, optionally journal text
  scan) — requires a named clinical advisor, a curated test corpus with
  TPR/FPR targets, locale-vetted hotline data, and legal sign-off on
  liability framing. The code path itself is in the binary even when the
  flag is off, so it is subject to security/legal scrutiny regardless.
- (b) Static "Get Support" entry in Settings linking a bundled localized
  hotline list. No automated detection. No quadrant/intensity trigger. No
  journal-text scanning.
- (c) Nothing crisis-related in v1.

**Recommendation (legs converge):** **(b)** for v1; promote heuristic to
v1.1 *after* legal/clinical review. Reword the Goal from "Crisis-aware"
to "Crisis-discoverable." If (a) is held: name the clinical advisor and
the legal counsel before Phase 0.

**Q5. Stakeholder owners — name names.**
Six roles are implied by the PRD but unassigned (stakeholders §1–5; gaps
§§5, 21, 32, 36; requirements §6–7). Which are committed for v1?

- **Clinical advisor** (licensed mental-health professional) — Goal #6
  and crisis content currency.
- **Security / threat-model owner** — including a coercive-control /
  shared-device threat model that is currently absent.
- **Product / business owner** — owns Q2 above.
- **Support persona / owner** — defines the maximum data surface support
  is allowed to see (privacy posture forbids reading journal content).
- **Localization owner** — gates non-English locales; safety-critical
  for crisis content.
- **Accessibility owner** — defines who runs the WCAG 2.1 AA audit and
  signs off the Mood Meter's non-color encoding + screen-reader path.

**Recommendation:** name three minimum (clinical, security, product).
Without these, several "Goals" are unverifiable claims.

### Tier 2 — answer before Phase 1 implementation begins

**Q6. SQLCipher path under Expo.**
"Expo (managed workflow)" + "SQLite via Expo SQLite + SQLCipher" do not
compose as written (feasibility C2). Pick:

- (a) `op-sqlite` / `react-native-quick-sqlite` with SQLCipher build flag,
  or a config plugin patching expo-sqlite. **Requires EAS Build + custom
  dev client commitment from Phase 0.** Update the PRD wording to "Expo
  with config plugins via EAS Build," not "managed workflow."
- (b) Application-layer AES-GCM per row over plain expo-sqlite (no
  SQLCipher). Slightly worse defense-in-depth (SQL queries see plaintext)
  but no native-build complexity.
- (c) Plain expo-sqlite + OS file protection only. Acceptable only if the
  privacy threat model explicitly says so.

**Recommendation:** spike (a) in Phase 0 week 1 (1–2 weeks budget); end
the spike with a green EAS Build and an encrypted DB on a real device.
Also resolve SQLCipher key-loss policy: device-only key (DB unrecoverable
on key loss; requires clear user-facing UX) vs. user-controlled escrow
(passphrase, OAuth-derived KEK).

**Q7. Mood Meter intensity model.**
Two engineers reading this PRD will build different UIs (ambiguity §4;
feasibility I1).

- (a) The cell *is* the intensity (10×10 grid, label per cell — closer to
  Brackett's published format).
- (b) Quadrant pick → emotion label → separate intensity slider (1–5).
- (c) Hybrid.

This decision gates the Reanimated 3 + WCAG-AA Mood Meter UI, which
feasibility leg I1 budgets at 4–6 weeks. **Recommendation:** decide
before Phase 1 starts and prototype on a real iPhone + Pixel for
VoiceOver / TalkBack confirmation in week 1 of Phase 1.

**Q8. Photo attachments — out, or in?**
Three readings appear in the draft (ambiguity §5). Schema/sync/export/
encryption implications cascade (feasibility O2; scope §2).

**Recommendation (legs converge):** **out for v1**; drop `photo_uri` from
schema and add explicitly to Non-Goals. Reintroduce as a Phase 2+ schema
migration if/when committed.

**Q9. Streaks — in, or out?**
Open Q14–16 admit the logic is undefined; timezone/DST correctness becomes
load-bearing only because of streaks; gamification despite the Non-Goals
carve-out; values-conflict for users with depression (scope §B;
stakeholders §11; ambiguity §8; gaps §32).

**Recommendation (legs converge):** **out**; replace with a non-gamified
"X check-ins this month" stat on Today. Removes Open Q14–16 entirely and
removes timezone correctness as a streak-correctness concern (still
applies to `logged_at` semantics).

**Q10. Reminder sequencing.**
Reminders are in Phase 5 polish; the thesis says consistency is the
mechanism (scope §C). **Recommendation:** move local reminders + deep
link to **Phase 1**. Negligible work; substantial sequencing improvement.

**Q11. Account recovery policy when both Apple and Google access lost.**
Currently undefined (gaps §6, §11). Pick:

- (a) Accept the lockout class explicitly with disclosure at sign-in
  ("if you lose access to both your Apple ID and Google account, you
  cannot recover your data").
- (b) Device-side recovery code generated at first sign-in, surfaced in
  Settings, optionally backed up to user-controlled storage.
- (c) Email-based recovery side-channel (conflicts with Apple
  Hide-My-Email relay revocation — requires a fallback).

**Recommendation:** state the choice in the PRD; (a) is the simplest and
most privacy-consistent and probably right if sync is cut from v1
(per Q3).

### Tier 3 — answer before Phase 2 (only if sync stays in v1)

**Q12. `updated_at` ownership.** Three positions in the draft contradict
each other (Constraints silent; Open Q9 says device-assigned; Phase 2
says server-assigned — ambiguity §1). Pick: device-assigned with skew
tolerance / server-assigned on receipt / hybrid logical clock.

**Q13. Edit-vs-delete precedence rule, and free-text merge strategy.**
LWW silently drops one of two simultaneous journal edits. Acceptable, or
do journal notes need a different merge (CRDT, manual merge prompt, last
write with audit-trail visibility)?

**Q14. Audit-trail replication semantics.** "Audit trail keeps prior
values… not exposed in UI by default" (Story 8) is real append-only
history that must replicate, syncs implications, GDPR export questions
(scope observation §3 flags this as hidden data collection — either drop
it entirely or expose it as opt-in).

### Tier 4 — answer before App Store / Play Store submission

**Q15. Performance budgets and device matrix.** State the device matrix
(iOS target/min, Android target/min, low-end Android reference device)
and per-target performance budgets (cold start, Mood Meter render and
sustained frame rate, sync round-trip, Insights heatmap at 365/1825 days)
— requirements §5.

**Q16. The "transparent privacy posture surface."** What in-app surfaces
discharge "Trust" (requirements §2; ambiguity vague-language)?
**Recommendation:** dedicated Privacy screen reachable in ≤2 taps, plus
a mandatory onboarding privacy step, plus a "this device only" indicator
on Today for local-only mode. Bind to a CI network-egress test on an
instrumented build.

**Q17. Shared-device / coercive-control safety defaults.** Currently
unaddressed (stakeholders §2, §6). Minimum acceptance: notifications
never reveal user content (emotion family, journal text, intensity,
context tags); locked-screen snapshot test in CI. Stretch: optional
biometric-on-by-default, app-icon disguise (v2), panic-clear (v2).

**Q18. GDPR/legal/store deliverables — owners and timeline.**
DPIA (Art. 35), explicit-consent flow (Art. 9), sub-processor list and
DPAs, ROPA (Art. 30), ToS, privacy policy, US-state privacy review
(CCPA/CPRA, CO/CT/VA), GDPR-K parental consent path if EU, age gate at
first run, **iOS Privacy Manifest** (`PrivacyInfo.xcprivacy`), Apple
Sensitive Health Information disclosure, Google sensitive-data
declaration, Apple Sign-In **Server-to-Server notification endpoint**
(account-delete, consent-revoked) and **Hide-My-Email relay** handling
— each needs an owner and a date (gaps §1–5, §15–18; feasibility C4).

**Q19. Operational baseline (only if sync in v1).** Server-side backup
cadence + retention + encryption + tested restore drill; deletion-queue
monitoring with 30-day alerting; on-call rotation with breach-class
incident severity matrix; SLOs (e.g., 99.5% / p95 <500 ms) with error
budgets — gaps §19–21; requirements §6.

## Important But Non-Blocking

Items multiple legs flagged as worth filling but not gating the next
phase.

- **Soft goals are unfalsifiable.** "Granularity," "Trust" (the
  in-app-surface clause), "Operationally honest" need acceptance criteria
  or replacement with concrete sub-claims (requirements §1, §2). The
  Granularity goal in particular has no measurement path that doesn't
  collide with the no-content-analytics constraint — clarify whether
  even controlled-vocabulary signals (emotion-label counts) count as
  "content analytics."

- **Cross-platform parity is asserted, not enforced.** Per-platform
  acceptance for sign-in, notifications, biometric, a11y tooling,
  performance, store policy (requirements §4). Either restate every
  acceptance criterion as "iOS: X, Android: Y" or add a cross-cutting
  "applies independently to iOS and Android unless noted." Add device
  matrix up front.

- **Lock-screen notification leakage and OS-level backup leakage** —
  two specific failure modes that need explicit constraints
  (requirements §11, §12). Notifications never reveal user content
  (snapshot test); SQLite excluded from iOS iCloud Backup / Android
  Auto Backup; Keychain entries marked
  `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` to prevent iCloud
  sync.

- **No-egress acceptance test.** A CI-runnable test that completes
  every documented flow on an instrumented network and fails the build
  on any unexpected outbound traffic (requirements §8). This is the
  single most load-bearing acceptance criterion for the privacy thesis.

- **DST / timezone decision table for streaks (only if streaks stay).**
  Replace "without breaking" with explicit (event × outcome) cells
  (requirements §9; ambiguity §10; gaps §32). If streaks are dropped
  per Q9, this collapses but `logged_at` semantics still need a
  decision.

- **Schema migration framework on device.** Versioned, tested with
  fixture DBs from each prior version, downgrade policy (forbid or
  explicit), migration tests as a Phase 0 quality gate (gaps §12). A
  primary source of silent data loss on routine app updates.

- **Emotion-taxonomy versioning.** Open Q1 names the question; without
  a versioning answer, future taxonomy updates silently break existing
  logs (gaps §14).

- **Insights performance at scale.** Define behavior at 5 years of
  daily logs (~1825+ entries); heatmap render time, FTS index size,
  query plan stability (requirements important consideration).

- **Storage growth and purge policy.** No upper bound stated (especially
  if photos ever land); behavior at cap unspecified (requirements
  important consideration).

- **Sync state UI failure surface.** Why sync failed (auth expired, conflict, server down) and manual resync UX
  (requirements observation).

- **Audit log of admin and sync operations.** PRD names this; Open Q23
  admits admin tooling may not exist v1 — reword to avoid implying
  admin tooling that doesn't exist (requirements observation).

- **Test plan additions.** Property tests for the sync engine, clock-skew
  / DST tests for streaks, migration tests, privacy regression / SBOM-
  diff CI, localization snapshot tests, pseudoloc + RTL builds, device
  matrix for E2E (gaps §31–35; requirements observation; ambiguity
  observation).

- **`logged_at` timezone semantics for Insights bucketing.** Decide
  whether `logged_at` carries a timezone and whether Insights bucket on
  the *original* wall-clock or the *current* wall-clock (ambiguity §10).
  Mirror whatever rule streaks use (or applies regardless if streaks are
  dropped).

- **"Row-level encryption for `journal_note`" needs a real definition.**
  Postgres has no native row-level encryption; pick column-level
  pgcrypto / app-layer AES-GCM / per-user envelope encryption with KMS
  KEKs (ambiguity §9). Only relevant if sync stays in v1.

- **Apple Sensitive Health Information specifics.** Mention exists,
  details don't; coping content + crisis link may push the App Store
  rating to 17+ and triggers Apple's mental-health content review (gaps
  §18).

- **Phase 6 is launch-blocking, not "polish."** Rate limiting, GDPR
  export/delete, observability, store submission gate launch. Rename to
  "Launch readiness" or split: launch-blocking vs. post-launch
  hardening (scope observation §10).

## Observations and Suggestions

- **Promote the appendix gap-table to the top of the PRD** — it
  orients reviewers fast and makes the relationship to `initial-spec.md`
  explicit (requirements observation).

- **Pick a uniform statement on Constraints↔Open-Questions interaction.**
  Several pairs contradict (`updated_at`, reminder model, streak
  ownership, all-entities timestamps, Phase 0 quality gates) — the
  Constraint asserts, the Open Question reopens. Either close the
  question or downgrade the constraint (ambiguity §1, §2, §6, §7, §8).

- **Strip rhetorical phrases that don't constrain implementation:**
  "frictionless," "operationally honest," "discreet," "GDPR-grade,"
  "mental-health-adjacent," "transparent privacy posture surfaced
  in-app." Replace with the time budget, the enumerated quality gates,
  the visual weight, the article reference, and the named in-app
  surface respectively (ambiguity vague-language).

- **Add a glossary** anchoring "Mood Meter cell," "intensity band,"
  "context tag," "coping activity," "audit trail," "core flow,"
  "crisis-aware," "heuristic" (ambiguity).

- **The "single managed host" framing under-represents shape** —
  Postgres + Redis + BullMQ workers are separate services, and Fly.io's
  first-party managed Postgres has been deprecated in favor of partners.
  Pin Railway (managed) or list Supabase / Neon / self-managed-on-Fly
  (feasibility C7).

- **Self-hosted Sentry is genuinely expensive** for a small team; default
  to scrubbed SaaS plus an *architectural* rule that journal text never
  reaches the error path (CI lint), not just a configuration rule
  (feasibility C6).

- **EAS Build paid plan is required, not optional** (~$1,200/yr; free
  tier burns out within days of PR-driven workflow) — feasibility I2.

- **Apple "Sensitive Health Information" guidance is stricter than
  ordinary privacy claims** and requires data-handling documentation
  with the submission package — add an explicit pre-submission
  acceptance gate (requirements observation).

- **Add Non-Goal firewalls** — short hard rules to prevent scope debate:
  "Any future AI feature that ingests journal text MUST use on-device
  inference" and "We do not write to system health stores in v1 or v2"
  (scope observation §8).

- **Open-Question numbering needs repair.** The brief referenced phantom
  Q-numbers (Q23 deletion verification, Q8 liability framing) — Q8 in
  the draft is sync conflict resolution, and Open Questions stop at Q20
  per stakeholders leg (Q25 in the appendix gap-table extends further).
  Realign so legs and the human gate can cite stable references
  (stakeholders observation).

- **The story for the "user in distress" (§6) and the crisis-aware Goal
  contradict each other on free-text scanning.** Pick the v1 surface
  per Q4 above and remove the inconsistency (ambiguity §3; scope
  observation §7).

- **No path to early user feedback is described.** First user-facing
  build is end-of-Phase-1 or Phase-2 with no TestFlight / friends-and-
  family / a11y user testing gate. Add an internal alpha milestone
  after Phase 1 lands the local check-in loop *with reminders* (per
  Q10) — scope §G.

- **Account-less local mode is the privacy thesis's single strongest
  feature.** The PRD treats it almost in passing. Surface as a primary
  onboarding option, not a tucked-away "or" (scope observation §4).

- **Story 8's audit trail is hidden data collection.** "Kept but not
  exposed by default" creates a subpoena / breach / "show edit history"
  trap. Either drop edit-trail entirely (edits overwrite) or expose it
  as opt-in (scope observation §3; gaps §17 in spirit).

- **Telemetry minimum (Open Q25).** Crash count, sync error rate,
  install/uninstall — these are reported by App Store Connect / Play
  Console directly; no embedded SDK needed. Make this explicit to
  remove the perceived tension between observability and privacy
  (feasibility O5; requirements observation).

## Confidence Assessment

The legs differ in their stated confidence; the synthesis below reflects
where the legs converge vs. where signal diverges.

- **High confidence** that the structural ambiguities exist as stated
  (Constraints↔Open-Questions contradictions; `updated_at` ownership;
  Phase 0 quality gates; photo attachments scope; SQLCipher under Expo
  managed-workflow incompatibility; Apple Sign-In S2S obligations
  missing). These are mechanical cross-references and verifiable
  against external docs (ambiguity overall confidence; feasibility C2,
  C4 high).

- **Medium-high confidence** that the gap inventory in the gaps leg
  is reasonably complete (DPIA / lawful-basis / sub-processors /
  account-recovery / migrations / SQLCipher key loss / iOS Privacy
  Manifest / age-gating / deletion-queue alerting / on-call). What
  would raise it: sight of any existing threat-model or compliance
  artifacts; clarity on launch jurisdiction.

- **Medium confidence** on prioritization within stakeholders and
  scope. The recommendations to (cut sync, defer heuristic crisis
  detection, drop streaks, collapse Insights to one chart) are
  *direction* — high confidence — but the *magnitude* depends on
  unanswered questions about timeline, team size, and goal priority
  ordering.

- **Medium confidence** on the Yale/RULER trademark severity
  (feasibility C1 medium): the IP overlap and prior-licensee fact are
  public record, but precise enforcement-posture probability requires
  a trademark search, which has not been done. Risk class is
  unambiguously high; the recommended path (resolve in week 1) holds
  regardless.

- **Lower confidence** on App Store review duration variance for
  sensitive-health-adjacent apps in 2026 (feasibility I5) — store
  policy is a moving target.

What would lift overall confidence to high across the synthesis:

1. **A trademark search and written legal opinion** on (a) the project
   name "How We Feel" and (b) the chosen emotion taxonomy. Week 1.
2. **A 1-week SQLCipher-in-Expo spike** that ends with a green EAS
   Build and an encrypted SQLite table on a real device. Settles Q6
   and the Phase 0 plan.
3. **Answers to the Tier-1 critical questions** (Q1–Q5) — IP, launch
   market + business model, sync v1?, crisis surface v1?, named
   stakeholder owners. With these five, several Tier 2–4 questions
   reduce to engineering decisions.
4. **A sync design doc** (only if Q3 keeps sync) before Phase 2 starts:
   timestamp source, edit-vs-delete precedence, audit-trail replication,
   test matrix.
5. **A staffing plan with named roles** — who owns Mood Meter UX +
   a11y, sync, security, support, legal/clinical advisory.
6. **A product priority ordering of the Goals list.** Currently nine
   Goals are stated equally; "Trust" and "Granularity" cannot both be
   #1. Whichever is #1 cascades through the other questions (e.g.,
   "Trust" #1 forces Q3 to "cut sync," Q4 to "static link," Q9 to
   "drop streaks").

## Next Steps

In rough order:

1. **Repair Open-Question numbering** (the brief referenced Q23 / Q8
   that don't exist as labeled). Realign so subsequent legs can cite
   stable references.
2. **Run the human clarification gate** (next step in `mol-idea-to-plan`,
   bead `hwf-ip9`) using the Tier-1 questions above — Q1–Q5 first.
   Carry forward Tier-2 questions if their dependencies have been
   resolved by Tier-1 answers.
3. **Update the PRD draft** with the answers as Constraints (and remove
   the corresponding Open Questions). Resolve the Constraints↔Open-
   Questions contradictions in the same pass.
4. **Decide v1 scope sentence in one sentence**, agreed by the product
   owner. If Tier-1 answers favor the legs' recommended cuts: *"An
   offline-only iOS+Android Mood Meter check-in app with journaling,
   daily reminders, a 30-day calendar heatmap, full GDPR export, and a
   static crisis-support link."*
5. **Begin Phase 0 only after** the Yale-licensing path is settled and
   a SQLCipher-in-Expo spike has produced a green EAS Build.
6. **Then proceed** to design legs (`hwf-w1t`) and the alignment +
   self-review rounds in `mol-idea-to-plan`.
