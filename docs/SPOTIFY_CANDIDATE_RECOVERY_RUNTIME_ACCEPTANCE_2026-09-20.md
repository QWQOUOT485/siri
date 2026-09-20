# Spotify Candidate Recovery Phase 1B Installed/Runtime Acceptance

Date: 2026-09-20
Installed target: `D:\\ai\\windows-siri-agent`
Evidence branch: `docs/phase1b-runtime-acceptance-20260920`

## Final conclusion

**Installed regression passed, but live Candidate Recovery acceptance is
blocked and remains unproven.**

The initial trusted clarification and one explicit playback path passed. The
bounded continuation request returned
`SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without rotating to a new token, so
the Phase 1B continuation gate is not accepted. No source fix was made during
this acceptance run. Siri voice acceptance was not performed.

## Source identity

- GitHub `main` tested: `fcb955a43b0590636f776ffc31e7ca71897114f2`.
- PR #35 merge commit: `dde5e07130517dcaa67d9136ad222f748930545f`.
- Reviewed Phase 1B head: `9e9fa551095cddc70e1ea907d44dc6ab2b06eac7`.
- Post-merge commits were docs-only `PROJECT_STATUS.md` handoff commits;
  no implementation commit appeared after PR #35.
- `v1.0.0` annotated tag object remained
  `dc882af5bd4acb051552a9067245677dca82540f`, targeting
  `f1c201ddc2e9866ae46befd279c04c61921ad586`.
- GitHub Release `v1.0.0` identity and publication metadata were unchanged.

## Deployment and parity

- A reversible backup was created at:
  `D:\\ai\\windows-siri-agent-deploy-backups\\20260920-225926-phase1b-before-runtime-acceptance`.
- The deployment manifest contained 158 tracked source-controlled files,
  excluding repository metadata/handoff files and protected local `config/`.
- Source files present in installed target: **158**.
- Missing files after deployment: **0**.
- SHA-256 mismatches after deployment: **0**.
- Phase 1B implementation files were all parity-clean:
  `app/adapters/spotify/catalog.py`,
  `app/adapters/spotify/client.py`,
  `app/services/spotify_clarification.py`, and
  `app/services/spotify_service.py`.
- `.env`, `config/`, `runtime/`, `logs/`, `outputs/`, `work/`, `.venv`, and
  secrets were not copied, deleted, or mirrored. Their presence and deployment
  metadata were stable across deployment.
- The installed token store remained present. A normal runtime auth lifecycle
  refreshed its local token JSON during acceptance; token contents were never
  read into the report.

## Installed regression

- Recovery/clarification + Spotify service: **49 passed**.
- Spotify catalog/client/auth/parser/player: **125 passed**.
- Semantic Memory Spotify integration: **3 passed**.
- API auth + action-schema security: **16 passed** (two existing dependency
  deprecation warnings).
- Full installed pytest: **336 passed**, two existing dependency warnings.
- Installed `compileall`: passed.
- Installed `pip check`: passed.
- No hosted CI is configured; these are local installed/source test results.

## Startup and loopback smoke

- Installed normal module startup completed without a traceback.
- `GET /health`: HTTP **200**.
- Health version: **1.0.0**.
- Health schema was exactly `ok`, `status`, `version`, and `uptime_seconds`.
- `GET /openapi.json`: HTTP **200**.
- OpenAPI `info.version`: **1.0.0**.
- Agent was stopped after the bounded runtime checks; port 8000 and target
  processes were no longer listening/running at final readback.

## Runtime flags and protected memory boundary

- Effective `semantic_memory_enabled`: **false**.
- Effective `LOCAL_AI_FALLBACK_APPROVED`: **false**.
- Effective Local AI mode during startup: **shadow**.
- Semantic Memory production database path existed: **false** before and after
  the runtime checks.
- Semantic Memory learning and second-occurrence alias acceptance: **not
  tested**. This gate did not enable production memory.
- Local AI promotion: unchanged and not performed.

## Provider preflight

- Local `/spotify/status`: authorized, with scope and expiry metadata present;
  no secret value was printed.
- The access token was expired/near expiry, so one bounded Accounts refresh was
  used without writing the refreshed token from the preflight helper.
- Exactly one read-only `GET /me/player/devices` preflight followed the
  refresh: one usable, active, non-restricted device was observed.
- Directly counted preflight provider calls: **2** (one Accounts refresh and one
  device read). Server-owned command search/playback calls are not exposed as a
  client-visible counter and were not fabricated as an exact number.
- Preflight and command flows observed no `429`, `QUOTA_EXCEEDED`, or `403`.
- `spotify_continue` was not tested.

## Candidate Recovery runtime result

### Safe parser boundary probe

Request: `播放 Sad overlxrd`

- Response: `SPOTIFY_LOW_CONFIDENCE_TRACK`.
- No clarification token or candidate page was returned.
- No playback occurred and no Spotify ID/URI was exposed.
- This was recorded as a safe fail-closed parser/resolver boundary, not as a
  Candidate Recovery pass.

### Initial candidate clarification and explicit selection

Request: `播放 Sad overlxrd 的 死亡不是生命的終點`

- Initial response: `SPOTIFY_CLARIFICATION_REQUIRED`.
- Public options: **2** (within the maximum of 3).
- The first option was the trusted `SASIOVERLXRD` candidate for
  `死亡不是生命的終點`; the second was a different artist candidate.
- Option fields contained only safe display metadata (`ordinal`, `label`,
  `track_name`, `artist_names`, `album_name`). No Spotify ID or URI was
  exposed.
- Initial token was opaque, present, and 43 characters long.
- No duplicate displayed labels were observed.
- No automatic playback occurred before selection.
- Explicit `第一首` selection played exactly the displayed first candidate.
- Replaying the consumed token failed closed with
  `SPOTIFY_CLARIFICATION_USED`.

Result: **PASS for initial clarification plus explicit trusted playback**.

### Bounded continuation attempt

The same known request was started again to exercise exactly one continuation;
no selection was sent in this flow.

- Initial page again contained 2 safe options and an opaque token.
- User-visible `都不是` returned
  `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED`.
- No new token was returned/rotated.
- No playback occurred.
- No Spotify ID/URI was exposed and no duplicate displayed labels were seen.
- No second continuation was attempted.

Result: **BLOCKED / NOT ACCEPTED for installed continuation recovery**.

## Siri boundary

`Siri voice acceptance not performed.` Windows HTTP/runtime evidence is not
represented as Siri E2E evidence.

## Scope and stop line

- No implementation source was modified during the acceptance run.
- No `spotify_continue`, seek, like/unlike, repeat/shuffle, transfer, device
  volume, or other unrelated Spotify feature was tested.
- No Semantic Memory production enablement, Local AI promotion, v1.0.0 tag,
  or GitHub Release change was made.
- Live acceptance stopped after the continuation exhaustion result; no retry or
  second continuation was used to force a pass.

