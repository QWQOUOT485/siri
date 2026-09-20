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

The source also parses a bounded provider `error.reason` in
`SpotifyApiError`, but the service's generic 403 mapping currently returns
only `SPOTIFY_FORBIDDEN` and drops that reason. The installed audit log has
the same bounded generic error code, so it cannot distinguish Premium,
device, content, or playback-state causes.

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

## Hypothesis result

- **External playback state / device / account condition — remains most
  likely.** The current live state had no active device, and historical
  failures are specific to empty-body resume while named-track playback and
  other controls succeeded. The exact historical provider reason remains
  unknown.
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
observability change is now reviewed, merged, and deployed to the installed
Agent, but the active-device precondition was absent, so no live 403 reason was
captured. Restore or identify a known active, non-restricted Spotify Desktop
device, then permit one bounded real resume acceptance. Stop immediately on
429 or `QUOTA_EXCEEDED`; do not retry or sleep.

Until then, keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false`; do not claim Siri voice acceptance or a
fixed resume path.
