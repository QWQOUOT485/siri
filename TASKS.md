# Current Tasks

## Current Milestone

Finish Windows Siri Agent v1 without weakening the deterministic security boundary.

Core Siri → Windows → Spotify playback and clarification are already functional. Current work is **quality, remaining deterministic controls, semantic memory, and Local AI promotion evidence** — not rebuilding the project skeleton.

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

## Priority Queue

### P0 — Preserve safety

- No user text may become shell/subprocess/PowerShell/CMD/executable path/arbitrary URL.
- Local AI remains off/shadow unless a separate promotion gate is completed.
- Clarification tokens and trusted Spotify IDs remain server-owned.
- Do not turn candidate-quality signals into automatic execution authority.
- Do not delete security regressions to make tests pass.

### P1 — Spotify candidate quality

1. Complete a genuine-ambiguity real-account acceptance case for saved/liked ranking.
2. Validate the implemented Top Tracks / Top Artists signal after `user-top-read` reauthorization; it must improve ordering without overriding explicit metadata or ambiguity safety.
3. Add Recently Played signal under the same rule.
4. Keep Spotify Search relevance / popularity as lower-priority evidence only.

### P2 — Deterministic playback-state controls

Implement and test closed actions from `docs/PLAYBACK_CONTROLS.md`:

- `spotify_shuffle_on` / `spotify_shuffle_off`
- `spotify_repeat_off` / `spotify_repeat_track` / `spotify_repeat_context`
- `spotify_continue`
- `spotify_seek`
- `spotify_set_volume`
- `spotify_like_current` / `spotify_unlike_current`

Requirements:

- no arbitrary Spotify endpoint / body / device ID / track ID / URI from the client
- like/unlike operates only on server-read current track
- these actions remain deterministic-only and outside Local AI

### P3 — Local Semantic Recovery Phase 1

Implement the approved exact-confirmed-alias design:

- EntityNormalizer
- SQLite persistence
- confirmed-alias RAM index
- candidate-only RapidFuzz path
- MemoryLearner
- conflict handling / poisoning tests
- fail-open-to-existing-deterministic behavior on DB failure

Promotion to confirmed alias requires server-owned clarification selection followed by successful playback.

### P4 — Local AI promotion preparation

Do **not** enable executable fallback yet.

Required work:

1. reconcile any stale broad AI wording with the current narrow `spotify_play_track / unknown` contract
2. produce a sanitized committed benchmark evidence summary tied to exact commit/model/config
3. run production-loopback shadow acceptance on real Windows Agent
4. verify hostile input, timeout, busy/unavailable model and malformed output all fail closed
5. verify deterministic commands and clarification remain unchanged
6. run separate independent promotion review

Only after all gates pass may `LOCAL_AI_FALLBACK_APPROVED=true` be considered.

### P5 — Project infrastructure

- Add hosted CI for unit/security tests if practical.
- Keep Windows/Spotify/Siri real acceptance separate from hosted CI claims.
- Keep `PROJECT_STATUS.md` concise; do not re-add chronological debug history.

## Current Acceptance Gaps

- saved=true has been verified against a real Spotify account, but its effect on a genuine ambiguity ordering case is not yet accepted.
- Top Tracks / Top Artists source ranking is implemented and covered, but real-account acceptance is pending `user-top-read` reauthorization; Recently Played is not implemented.
- Spotify extended playback controls above are not complete.
- exact Windows volume has Windows runtime acceptance but not Siri voice / physical-speaker acceptance.
- Local Semantic Recovery Phase 1 is approved but not complete.
- Local AI production fallback remains unapproved.
- GitHub currently has no hosted workflow/status evidence for HEAD.

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
- remaining v1-scoped Spotify controls are implemented or explicitly deferred by product decision
- Local AI is either safely kept off/shadow or separately promoted through the documented gate
- `PROJECT_STATUS.md` accurately distinguishes source completion from real acceptance
