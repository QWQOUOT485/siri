# Current Tasks

## Current Milestone

Verify release-cut readiness for the accepted Windows Siri Agent v1.0 scope
without weakening the deterministic security boundary.

Core Siri → Windows → Spotify playback and clarification are functional. The
v1.0 scope freeze was accepted when PR #29 merged into `main`; its retained
scope, `spotify_continue` known limitation, proposed blockers, and v1.1
deferrals are recorded in
`docs/V1_SCOPE_FREEZE_2026-09-20.md`. This phase is release-cut verification
and documentation cleanup only; do not add a source workaround or a new live
Spotify retry.

## v1.0 Scope Freeze Decision

- Retain the Windows security boundary, API key/LAN-only operation, trusted app
  control, shutdown confirmation, Windows volume, Spotify basic/named-track
  playback, clarification, shuffle/repeat, and installed regression evidence.
- Keep `spotify_continue` deterministic and fail-closed, but mark it
  **NOT ACCEPTED** because the active-device real run returned
  `SPOTIFY_FORBIDDEN` with sanitized `provider_reason=UNKNOWN`.
- Treat Top-Artist-only and Recently-Played-only acceptance gaps as optional
  evidence, not v1.0 blockers.
- Defer seek, Spotify device volume, like/unlike, Candidate Recovery Phase 1B,
  preference memory, and broader Local AI authority to v1.1 or a separately
  approved scope.
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

### P1 — v1.1 candidates, only with a separate decision

- `spotify_seek`
- Spotify device volume
- `spotify_like_current` / `spotify_unlike_current`
- Candidate Recovery Phase 1B
- preference memory
- broader Local AI authority or executable fallback

These are not to be implemented as part of the v1.0 scope-freeze PR.

### P2 — Optional evidence, not a v1.0 blocker

- Top-Artist-only genuine-ambiguity reordering
- Recently-Played-only genuine-ambiguity reordering
- Siri voice / independent speaker acceptance for exact Windows volume

Keep Spotify relevance/popularity and personalization signals as bounded
candidate evidence only.

### P3 — Project infrastructure

- Add hosted CI for unit/security tests if separately scheduled.
- Keep Windows/Spotify/Siri real acceptance separate from hosted CI claims.
- Keep `PROJECT_STATUS.md` concise; do not re-add chronological debug history.

## Current Acceptance Gaps

- `spotify_continue` is source-tested and implemented, but its only permitted active-device real run failed closed with `SPOTIFY_FORBIDDEN` / sanitized `provider_reason=UNKNOWN`; it remains a v1.0 known limitation and **NOT ACCEPTED**. See `docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`.
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
