# Spotify Playback-State Controls — Installed Runtime Acceptance

Date: 2026-09-20

Decision: **PARTIAL ACCEPTANCE / NO-GO for `spotify_continue`**

This report records a bounded run against the installed Agent after aligning
the non-secret source from commit `485c949` to
`D:\ai\windows-siri-agent`. It does not change the Local AI or semantic
memory gates, and it does not claim Siri voice acceptance.

## Deployment and safety boundary

- The installed Agent was run only on loopback `127.0.0.1:18000` with startup
  catalog refresh disabled.
- The source parity check covered 157 app/scripts/tests/docs/metadata files and
  found no differences after staging.
- The installed `.env`, local YAML config, app cache, logs, Spotify token
  store, runtime data, work files, outputs, and virtual environment were not
  overwritten by the alignment. Existing installed code was copied to a local
  acceptance backup before staging.
- Effective runtime settings remained semantic memory disabled, fuzzy memory
  auto-retry disabled, Local AI shadow mode, and
  `LOCAL_AI_FALLBACK_APPROVED=false`. No semantic-memory SQLite file was
  created.
- Installed-host checks passed: full pytest **303 passed**, compileall passed,
  pip check passed, and loopback `/health` returned HTTP 200.
- The live run used the existing local token lifecycle. The token file was
  preserved during alignment; its JSON may be rewritten by the normal local
  refresh path during an authorized Spotify call. No token value is recorded.

## Real Spotify sequence

The initial read-only state had one active device, a current playing item,
`shuffle=false`, and `repeat=track`. The sequence was sent through the
installed Agent `/command` endpoint using only closed natural-language
commands:

| Command | Result | Observed evidence |
| --- | --- | --- |
| 開啟隨機播放 | PASS | action `spotify_shuffle_on`; readback `shuffle=true` |
| 單曲循環 | PASS | action `spotify_repeat_track`; readback `repeat=track` |
| 就一直播下去 | **FAIL-CLOSED** | action `spotify_continue`; `SPOTIFY_FORBIDDEN` |
| 後續 readback | PARTIAL | `repeat=off`, `shuffle=true`, still playing; no retry was sent |
| 循環播放清單 | PASS | action `spotify_repeat_context` |
| 關閉循環 | PASS | action `spotify_repeat_off` |
| 關閉隨機播放 | PASS | action `spotify_shuffle_off`; readback `shuffle=false`, `repeat=off` |
| restore initial repeat | PASS | action `spotify_repeat_track` |

The `spotify_continue` implementation performs repeat-off before resume. The
readback proves the repeat-off part and unchanged shuffle state, but the Agent
returned `SPOTIFY_FORBIDDEN` for the bounded operation, so the combined
continue control is not accepted. It was not retried. The final readback after
restoration was `shuffle=false`, `repeat=track`, with playback still active.

No `429`, `QUOTA_EXCEEDED`, or rate-limit log line occurred in this run. If a
quota/rate-limit response occurs, the client/service path is required to fail
fast without retry; the source/unit suite covers that boundary. The installed
control requests were logged as Local AI `unsupported_domain` and remained on
the deterministic path.

## Remaining acceptance gates

- Diagnose the real Spotify/device/account reason for the `start/resume`
  portion of `spotify_continue` returning `403`, then run a new bounded
  acceptance only after that blocker is understood.
- Siri/iPhone voice E2E was not run, and no Shortcut trust-boundary change was
  made.
- `spotify_seek`, Spotify device volume, and like/unlike remain unimplemented
  in this batch.
- Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false`.
