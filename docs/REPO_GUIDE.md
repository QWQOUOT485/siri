# Repository Guide

這份文件只回答一件事：**第一次進這個 repo，應該先看哪裡。**

## Start Here

依序閱讀：

1. `AGENTS.md` — coding agent 規則與文件優先級
2. `PROJECT_STATUS.md` — 現在做到哪、哪些還沒驗收
3. `docs/SECURITY.md` — 不可突破的安全界線
4. `TASKS.md` — 現在真正的工作順序
5. 任務相關規格

不要從 `docs/SOURCE_SPEC.md` 推導目前行為；它是唯讀歷史快照。

## Repository Map

```text
app/
  domain/      closed actions、trusted domain models
  services/    parser、matching、Spotify、Local AI orchestration
  adapters/    Windows / Spotify / LM Studio 等外部系統邊界
  api/         HTTP request/response boundary
  main.py      Agent startup

config/        local allowlists / aliases / non-secret configuration
scripts/       setup、start、startup、uninstall、diagnostics
tests/
  unit/        mocked deterministic/security regressions
  integration_windows/
               real Windows safe/read-only integration checks

docs/
  SECURITY.md          highest-priority invariants
  SPEC.md              active product requirements
  ARCHITECTURE.md      active architecture
  API.md               HTTP contract
  WINDOWS.md           Windows runtime/adapters
  NETWORKING.md        LAN/firewall rules
  SPOTIFY.md           Spotify integration
  PLAYBACK_CONTROLS.md deterministic playback-state controls
  SIRI_SHORTCUT.md     current iPhone Shortcut flow
  semantic_recovery/   approved semantic-memory design
  LOCAL_AI_*           Local AI design/review/benchmark material
  SOURCE_SPEC.md       historical read-only source snapshot
```

## Main Runtime Flow

```text
Siri / Shortcut
→ HTTP API
→ authentication + network policy
→ deterministic parser
→ ValidatedAction
→ trusted service / catalog object
→ Windows or Spotify adapter
```

For guarded Spotify semantic retry:

```text
original utterance
→ deterministic parser/resolver
→ eligibility gate
→ Local AI
→ strict schema
→ deterministic grounding
→ policy gate
→ ValidatedAction
→ deterministic Spotify resolver
```

Local AI is never an execution engine.

## Where To Work

### Windows app control

Read:

- `docs/SECURITY.md`
- `docs/WINDOWS.md`
- `docs/ARCHITECTURE.md`

Preserve:

`ValidatedAction → Trusted AppEntry → LaunchSpec → Windows adapter`

### Spotify

Read:

- `docs/SPOTIFY.md`
- `docs/PLAYBACK_CONTROLS.md`
- `docs/SECURITY.md`

Track/artist/album text is search data only. Client input must never become a trusted Spotify URI, arbitrary endpoint or execution target.

### Siri Shortcut

Read:

- `docs/SIRI_SHORTCUT.md`
- `PROJECT_STATUS.md`

The accepted clarification flow depends on the server-owned token and second dictation within the same Shortcut run.

### Local Semantic Recovery

Read all of:

- `docs/semantic_recovery/README.md`
- `docs/semantic_recovery/RECOVERY_PIPELINE.md`
- `docs/semantic_recovery/MEMORY_MODEL.md`
- `docs/semantic_recovery/SECURITY.md`
- `docs/semantic_recovery/IMPLEMENTATION_PLAN.md`
- `docs/semantic_recovery/TESTING.md`

Only exact confirmed non-conflicted aliases may auto-canonicalize in Phase 1.

### Local AI

Start with current active rules:

- `docs/SECURITY.md`
- `docs/ARCHITECTURE.md`
- `PROJECT_STATUS.md`

Then use the Local AI proposal/review/runbook as supporting design/evidence.

Current production-facing scope is intentionally narrow: `spotify_play_track` / `unknown`. Do not re-expand old proposal text into playback controls, clarification or system actions.

## Test Meaning

Do not treat all green tests as the same kind of acceptance.

- unit/security tests = source behavior evidence
- Windows integration tests = real Windows safe integration evidence
- controlled Windows runtime = deployed Agent evidence
- Spotify real-account tests = external API/account evidence
- Siri Shortcut E2E = actual iPhone voice flow evidence

`PROJECT_STATUS.md` must keep those levels separate.

## Before Finishing A Change

- run relevant tests from `docs/TESTING.md`
- check security invariants
- do not expose secrets
- if real project state changed, update `PROJECT_STATUS.md`
- remove stale next steps instead of appending another chronological status block
