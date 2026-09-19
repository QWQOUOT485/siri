# Windows Siri Agent Architecture

How should this system be designed? Preserve the v2 architecture completely.

## Layer Architecture

```text
API Layer (FastAPI routes)
  → validation, serialization, call services; no direct Windows operations
    ↓
Infrastructure (auth / rate_limit / config / logging)
  → cross-cutting concerns, not domain core logic
    ↓
Service Layer (orchestration)
  → CommandService → Parser → Matcher → AppService → Adapter
    ↓
Domain Layer (pure data models and rules, no Windows dependency)
  → actions.py / app_models.py / matching.py
  → This layer can be fully unit tested without real Windows
    ↓
Windows Adapter Layer (only place touching Windows API)
  → discovery / launcher / process / media / volume / system / firewall
  → Only operates in current logged-in user's interactive session
  → Only this layer (and some integration tests) needs real Windows verification
    ↓
Current logged-in Interactive User Session
    ↓
Windows System
```

**Key modification:** Agent itself must run in current user's interactive desktop session (Task Scheduler At log on, not SYSTEM / not regular Windows Service).

## Layer Responsibilities

- **API Layer**: validation, serialization, call services. No direct Windows operations.
- **Infrastructure**: auth (constant-time compare, no log key), rate_limit (middleware, not domain), config (.env, allowed_networks, websites, manual_apps), logging (no secrets).
- **Service Layer**: orchestration. CommandService → Parser → Matcher → AppService → Adapter. ShutdownService for token lifecycle. AppService for catalog queries, refresh, AppEntry→LaunchSpec.
- **Domain Layer**: Pure data models, no Windows import. Actions enum, AppEntry/LaunchSpec/ProcessSpec models, matching logic (normalize + alias + token/prefix + fuzzy + confidence).
- **Windows Adapter Layer**: Only place touching Windows API. All operate targeting current interactive user session. Abstract interfaces for test injection.

## Dependency Inversion

Domain has no Windows dependency. Windows Adapters implement abstract interfaces defined in `base.py`. Services orchestrate between Domain and Adapters.

## Key Data Models

- **AppEntry**: display_name, normalized_name, aliases, launch_method, launch_target, executable path (from trusted sources), process info, source, app type, AUMID, shortcut path, confidence, launch_source (Trusted/Metadata-only), launch_confidence, metadata_confidence.
- **LaunchSpec**: Built by Catalog from AppEntry. Windows Adapter only accepts this, not arbitrary strings.
- **ProcessSpec**: Process hints for Running Application Resolver.
- **stable app_id**: Matcher uses app_id after finding app, avoids repeated name matching.

## Application Discovery Source Classification

**A. Trusted Launch Sources** (can be used as launch targets):
- Start Menu .lnk (Current User / All Users)
- Registry App Paths
- Windows AppsFolder
- UWP / packaged app AUMID
- Windows system_apps mapping (well-known system targets)
- User's local manual_apps config

**B. Metadata-only Sources** (supplementary info only, NOT launch targets):
- Installed Programs Registry / Uninstall Registry
- Publisher / Version / Install Location metadata
- Other sources without clear launch contract

## Catalog

In-memory catalog using stable app_id. Bridges services and adapters.

## Matcher

normalize + alias + token/prefix + fuzzy + confidence ranking. Search priority: exact alias → exact normalized → strong prefix/token → fuzzy → ambiguous candidates.

## Running Application Resolver

Not just 'app name → process name → kill'. Flow:
1. Catalog process hints / executable identity
2. Current logged-in user session
3. Top-level windows / associated process tree
4. Graceful Close (WM_CLOSE)
5. Wait reasonable timeout
6. Check result
7. If still exists, report failure (don't force close)

Force Close is separate explicit operation.

## Firewall Responsibility

- Runtime: inspect only (`inspect_network_profile()`, `inspect_firewall_rule()`)
- `setup.ps1`: create/remove rules only with explicit user consent
- Private Profile only
- Never auto-modify network profile, Router, NAT, Port Forwarding, UPnP

## Rate Limiter Placement

Belongs in API/infrastructure layer (middleware), not domain/service logic.

## system_apps Mapping

Windows built-in tools (Task Manager, Settings, Calculator, etc.) maintained as well-known system targets. Trusted Launch Source. Not dependent on general Discovery. Not 'hardcoding all apps'.

## Spotify Music Control

Spotify is the only V1 provider for named-track playback.

Architecture:

```text
Siri text
  ↓
Rule-based Parser
  ↓
ValidatedAction(spotify_play_track, track, optional artist/album hint)
  ↓
SpotifyService
  ├─ SpotifyAuth / token refresh
  ├─ SpotifyCatalog search
  ├─ match / ambiguity check
  └─ SpotifyPlayer device + playback
  ↓
Spotify Web API
  ↓
Spotify Connect device on Windows
```

The Spotify integration is separate from the generic Windows launcher. Song title, artist, and the optional album/version hint are untrusted search text and may only enter the Spotify search request. They must never be used as an executable path, shell command, command-line argument, process ID, or arbitrary URL.

The service converts Spotify API results into trusted internal objects (for example `SpotifyTrackRef` containing Spotify track ID/URI and display metadata). Only those trusted objects may reach the playback method.

For playback, resolve the configured or active Spotify Connect device. If the desired Windows device is not active, the service may use Spotify's device-transfer capability. If no suitable device exists, optionally open Spotify Desktop through the existing Trusted AppEntry flow and return/retry safely.

Authorization uses OAuth Authorization Code with PKCE and least-privilege scopes; token handling belongs in infrastructure, not domain. See [SPOTIFY.md](SPOTIFY.md).


## Local Semantic Recovery / Alias Memory

Spotify named-track requests may pass through a local ASR/entity-recovery layer before Local AI.

```text
Siri text
→ deterministic parser
→ entity normalization
→ exact confirmed alias memory
→ deterministic Spotify resolver
→ fuzzy / track-first candidate evidence if unresolved
→ deterministic clarification
→ optional future vector evidence
→ Local AI semantic retry only if still eligible
```

Phase 1 authority rule: only an **exact confirmed non-conflicted alias** may automatically canonicalize an entity. Fuzzy similarity, track-first evidence, vector similarity and AI are not identity/execution authority.

Alias promotion is controlled by a single `MemoryLearner`; automatic confirmation requires a server-owned clarification selection followed by successful playback. Conflicted aliases leave the automatic fast path.

See [Local Semantic Recovery](semantic_recovery/README.md) for the implementation specification.

## Local AI Semantic Fallback (V1 allowed, not currently enabled)

The Phase 0.5 benchmark did not produce a model that met the project safety and
quality thresholds. Therefore `LOCAL_AI_ENABLED=false` remains the default and
no model is approved for production fallback. The architecture below is the
smallest future integration shape; it does not authorize implementation or
execution by itself.

The first AI integration may interpret only free-form Spotify named-track
requests. It may also be invoked as a **semantic retry** when the deterministic
parser produced a plausible `spotify_play_track` action but the deterministic
Spotify resolver returns no usable result, a low-confidence result, or another
explicitly defined signal of probable entity segmentation error. It must not
interpret playback controls, clarification selection, application commands, or
system actions.

```text
Siri text
  ↓
Rule-based Parser
  ├─ confident supported command → ValidatedAction
  ├─ clarification_token present → deterministic server-owned selection
  └─ eligible Spotify semantic-retry case
       (parser miss OR parser produced spotify_play_track but
        deterministic Spotify resolution indicates no-result /
        low-confidence / probable entity split)
          ↓
     RawAIIntent (untrusted)
          ↓
     strict schema validation
          ↓
     deterministic SemanticGrounder
          ↓
     AIPolicyGate
          ↓
     ValidatedAction or unknown
          ↓
     existing deterministic Spotify resolver
          ↓
     trusted SpotifyTrackRef
          ↓
     SpotifyPlayer
```

V1 Local AI constraints:

- rule parser remains first; AI is permitted only after a deterministic eligibility gate
- AI eligibility may include a deterministic `spotify_play_track` parse that later fails safe resolution; parser success alone is not proof that artist/track segmentation was semantically correct
- example: `播放死亡是生命的終點` may be syntactically split as artist=`死亡是生命`, track=`終點`; if deterministic Spotify resolution cannot support that parse, shadow/future fallback may ask AI to reinterpret the original utterance
- initial AI schema allows only `spotify_play_track` and `unknown`
- `track` is required and must be grounded in the original utterance; ungrounded `track` invalidates the interpretation
- ungrounded optional `artist` / `album` are forced to `null`
- the first integration does not send clarification candidates or `clarification_token` to AI; an incoming token always uses the existing deterministic clarification store
- AI does not parse `spotify_pause`, `spotify_resume`, `spotify_next`, `spotify_previous`, app actions, volume, shutdown, force-close, firewall, or system administration
- AI output never becomes a `ValidatedAction` until schema validation, grounding, and policy checks complete
- no executable path, shell command, URL, process ID, Spotify URI/track ID, token, or trusted catalog object may appear in the AI schema
- production LM Studio access is loopback-only; a non-loopback configured endpoint must fail closed rather than silently falling back to LAN
- no cloud LLM fallback, silent model download, or remote configuration of model/backend/base URL
- timeout, connection failure, malformed output, or policy rejection preserves the deterministic behavior and never creates an action
- the current implementation defaults to `LOCAL_AI_ENABLED=false` / `LOCAL_AI_MODE=off`; `shadow` may record bounded diagnostics but never returns an executable action
- `fallback` remains behind the local `LOCAL_AI_FALLBACK_APPROVED` promotion gate and is not production-approved by the current benchmark result
- enabling execution requires a new measured benchmark after the revised prompt/grounding design; the Phase 0.5 result is not sufficient

See [LOCAL_AI_ARCHITECTURE_PROPOSAL.md](LOCAL_AI_ARCHITECTURE_PROPOSAL.md) for
the reviewed design and deferred options.

## Next Optimization Priorities

After the successful Siri clarification E2E, implementation work should proceed in this order.

### Priority 1 — Spotify candidate quality

This is the highest-impact current UX issue. Bare or ambiguous song titles can return obscure candidates even though the clarification mechanism itself now works.

Planned work:

- evaluate adding `market=TW` to Spotify Search requests for availability/relinking behavior; do not treat it as a Taiwan-popularity ranking signal
- preserve Spotify's original relevance order as an input signal instead of discarding it completely
- **Completed source slice:** query whether the existing top-three trusted ambiguity candidates are already saved in the user's Spotify Library and use that as the strongest personalization signal after explicit user intent; scope failure falls back to deterministic order
- **Completed source slice:** query the user's Top Tracks / Top Artists as a secondary personalization signal; real-account acceptance remains separate
- query Recently Played as a tertiary personalization signal
- use Spotify search relevance after explicit intent + saved/top/recent personalization
- evaluate popularity or another availability-safe popularity-like signal only as a final tie-breaker
- never let personalization/popularity override an explicitly provided artist, album, version intent, or genuine ambiguity
- same-title tracks from different plausible artists must still enter clarification rather than auto-play
- add regression fixtures for ambiguous Chinese song titles and common Traditional/Simplified variants
- verify any ranking change against real Spotify responses before calling it accepted

The target ranking signal order is:

```text
explicit user artist / album / version intent
→ deterministic title / identity / Live filtering
→ saved / liked in user's Library
→ user's Top Tracks / Top Artists
→ user's Recently Played
→ Spotify Search relevance
→ popularity-like tie-breaker only
```

The goal is better ordering of the 2–3 candidates the user sees, not less-safe automatic guessing. Personalization may promote a candidate within an otherwise valid set, but it must never override explicit intent or eliminate genuine ambiguity by itself.

Implementation note: personalization requires OAuth scopes `user-library-read`, `user-top-read`, and `user-read-recently-played`. Library membership uses the current read-only `GET /me/library/contains` endpoint against server-owned Spotify track URIs; Top Items uses `GET /me/top/{type}`; Recently Played uses `GET /me/player/recently-played`. These are local ranking signals only and must not be exposed as client-controlled fields. Existing users will need to re-authorize Spotify once after the new scopes are added.

### Priority 1B — Expanded Spotify controls and Library actions

Add deterministic closed actions for Spotify features already supported by the Web API:

```text
spotify_shuffle_on
spotify_shuffle_off
spotify_repeat_off
spotify_repeat_track
spotify_repeat_context
spotify_seek
spotify_set_volume
spotify_like_current
spotify_unlike_current
```

Initial natural-language examples:

```text
開啟隨機播放
關閉隨機播放
單曲循環
循環播放清單
關閉循環
跳到一分三十秒
Spotify 音量 50
喜歡這首
取消喜歡這首
```

Rules:

- playback-control values must be parsed into closed validated fields; never pass arbitrary query/body values from the client directly to Spotify
- seek position must be bounded to a validated non-negative millisecond value
- Spotify volume must be an integer 0–100 and is distinct from Windows master volume
- like/unlike operates only on the server-resolved currently playing Spotify track in the first implementation
- Library writes use Spotify's current `PUT /me/library` / `DELETE /me/library` endpoints and require `user-library-modify`
- these controls remain deterministic; do not route them through Local AI
- 401/403/429/runtime failure must return a bounded error and must not use shell/media-key fallbacks that change semantics

The existing `user-modify-playback-state` scope already covers shuffle/repeat/seek/Spotify-volume. Like/unlike adds `user-library-modify`.

### Priority 2 — Improve deterministic spoken-song parsing

Before expanding Local AI, improve the rule parser for common natural phrases that are easy to support deterministically.

Target examples include:

```text
幫我播周杰倫那首晴天
我想聽晴天
放一下周杰倫的晴天
來個周杰倫的晴天
```

Prefer explicit aliases/patterns when they can be implemented clearly and regression-tested. Do not use the LLM merely to replace simple deterministic grammar. However, do not keep adding ad-hoc grammar patches for open-ended entity-boundary ambiguity. When deterministic parsing looks valid but Spotify resolution shows no-result/low-confidence evidence, that case belongs in the AI semantic-retry/shadow corpus.

### Priority 3 — Keep the Siri Shortcut in the accepted stable shape

The accepted clarification flow is:

```text
第一輪語音
→ POST /command
→ 有 clarification_token？
   ├─ 是
   │  → 朗讀候選
   │  → 關閉 Siri 並繼續
   │  → 第二次聽寫
   │  → POST /command + clarification_token
   │  → 播放成功後結束
   └─ 否
      → 朗讀一般結果
```

Remove obsolete test-only actions, duplicate dictionary extraction, and duplicate Speak actions when maintaining the Shortcut. Do not move `Dismiss Siri and Continue` back to the start of the Shortcut; it belongs after candidate speech and immediately before the second dictation.

### Priority 4 — Rotate the exposed API key (completed 2026-09-19)

A previous troubleshooting screenshot exposed part of the API key. Rotate it before treating the current setup as cleaned up:

- generate a new high-entropy API key
- update the Windows Agent local configuration
- update the iPhone Shortcut header
- invalidate/remove the old key
- never commit or log either key

This rotation was completed for the installed Agent: the local key was
replaced, the iPhone Shortcut header was updated, the `.env` ACL was
restricted, and a fresh authenticated `/info` check passed after restarting
port 8000. Future rotations should repeat the same coordinated procedure.

### Priority 5 — Local AI stays gated

The completed Phase 0.5 benchmark did not meet the project's safety/quality acceptance thresholds. Do not wire Local AI into production `/command` execution yet. The first guarded semantic-retry skeleton now exists, but it remains off by default.

Next AI work should be:

```text
run the new strict schema / grounding / policy tests
→ run loopback-only shadow mode, including parser-success/resolver-failure cases
→ collect real Siri failure corpus
→ rerun benchmark
→ enable guarded fallback only if thresholds pass
```

Initial AI responsibility remains limited to free-form `spotify_play_track` semantic extraction. Existing deterministic Spotify clarification, playback controls, app control, volume, shutdown, force-close, firewall, and system-administration paths must remain outside the first AI execution scope.

## Directory Structure (v2)

```text
windows-siri-agent/
├── app/
│   ├── main.py
│   ├── runtime.py
│   ├── cli.py
│   ├── catalog.py
│   ├── api/
│   │   ├── routes_health.py
│   │   ├── routes_apps.py
│   │   ├── routes_action.py
│   │   ├── routes_command.py
│   │   ├── routes_spotify.py
│   │   └── schemas.py
│   ├── domain/
│   │   ├── actions.py
│   │   ├── app_models.py
│   │   ├── matching.py
│   │   ├── chinese.py
│   │   └── local_ai.py
│   ├── infrastructure/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── spotify_auth.py
│   ├── services/
│   │   ├── command_parser.py
│   │   ├── command_service.py
│   │   ├── ai_eligibility.py
│   │   ├── ai_policy.py
│   │   ├── local_ai_service.py
│   │   ├── semantic_grounder.py
│   │   ├── app_service.py
│   │   ├── shutdown_service.py
│   │   ├── spotify_service.py
│   │   └── spotify_clarification.py
│   └── adapters/
│       ├── local_ai.py
│       ├── spotify/
│       │   ├── base.py
│       │   ├── client.py
│       │   ├── catalog.py
│       │   └── player.py
│       └── windows/
│           ├── base.py
│           ├── discovery.py
│           ├── launcher.py
│           ├── process.py
│           ├── media.py
│           ├── volume.py
│           ├── system.py
│           └── firewall.py
├── tests/
│   ├── unit/
│   ├── integration_windows/
│   └── fixtures/
├── scripts/
│   ├── setup.ps1
│   ├── start.bat
│   ├── install-startup.ps1
│   ├── uninstall-startup.ps1
│   ├── uninstall.ps1
│   └── ai_model_poc.py
├── config/
├── docs/
├── .env.example
├── .gitignore
└── requirements.txt
```

This tree is descriptive, not a permission boundary. Security authority remains in the domain/service contracts and in `docs/SECURITY.md`.

## Key Design Decisions (v2)

1. **Interactive User Session 是架構的第一優先前提**：`main.py` 啟動時即偵測目前是否執行在 interactive user session，若否，log warning 並在 `/info` 標示 GUI launch 可能不正常。自動啟動一律採 Task Scheduler `At log on`（interactive user 模式），不採一般 Windows Service。
2. **Discovery 輸出區分 `launch_source`（Trusted / Metadata-only）**：`AppEntry` 除了 display_name、aliases、confidence 之外，明確標記資料是否來自可信啟動來源（Start Menu `.lnk`、App Paths、AppsFolder/AUMID、system_apps mapping、manual_apps）或僅為補充 metadata（Uninstall Registry 等）。只有 Trusted Launch Source 可以進一步生成 `LaunchSpec`。
3. **啟動資料流逐層收斂，Adapter 不信任任何遠端字串**：`Command Parser → ValidatedAction → Matcher → Trusted AppEntry → LaunchSpec → Windows Launcher Adapter`。`launcher.py` 只接受 `app_service.py` 建立好的 `LaunchSpec`，即使上層已驗證，Adapter 內部仍再次確認 path 存在、來源合法。
4. **Process 關閉改為 Running Application Resolver**：`process.py` 先用 Catalog 的 process hints 在目前 session 內找出相關 process/top-level window，發送 graceful close，等待 timeout 後再確認；找不到可靠對應時回報「無法安全判斷應關閉哪個程序」，不亂殺。`force_close_app` 是獨立、明確、higher-risk 的操作，不會被自然語言「關閉 X」自動觸發。
5. **Firewall 職責明確分離**：`firewall.py` 執行期只提供 `inspect_network_profile()` / `inspect_firewall_rule()`（唯讀）；`create_private_rule()` / `remove_agent_rule()` 只能由 `setup.ps1` 在使用者明確同意後呼叫，且規則只開放 Agent port、只在 Private Profile。
6. **Rate limiter 放在 infrastructure，不放 domain**：`rate_limit.py` 作為 middleware，處理 client IP / request frequency，與 domain 的商業規則（parser、matcher、shutdown flow）分離。
7. **Catalog 使用穩定 `app_id`**：Matcher 找到程式後，後續流程（`/apps/search` 回傳、`/action` 執行）盡量透過 `app_id` 傳遞，避免重複用 display name 比對造成同名程式、大小寫、fuzzy match 不一致的問題。
8. **Windows 內建工具走 `system_apps` mapping**：Task Manager、Settings、Calculator 等視為 Trusted Launch Source 的固定入口，不依賴一般 Discovery，也不算「把所有應用程式寫死」。
9. **測試分兩類**：`tests/unit/`（mock 化，可在任何環境含本容器完整執行）與 `tests/integration_windows/`（只能在真實 Windows 執行，且明確禁止 shutdown / lock / force kill 等破壞性操作，只做唯讀或安全的探測）。
10. **V1 音樂來源固定為 Spotify**：`play` 恢復 Spotify；指定歌名使用 `spotify_play_track` 搜尋 Spotify Catalog 並播放可信 track URI。取消 YouTube Music / Apple Music provider 選擇流程。歌名與歌手僅能進 Spotify搜尋，不可形成 executable path、command、argument 或 arbitrary URL。
11. **V1 允許 Local LLM semantic fallback / semantic retry，但目前不啟用**：Rule parser 仍優先；第一個 AI integration scope 只處理 free-form `spotify_play_track` / `unknown`，以及 parser 雖產生 `spotify_play_track`、但 deterministic Spotify resolver 顯示 no-result／低信心／疑似 entity-boundary 錯誤的受控 semantic retry。既有歌曲 clarification 與基本播放控制維持 deterministic。AI 輸出必須依序通過 closed schema、deterministic grounding 與 policy gate，且 Phase 0.5 未過門檻，因此正式 execution 前先走 shadow mode；高風險操作永久 deterministic-only，LM Studio/模型不可直接產生 trusted execution target。
12. **Local AI 的 loopback 是安全閘門而非偏好**：production 只允許同機 `127.0.0.1` endpoint；LAN endpoint 只可用於隔離開發/benchmark，不能被 runtime 自動採用。帶有 `clarification_token` 的 `/command` 請求必須直接進入既有 deterministic clarification store，不得呼叫 AI。

See also [SECURITY.md](SECURITY.md) and [WINDOWS.md](WINDOWS.md).


## Deterministic Playback-State Controls

Exact Windows volume and Spotify playback-state commands remain outside Local AI.

```text
Siri text
→ deterministic CommandParser
→ bounded ValidatedAction
→ service
→ fixed Windows/Spotify adapter operation
```

Approved closed actions:

```text
set_volume(volume_percent=0..100)

spotify_shuffle_on/off
spotify_repeat_track/context/off
spotify_continue
spotify_seek
spotify_set_volume
spotify_like_current/unlike_current
```

Windows exact master volume uses the endpoint scalar setter; failure to access an exact setter must return an error instead of approximating with media-key presses. Relative up/down may retain the existing fallback.

`spotify_continue` means repeat off followed by resume while preserving current shuffle state.

No action accepts arbitrary Spotify endpoint URLs, arbitrary HTTP bodies, shell text, executable paths, or client-provided Spotify IDs/URIs. See [PLAYBACK_CONTROLS.md](PLAYBACK_CONTROLS.md).
