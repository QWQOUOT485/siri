# Current Tasks

## Current Milestone

**v1.1 Candidate Recovery Phase 1B — source merged; continuation runtime gate not accepted**

The v1.0.0 runtime release-cut gate and installed identity acceptance passed for
the reviewed deterministic scope. The v1.0.0 release commit and annotated tag
target is `f1c201ddc2e9866ae46befd279c04c61921ad586`, after evidence-only PR
#33 merged.
The annotated `v1.0.0` tag targets that commit, and the GitHub Release
`Windows Siri Agent v1.0.0` is published. Source and installed identity report
`1.0.0`; the release evidence records source/installed full pytest at 307
passed, 161 release-controlled files with zero missing or SHA-256 mismatches,
and installed `/health` plus OpenAPI version `1.0.0`.

Core Siri → Windows → Spotify playback and clarification are functional. The
v1.0 scope freeze was accepted when PR #29 merged into `main`; its retained
scope, `spotify_continue` known limitation, proposed blockers, and v1.1
deferrals remain recorded in `docs/V1_SCOPE_FREEZE_2026-09-20.md`. Candidate
Recovery Phase 1B source implementation was merged to `main` by PR #35
(`dde5e07130517dcaa67d9136ad222f748930545f`). The tested current `main` is
`fcb955a43b0590636f776ffc31e7ca71897114f2`.

Installed alignment and regression passed, and the initial real trusted
clarification plus explicit playback passed. The bounded continuation runtime
gate remains **BLOCKED / NOT ACCEPTED**: live `都不是` returned
`SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a next page or token
rotation. This does not prove a source bug. Siri voice acceptance was not
performed; Semantic Memory remains disabled; Local AI fallback remains
unapproved. The detailed evidence boundary is recorded in
`docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.

## v1.0.0 Release Identity Cut

- Runtime release-cut gate: **PASSED** for the reviewed deterministic scope.
- Source product version is now `1.0.0`.
- Installed `1.0.0` deployment, source/runtime parity, `/health`, and OpenAPI
  identity acceptance **PASSED**.
- The annotated `v1.0.0` tag targets
  `f1c201ddc2e9866ae46befd279c04c61921ad586`, and the formal GitHub Release
  `Windows Siri Agent v1.0.0` is published.
- Evidence-only PR #33 is merged as
  `f1c201ddc2e9866ae46befd279c04c61921ad586`.
- `spotify_continue` remains **NOT ACCEPTED**.
- `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false` remain unchanged.
- Hosted CI remains absent and is not being added in this docs-only change.

## v1.0 Scope Freeze Decision

- Retain the Windows security boundary, API key/LAN-only operation, trusted app
  control, shutdown confirmation, Windows volume, Spotify basic/named-track
  playback, clarification, shuffle/repeat, and installed regression evidence.
- Keep `spotify_continue` deterministic and fail-closed, but mark it
  **NOT ACCEPTED** because the active-device real run returned
  `SPOTIFY_FORBIDDEN` with sanitized `provider_reason=UNKNOWN`.
- Treat Top-Artist-only and Recently-Played-only acceptance gaps as optional
  evidence, not v1.0 blockers.
- Defer seek, Spotify device volume, like/unlike, preference memory, and broader
  Local AI authority to a separately approved scope. Candidate Recovery Phase
  1B source is merged via PR #35; its installed/runtime continuation gate is a
  separate acceptance boundary and remains not accepted.
- Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false`.

## Before Coding

1. Read `AGENTS.md`.
2. Read `PROJECT_STATUS.md`.
3. Read `docs/SECURITY.md`.
4. Read `docs/SPEC.md` and `docs/ARCHITECTURE.md`.
5. Read task-specific docs:
   - Spotify → `docs/SPOTIFY.md`
   - playback controls → `docs/PLAYBACK_CONTROLS.md`
   - Local AI → `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` plus current SECURITY / ARCHITECTURE rules
   - semantic recovery → `docs/semantic_recovery/`
   - Windows adapters → `docs/WINDOWS.md`
   - API → `docs/API.md`
   - Siri → `docs/SIRI_SHORTCUT.md`
6. Before finishing, run relevant tests per `docs/TESTING.md`.
7. If real project state changed, update `PROJECT_STATUS.md`.

## Post-freeze Queue

### P0 — Preserve safety and release evidence

- No user text may become shell/subprocess/PowerShell/CMD/executable
  path/arbitrary URL.
- Local AI remains off/shadow and semantic memory remains disabled.
- Clarification tokens and trusted Spotify IDs remain server-owned.
- Do not turn candidate-quality signals into automatic execution authority.
- Do not delete security regressions to make tests pass.
- Keep source/unit, installed, and real-device evidence explicitly separate.

### P1 — v1.1 candidates and current Phase 1B slice

- `spotify_seek`
- Spotify device volume
- `spotify_like_current` / `spotify_unlike_current`
- Candidate Recovery Phase 1B — **source merged via PR #35; continuation runtime
  acceptance BLOCKED / NOT ACCEPTED**
- preference memory
- broader Local AI authority or executable fallback

The other listed items require a separately scoped v1.1 decision and branch.
Phase 1B source/unit work is merged to `main`. Installed alignment/regression
and the initial trusted clarification plus explicit playback passed, but the
bounded continuation returned `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED`
without a next page or token rotation, so continuation remains
**BLOCKED / NOT ACCEPTED**. Installed/runtime evidence is not Siri voice
acceptance; Siri voice acceptance was not performed.

### P2 — Optional evidence, not a v1.0 blocker

- Top-Artist-only genuine-ambiguity reordering
- Recently-Played-only genuine-ambiguity reordering
- Siri voice / independent speaker acceptance for exact Windows volume

Keep Spotify relevance/popularity and personalization signals as bounded
candidate evidence only.

### P2.5 — Local AI decision-head research PoC

Research a Jev-like / non-generative local decision model using a small Qwen
backbone. This is an evaluation task only and must not change production Local
AI authority or set `LOCAL_AI_FALLBACK_APPROVED=true`.

Primary references / approaches to investigate:

- `jaredpalmer/kev`: small Qwen backbone + LoRA + decision/readout head
- `Mapika/decider`: Qwen-based one-forward-pass probabilistic decision model
- `LitJev`: logits-based Jev-style decision experiments without full text generation

Initial experiment scope:

- Start with approximately 0.5B–2B Qwen-class models; do not assume a larger
  model is better.
- Target only the current narrow Local AI domain:
  `spotify_play_track` vs `unknown`, plus bounded track / artist / album
  semantic recovery where the architecture safely permits it.
- Compare the current generative structured-output baseline against a
  non-generative decision-head approach.
- Reuse the existing frozen 109-case Local AI benchmark/evaluation harness where
  possible; do not train on the held-out benchmark answers.
- Measure at least: strict-schema/typed-output success, supported semantic
  accuracy, semantic-retry accuracy, safe-unknown behavior, false execution,
  post-grounding false acceptance, P50/P95 latency, malformed-output rate, and
  timeout/failure behavior.
- If a decision head produces probabilities/confidence, evaluate calibration;
  confidence must remain evidence only and must not become execution authority.
- Build any training corpus from reviewed/sanitized examples, with separate
  training/validation/frozen-evaluation splits.
- Keep secrets, OAuth tokens, private paths, Spotify IDs/URIs, and raw sensitive
  logs out of training data.
- Prefer a parameter-efficient experiment (LoRA/QLoRA or similarly bounded
  tuning) that fits a single consumer GPU in the roughly 12–16 GB VRAM class.
- Do not introduce mixed-vendor cross-host distributed training for the first
  PoC.
- Any candidate that beats the baseline must still pass the existing grounding,
  policy, fail-closed, shadow, and independent promotion gates before executable
  fallback can be considered.

Success criteria for the research task:

~~~text
same frozen evaluation corpus
+ measurable semantic or latency improvement
+ no safety regression
+ reproducible model / dataset / config identity
~~~

A larger parameter count by itself is not a success criterion.

### P3 — Project infrastructure

- Add hosted CI for unit/security tests if separately scheduled.
- Keep Windows/Spotify/Siri real acceptance separate from hosted CI claims.
- Keep `PROJECT_STATUS.md` concise; do not re-add chronological debug history.

## Current Acceptance Gaps

- `spotify_continue` is source-tested and implemented, but its only permitted active-device real run failed closed with `SPOTIFY_FORBIDDEN` / sanitized `provider_reason=UNKNOWN`; it remains a v1.0 known limitation and **NOT ACCEPTED**. See `docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`.
- Candidate Recovery Phase 1B initial trusted clarification and explicit
  playback passed after installed alignment, but the bounded live continuation
  returned `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a next page or
  token rotation. It remains **BLOCKED / NOT ACCEPTED**; this does not prove a
  source bug. See `docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.
- Exact Windows volume has installed runtime acceptance but not Siri voice / physical-speaker acceptance.
- Top-Artist-only and Recently-Played-only real-account ordering cases remain partial/unproven and are not v1.0 blockers.
- Semantic-memory runtime acceptance is incomplete; keep it disabled.
- Local AI production fallback remains unapproved; keep shadow/off.
- Hosted CI is not established; local source evidence must not be presented as hosted CI evidence.

## Definition of Done for v1

- all mandatory `docs/SECURITY.md` invariants remain enforced
- core Windows app control and Spotify named-track playback work
- Siri clarification E2E remains passing
- OAuth tokens and secrets remain local
- shutdown remains two-step
- no remote arbitrary execution path exists
- relevant unit/security tests pass
- Windows integration tests pass where required
- setup/start flow works on real Windows
- remaining v1-scoped Spotify controls are implemented or explicitly deferred by the scope-freeze decision
- Local AI is safely kept off/shadow; executable fallback is not part of this freeze
- semantic memory remains disabled until its separate runtime acceptance gate passes
- `PROJECT_STATUS.md` accurately distinguishes source completion from real acceptance
