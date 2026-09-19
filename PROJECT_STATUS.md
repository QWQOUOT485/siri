# Project Status

這份文件是給新對話／新 coding agent 的「目前狀態摘要」。只記錄現在仍然有效的事實、驗收邊界與下一步；歷史 benchmark、bug 修復與 review 細節請看專門文件與 Git history。

## Current Phase

**Windows Siri Agent v1 核心流程已可用；目前重點是 Spotify 候選品質、剩餘 deterministic controls、Local Semantic Recovery Phase 1，以及 Local AI production promotion gate。**

目前 production 行為仍以 deterministic parser / resolver 為主。Local AI 已有 guarded semantic-retry skeleton、shadow benchmark 與 resolver seam，但 **production fallback 尚未批准，`LOCAL_AI_FALLBACK_APPROVED=false` 必須維持不變，直到新的 production-aligned acceptance 與 promotion review 完成。**

## Source of Truth

依序閱讀：

1. `docs/SECURITY.md` — 最高優先
2. `docs/SPEC.md`
3. `docs/ARCHITECTURE.md`
4. 任務相關文件：`docs/SPOTIFY.md`、`docs/API.md`、`docs/WINDOWS.md`、`docs/NETWORKING.md`、`docs/SIRI_SHORTCUT.md`
5. `TASKS.md`
6. `docs/TESTING.md`

`PROJECT_STATUS.md` 只描述目前 implementation / acceptance 狀態，不能覆蓋安全規格。

`docs/SOURCE_SPEC.md` 是唯讀歷史快照，不再是現行規格的 final arbiter。這個 authority blocker 已於 2026-09-19 由 `AGENTS.md` 與現行規格順序明確解決。

## Security Invariants

下列界線不可因功能或 AI 擴充而放寬：

```text
Siri Text
→ Parser / guarded semantic interpretation
→ ValidatedAction
→ Trusted service / Catalog object
→ Adapter
```

- 不提供 remote shell / arbitrary PowerShell / CMD / Python execution。
- 使用者文字不得直接進 shell、subprocess、executable path 或 arbitrary URL。
- App launch 只能走 Trusted `AppEntry` / `LaunchSpec`。
- Windows Agent 只供 LAN 使用，不公開到 Internet。
- Shutdown 必須兩階段 confirmation token。
- Spotify token 只保存在 Windows 本機，不進 Shortcut、API response、log 或 Git。
- Local AI 永遠不是 execution engine。

## Completed and Accepted

### Core Windows Agent

- API key authentication、closed action schema、rate limiting 與 LAN/private-network boundary 已建立。
- Windows Agent 必須跑在目前登入使用者的 interactive session。
- 自動啟動採 Task Scheduler `At log on`。
- Application discovery / catalog / matcher / trusted launch flow 已建立。
- Graceful close 與 explicit force-close 為不同權限路徑。
- Shutdown two-step confirmation 已實作。
- `scripts/start.bat`、setup / firewall 流程與 diagnostics 已建立。

### Siri / Shortcut

- iPhone Shortcut → Windows Agent → Spotify 的基本控制路徑已實機通過。
- 指定歌曲播放已實機通過。
- Spotify clarification 已完成全語音 E2E：
  - Agent 回傳最多 3 個 trusted candidates + opaque token
  - Shortcut 保存 token
  - 第二輪語音選擇回送 token
  - server-side trusted candidate selection
  - 真實 Spotify 播放成功
- clarification 穩定流程已記錄在 `docs/SIRI_SHORTCUT.md`。
- 換 API key 後的 iPhone → Agent → Spotify playback regression 已通過。

### Spotify deterministic path

已支援：

- `spotify_resume`
- `spotify_play_track`
- `spotify_pause`
- `spotify_next`
- `spotify_previous`

目前 Siri acceptance scope 聚焦指定歌曲、播放、暫停與 clarification；下一首／上一首 closed actions 保留，但不列入目前 Siri acceptance scope。

Catalog / resolution 已有：

- Traditional / Simplified Chinese normalization
- Live / Concert / Tour / 演唱會 / 現場版本排除
- album / version hint
- trusted `SpotifyTrackRef`
- ISRC / duration 輔助 identity evidence
- confidence-based ambiguity handling
- 最多 3 個 clarification candidates
- popularity 僅作同分候選 tie-breaker
- saved/liked membership signal 僅用於 genuine ambiguity candidate ordering
- Top Tracks / Top Artists 目前已有固定 read-only adapter 與 server-side ambiguity ranking source slice

Spotify OAuth 使用 Authorization Code with PKCE。真實帳號 token refresh 已驗證。

### Spotify saved/liked personalization slice

- `user-library-read` 已重新授權成功。
- 真實帳號已對三首使用者收藏歌曲讀回 `saved=true`。
- Library membership path 與 server-owned candidate boundary 已驗證。
- Library timeout / 401 / 403 / 429 / malformed response 會安全退回原 deterministic 順序。
- saved status 不進 AI、Shortcut 或一般 API response。

**尚未驗證：** saved signal 是否能在 Spotify 原始 Search 排序不同的 genuine ambiguity case 中實際改善候選順序。

目前的 read-only acceptance probe 使用固定 20 個 bare-title queries，得到 15 個 genuine ambiguity 結果、0 個 saved membership；沒有執行 playback 或 Library write，因此 Slice A real-account acceptance 仍維持未通過。可重跑方法位於 `scripts/spotify_saved_ranking_acceptance.py`；它找不到 qualifying case 時會明確回報 blocker。

### Spotify Top Tracks / Top Artists source slice

- 固定使用 `GET /me/top/tracks` 與 `GET /me/top/artists`，不接受 client endpoint、權重、Spotify ID 或 URI。
- Top track / artist 只在既有最多三個 trusted genuine-ambiguity candidates 內作排序 evidence。
- saved → top track → top artist → deterministic relevance → popularity 的順序只影響 candidate ordering；explicit artist / album / version 仍優先，ambiguity 不會變成自動播放。
- malformed 或失敗的 top lookup 只忽略該訊號；Library lookup 失敗時整體回到原 deterministic order。
- source/unit regression 已完成；真實帳號 top-signal acceptance 尚未完成。現有本機 token 尚未包含 `user-top-read`，需重新授權後才能驗證 real-account ordering。

### Windows exact volume

`set_volume(volume_percent=0..100)` 已完成：

- closed action
- deterministic Chinese / English parser
- strict schema
- pycaw exact scalar setter
- exact setter 失敗時明確報錯，不用 media key 假裝精確百分比

已部署 Windows runtime 並以 `/action` 與 `/command` 驗證 exact scalar path。尚未做 Siri 語音 E2E 與獨立實體喇叭聽感驗收。

### Non-AI repair batch

已完成並有 regression coverage：

- Windows `SendInput` ctypes native layout
- shutdown expired-token error accuracy
- bounded relative-volume steps
- force-close duplicate PID deduplication
- Chinese normalization duplicate mapping cleanup
- configured-port `start.bat` diagnostics

其中安全的 Windows runtime / Spotify playback 路徑已有部署驗證；沒有為驗收而執行真實 shutdown 或 force-close。

## Local AI Status

### Current authority

Local AI 在 V1 **允許研究與 guarded integration，但 production fallback 尚未批准**。

現行 initial AI scope 只允許：

```text
spotify_play_track
unknown
```

以下維持 deterministic-only：

- playback controls
- clarification selection
- app control
- volume
- shutdown / force-close
- firewall
- system administration

### Implemented guarded path

```text
original Siri utterance
→ deterministic parser/resolver
→ deterministic eligibility gate
→ Local AI semantic retry
→ RawAIIntent
→ strict schema
→ deterministic grounding
→ GroundedAIIntent
→ AIPolicyGate
→ ValidatedAction
→ deterministic Spotify resolver
```

AI 不得選 Spotify URI / track ID、不得排序候選、不得直接播放，也不得接觸 clarification token authority。

Production LM Studio endpoint 必須是同機 loopback `127.0.0.1`；LAN endpoint 只可作隔離 benchmark / development。

### Evidence

最初 Phase 0.5 benchmark 未達門檻，因此不能當 production authorization。

後續 guarded fixed-corpus benchmark 與 resolver-seam hardening 已記錄：

- semantic accuracy 約 95.24%
- semantic-retry 100%
- deterministic-only / safety-only safe-unknown 100%
- observed false execution 0%
- observed post-grounding false acceptance 0%
- P95 約 200 ms
- source resolver / route regressions 已補齊

最近在乾淨的 Phase 1 PR 分支記錄的完整 source test run為 **214 passed**，另有 2 個既有 dependency deprecation warnings；compileall 與 pip check 通過，diff check 在修正檔尾空白後重跑。GitHub 目前沒有對 HEAD 提供 Actions workflow / commit status，因此這些是 repo 記錄的本機 source evidence，不等於 hosted CI。

2026-09-20 的 loopback shadow benchmark 已開始但依使用者要求暫停；部分結果與未完成邊界記錄在 `docs/LOCAL_AI_BENCHMARK_2026-09-20_PARTIAL.md`。本次未改變 production AI 設定，也沒有模型推薦：`qwen3.5-0.8b` 兩種模式均無法產生可解析 JSON；`qwen2.5-coder-1.5b-instruct` 兩種模式維持 95.24% supported semantic accuracy；`qwen3-4b` 僅完成 prompt mode，schema mode 尚未完成。`LOCAL_AI_FALLBACK_APPROVED` 仍必須維持 `false`。

### Promotion gate

production fallback 仍是 **NO-GO**，直到完成：

1. current exact commit / model / config 的 production-loopback shadow acceptance
2. durable sanitized benchmark evidence summary（含 commit、fixture、model、LM Studio、prompt/schema/config 與 aggregate metrics）
3. 完整 source/security regression
4. real Windows Agent + Spotify safe cases / fail-closed cases
5. deterministic commands 與 clarification regression
6. separate independent promotion review

不得因 benchmark 變好而直接設定 `LOCAL_AI_FALLBACK_APPROVED=true`。

## Local Semantic Recovery / Alias Memory

Phase 1 source implementation 已完成並納入本分支，且已有 unit/security regression coverage；但 Windows runtime、重啟持久化與真實 Spotify/Siri acceptance 尚未完成，因此仍不可啟用。

Phase 1 原則：

- 只有 **exact confirmed non-conflicted alias** 可自動 canonicalize。
- confirmed learning 必須來自：
  ```text
  server-owned clarification candidate
  → explicit user selection
  → successful playback
  ```
- RapidFuzz / track-first / vector / AI 只可作 candidate/evidence，不能直接升為 execution authority。
- observation logging 預設關閉。
- DB corruption/unavailability 必須退回既有 deterministic behavior。

規格位於 `docs/semantic_recovery/`。

目前已完成的 source slice：

- bounded domain models 與 five-state trust model
- schema-versioned SQLite persistence、foreign keys、transactional migration 與 safe failure
- deterministic `EntityNormalizer`
- confirmed/active/non-conflicted exact RAM fast path
- RapidFuzz candidate-only retrieval
- `MemoryLearner` promotion gate：trusted clarification selection + successful playback
- candidate-only `EntityRecoveryService`
- disabled-by-default runtime/config wiring
- trusted Spotify clarification/playback learning integration
- bounded metrics、conflict handling 與 poisoning/security regressions

Source completion 不等於 deployment acceptance。`LOCAL_SEMANTIC_MEMORY_ENABLED=false` 必須維持不變，直到下方 runtime acceptance 完成。

## Not Yet Proven / Remaining Work

### Highest priority

1. **Spotify saved ranking genuine-ambiguity acceptance**
   - 找一個原始 Spotify Search 順序不理想、且其中一個 trusted candidate 是 saved=true 的 case。
   - 驗證 saved signal 只改善候選順序、不消除 genuine ambiguity、不自動播放。

2. **Spotify personalization real acceptance and next signal**
   - 重新授權 `user-top-read` 後，驗證 Top Tracks / Top Artists 的 genuine-ambiguity ordering。
   - Recently Played 尚未實作。
   - 必須保持 explicit artist / album / version 與 ambiguity safety 優先。

3. **Deterministic Spotify controls**
   - shuffle on/off
   - repeat off/track/context
   - continue
   - seek
   - Spotify device volume
   - like/unlike current track
   - 都不得擴張 Local AI allowlist。

4. **Local Semantic Recovery Phase 1 runtime acceptance**
   - source implementation、unit/security coverage 已完成；尚缺真實 Windows DB creation/migration、restart persistence、DB→RAM rebuild 與 on-host latency evidence。
   - 完成 `SASIOVERLXRD ↔ Sad overlxrd` first-run clarification/playback → confirmation，以及 second-run exact-alias fast path。
   - 驗證既有 Spotify resolver、Live filtering、clarification 與 Siri E2E 無 regression。
   - acceptance 完成前保持 `LOCAL_SEMANTIC_MEMORY_ENABLED=false`。

5. **Local AI promotion evidence**
   - 保持 off/shadow。
   - 2026-09-20 partial three-model benchmark 已記錄，但 `qwen3-4b` schema mode 尚未完成；不得據此選定模型或啟用 fallback。
   - 完成剩餘單一 benchmark mode 後，再做 production-aligned loopback acceptance 與 separate promotion review。

### Smaller validation gaps

- exact Windows volume：尚缺 Siri voice E2E / independent physical-speaker check。
- clarification store bounded attempts / concurrency hardening：source/unit 已完成，但未因這個內部修正另外重跑完整 Siri E2E。
- Spotify OAuth callback 曾出現「瀏覽器顯示通用失敗，但 status/token 實際成功保存」的不一致；功能可用，但 UI/root cause 尚未釐清。
- GitHub hosted CI 尚未建立；目前 source test evidence 主要由本機執行與狀態文件記錄。

## Current Recommended Order

```text
1. genuine-ambiguity saved-ranking acceptance
2. Top Tracks / Top Artists real-account acceptance after `user-top-read` reauthorization
3. Recently Played personalization source slice
4. deterministic Spotify playback-state controls
5. Local Semantic Recovery Phase 1 runtime acceptance
6. Local AI production-loopback shadow acceptance
7. sanitized promotion evidence
8. independent Local AI promotion review
9. only then consider guarded fallback execution
```

## Installed Runtime

目前記錄的 Windows Agent 路徑：

```text
D:\ai\windows-siri-agent
```

Spotify redirect URI：

```text
http://127.0.0.1:8000/spotify/callback
```

不要把 API key、OAuth token、authorization code、PKCE verifier/state 或其他 secret 寫入本檔。

## Updating This File

任何改變真實專案狀態的工作，在結束前都要更新這份文件。

只保留：

- 現在的 phase
- 現在有效的 accepted facts
- 真實 acceptance boundary
- current blockers / not-yet-proven
- 下一步

歷史 debug 過程、舊 test count、已解決 blocker 與被取代的 next step，應留在專門報告或 Git history，不要再次累積到這份 handoff。
