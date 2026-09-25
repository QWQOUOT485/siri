# Spotify `continue` / `resume` 403 Diagnosis

Date: 2026-09-20

Decision: **`spotify_continue` remains NOT ACCEPTED; no source fix is proven
necessary.** The strongest current hypothesis is an external Spotify
playback-state, device, or account condition, but that is not a proven root
cause: the provider's concrete 403 reason was not captured by the installed
audit path. This branch records evidence only; it does not retry playback or
change control semantics.

## Scope and safety boundary

- The diagnosis started from current `main` at `20cbaf7` after the state-
  controls acceptance report was merged.
- No access token, refresh token, API key, device ID, track ID, Spotify URI,
  raw provider body, or private credential is recorded here.
- No queue rebuild, shuffle change, hidden transfer, fallback, or Siri
  Shortcut change was performed.
- The existing `repeat off -> resume` behavior remains unchanged.
- No live retry was issued after the bounded probe found no active device.

## Source path inspected

`SpotifyPlayer.continue_playback()` performs this fixed sequence:

```text
resolve device
→ transfer only when the selected device is inactive
→ PUT /me/player/repeat?state=off
→ PUT /me/player/play?device_id=<server-selected-device> with an empty body
```

The client only adds a request body when a trusted track is supplied. The
same `/me/player/play` operation is therefore used for both ordinary resume
and continue, while named-track playback supplies a trusted `uris` body.

The source parses a bounded provider `error.reason` in `SpotifyApiError`.
Before the observability fix was merged, the service's generic 403 mapping
returned only `SPOTIFY_FORBIDDEN` and dropped that reason; that historical
gap is why the earlier installed audit lines cannot distinguish Premium,
device, content, or playback-state causes. The reviewed fix now preserves a
validated bounded reason in `OperationResult.data.provider_reason` without
changing the user-visible error code or playback semantics.

## Reproduction and minimisation evidence

The deterministic mock transport loop was run against the real service,
player, and client composition. It asserted the user-visible failure and
request sequence:

```text
active device + repeat 204 + play 403
→ result SPOTIFY_FORBIDDEN
→ devices, repeat, play
→ PUT /me/player/play?device_id=<mock-device> with empty body
```

A differential loop then varied only the operation shape:

| Case | Result | Load-bearing request evidence |
| --- | --- | --- |
| `spotify_resume` | 403 / fail closed | active device, `PUT /me/player/play`, empty body |
| `spotify_continue` | 403 / fail closed | same resume request after repeat-off |
| named-track playback | 204 / success | same endpoint/device, trusted track body |

The active-device case reproduces without transfer, queue inspection, or
playback-state readback. This rules out transfer and queue composition as
necessary conditions in the source path, but it does not turn a mock 403 into
the provider's actual reason.

The official Spotify contract permits `device_id` and makes the playback
body fields optional, while documenting 403, Premium, and
`user-modify-playback-state` requirements. It also documents that a
restricted device accepts no Web API commands:

- [Start/Resume Playback](https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback)
- [Get Available Devices](https://developer.spotify.com/documentation/web-api/reference/get-a-users-available-devices)

Therefore the empty body is valid API usage; it is not, by itself, evidence
of a client-side malformed request.

## Installed evidence

Sanitized historical audit lines show the failure is not unique to the new
`continue` composition:

- `2026-09-19 14:55:52` — `spotify_resume` failed with
  `SPOTIFY_FORBIDDEN`; `14:56:09` named-track playback succeeded.
- `2026-09-19 17:35:53` — `spotify_resume` failed with
  `SPOTIFY_FORBIDDEN`; a later named-track playback succeeded.
- `2026-09-20 12:00:01` — shuffle-on and repeat-track succeeded;
  `12:00:14` continue failed with `SPOTIFY_FORBIDDEN`; repeat-context,
  repeat-off, shuffle-off, and final repeat restoration then succeeded.

The previous bounded acceptance readback showed repeat-off applied, shuffle
preserved, and playback still active after the failed combined operation.
It did not retry the resume portion and did not capture the provider body.

One new live diagnostic probe used the normal local token lifecycle without
printing token values. Spotify returned one usable device but zero active
devices at probe time. Because there was no active target, the probe sent no
resume request and did not transfer playback. It also observed no 429 or
`QUOTA_EXCEEDED` response.

## Follow-up after observability merge and deployment

PR #26 was reviewed and merged to `main` as `874a944`. The reviewed
non-secret source was staged to the installed Agent after a reversible local
backup; `.env`, local configuration, runtime data, logs, outputs, work data,
token storage, and the virtual environment were excluded from the staging
set. Installed verification passed with targeted Spotify/security tests at
169 passed, the full suite at 306 passed, compileall passed, pip check passed,
and loopback `/health` returned 200. Runtime settings remained Local AI
shadow with fallback approval false and semantic memory disabled.

A single bounded read-only live preflight through the installed token
lifecycle then found 1 usable non-restricted device and 0 active devices; the
server-selected device was inactive. No `spotify_continue`, transfer, retry,
or playback command was sent, so this follow-up captured no new provider 403
reason and does not change the NO-GO decision.

## Active-device acceptance after deployment

After the user manually opened Spotify Desktop and established a controllable
device, one new bounded acceptance was authorized against the installed Agent
from current `main` (`6c10311`). The run used one read-only preflight followed
by exactly one `spotify_continue` command; it did not use a retry, transfer,
direct provider control, or a second command.

Sanitized preflight state:

```text
device_count=1
usable_nonrestricted=1
active_nonrestricted=1
restricted=0
server_selected_exists=true
server_selected_active=true
repeat=off
shuffle=false
playback_is_playing=true
playback_has_item=true
```

The installed Agent received the Siri text `就一直播下去` once. The HTTP
transport returned 200, but the operation failed closed:

```text
success=false
action=spotify_continue
error_code=SPOTIFY_FORBIDDEN
data.provider_reason=UNKNOWN
```

`UNKNOWN` is the sanitized bounded provider-reason value; no raw provider
body, token, device ID, track ID, or credential was recorded. Because the
operation returned 403, no post-command playback readback was performed. The
selected device was already active, so no transfer was attempted. No 429 or
`QUOTA_EXCEEDED` response occurred. The local Agent was stopped afterward and
the loopback ports were closed.

## Hypothesis result

- **External playback state / device / account condition — remains most
  plausible, but not proven.** The new attempt had an active, usable,
  non-restricted selected device and still returned 403, so the earlier
  no-active-device observation is not sufficient to explain this failure.
  Historical failures remain specific to empty-body resume while named-track
  playback and other controls succeeded. The deployed bounded reason was
  `UNKNOWN`, which does not identify a provider-side cause.
- **Transfer or queue composition — not necessary.** An active-device mock
  reproduces the failure without either step.
- **Malformed request shape — not supported by current evidence.** The
  request uses an allowlisted endpoint, server-selected device ID, and an
  optional empty body accepted by the official contract.
- **Global missing scope/Premium — not established.** The token scope was
  present during the installed check, and the same runtime accepted repeat,
  shuffle, and named-track playback; this lowers but does not eliminate the
  possibility of an account-side policy condition.
- **Provider-reason observability gap — confirmed.** The client retains a
  bounded reason internally, but the public operation result and audit log
  discard it. No speculative source change was made without a captured live
  reason.

## Stop line and next evidence

`spotify_continue` is still **NOT ACCEPTED**. The bounded provider-reason
observability change is reviewed, merged, and deployed to the installed Agent.
The active-device precondition then passed, but the one permitted command still
returned `SPOTIFY_FORBIDDEN` with only the sanitized reason `UNKNOWN`; this
does not prove a source bug or a provider root cause. No retry or post-403
readback is authorized by this evidence. Stop immediately on 429 or
`QUOTA_EXCEEDED`; do not retry or sleep.

Until then, keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false`; do not claim Siri voice acceptance or a
fixed resume path.
