# Windows Siri Agent v1.0 Scope Freeze

Date: 2026-09-20
Acceptance status: Accepted when PR #29 merged into `main` (`c31a0ac0f59fa45a31a06991116845bebfb5b734`); docs-only, no implementation change
Freeze branch base: `f9f36695dfe092bca0cfeb21e8b15ea1044fd7c7`
Historical related merge: PR #28 (`4c66a9d`), evidence-only; no implementation change

## Decision

Freeze the v1.0 implementation scope around the deterministic, safety-gated
Windows Siri Agent and its accepted Spotify playback path. This document is a
release-scope decision, not a claim that every optional feature has real-world
acceptance.

The scope-freeze change is docs-only. It does not change source behavior,
retry Spotify playback, add a provider workaround, enable semantic memory, or
enable Local AI fallback.

## Evidence labels

- **Implemented** — the source path exists.
- **Source tested** — unit/security/compile or static evidence exists.
- **Installed tested** — the reviewed source was deployed and the installed
  host regression or smoke evidence exists.
- **Real-device accepted** — a bounded real Windows/Spotify or Siri run passed
  for the stated behavior.
- **Partial / known limitation** — evidence is useful but does not support a
  success claim.
- **Deferred** — deliberately outside the v1.0 release gate.

## Retain in v1.0

| Area | Current evidence boundary | v1.0 interpretation |
| --- | --- | --- |
| Windows security boundary, API key, LAN-only exposure, closed actions, local secrets | Implemented; source/security coverage and installed alignment exist | Release blocker: invariants must remain enforced. |
| App open/close and explicit force-close separation | Implemented; deterministic source/security coverage and installed runtime path exist | Release blocker: preserve trusted catalog/process boundaries. Destructive force-close is not performed as an acceptance shortcut. |
| Shutdown confirmation | Implemented and security-tested | Release blocker: two-step confirmation remains mandatory. No real shutdown is performed for acceptance. |
| Windows exact volume | Implemented; source tests and installed exact scalar path verified | Retain the exact deterministic path. Siri voice and independent physical-speaker checks remain unproven, but are not promoted to a scope-freeze blocker. |
| Spotify basic playback, resume, pause, and named-track playback | Implemented; source coverage, installed runtime alignment, and real playback evidence exist | Release blocker: keep trusted Spotify resolution and fail-closed provider errors. |
| Spotify clarification | Implemented; server-owned candidates/token flow and real Siri voice E2E previously passed | Release blocker: keep candidate selection server-owned and bounded. |
| Spotify shuffle on/off and repeat off/track/context | Implemented; source/unit coverage and installed bounded real-device acceptance passed | Release blocker: retain deterministic fixed endpoints and no client-supplied provider IDs. |
| Installed deployment and regression | PR #26 post-deployment installed-host verification recorded targeted Spotify/security tests (169 passed), installed full pytest (306 passed), compileall passed, pip check passed, and loopback `/health` HTTP 200. An earlier installed regression recorded 303 passed; that is historical evidence, not the latest installed full suite. | Release blocker: preserve the reviewed installation boundary and rerun the appropriate regression at release cut. |
| `spotify_continue` deterministic action | Implemented and source-tested, but real-device result is a known limitation below | Keep the action and its fail-closed semantics in v1.0; do not represent it as accepted playback. |

## v1.0 known limitations

### `spotify_continue`

The deterministic implementation performs repeat-off followed by resume and
preserves shuffle. A bounded real run had an active, usable, non-restricted
selected device and sent exactly one command. The operation still failed
closed with `SPOTIFY_FORBIDDEN` and sanitized `provider_reason=UNKNOWN`.

There was no retry, transfer, direct provider control, post-403 readback, or
429 / `QUOTA_EXCEEDED` response. No source bug or safe provider workaround is
proven. `spotify_continue` therefore remains **NOT ACCEPTED**, while the rest
of the accepted shuffle/repeat controls remain in scope. Do not bypass the
provider behavior for the release.

### Non-blocking known evidence / UX gaps

- Top-Artist-only genuine-ambiguity reordering has not been independently
  accepted.
- Recently Played has source/unit evidence but no qualifying recent-only
  real-account reorder case.
- Exact Windows volume still lacks Siri voice and independent speaker
  acceptance.
- Spotify OAuth callback behavior once showed a generic browser failure even
  though status and token storage succeeded; functionality works, but the UI
  and root cause remain unclarified.
- Clarification-store bounded-attempt and concurrency hardening is covered by
  source/unit tests, but a full Siri E2E was not rerun specifically because of
  that hardening.
- Spotify quota hardening and personalization cache have source/unit evidence,
  while real-provider evidence remains constrained by Development Mode quota
  and provider conditions. Mock/cache evidence is not real Spotify acceptance.

These boundaries remain active but are **not v1.0 release blockers**. They must
remain visible in status/reporting and must not be upgraded into blockers merely
to make the scope appear more complete.

## Deferred to v1.1

- Spotify seek.
- Spotify device volume.
- Like/unlike current track.
- Candidate Recovery Phase 1B; keep it deferred unless separately scheduled.
- Preference memory and broader personalization authority.
- Broader Local AI authority or executable fallback.

The Phase 1 semantic-memory source slice remains guarded and not release-
enabled. Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false`; Local AI may remain in its documented
shadow-only mode.

## Proposed v1.0 release blockers

1. Any regression of the mandatory `docs/SECURITY.md` invariants, including
   remote execution, arbitrary paths/URLs, public exposure, secret leakage,
   or shutdown confirmation bypass.
2. Failure of the deterministic core Windows path, named-track playback, or
   server-owned clarification flow on the reviewed installed runtime.
3. Failure of the required source/security regression or the release-cut
   installed deployment/health checks.
4. Enabling semantic memory or executable Local AI fallback without its
   separate acceptance and promotion gates.

The `spotify_continue` provider limitation, Top-Artist/Recently-Played
acceptance gaps, and the v1.1 feature list above are explicit scope decisions,
not reasons to add an unsafe workaround or to claim unproven acceptance.
