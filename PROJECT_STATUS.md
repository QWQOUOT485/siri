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
- Recently Played 目前已有固定 read-only adapter 與 server-side ambiguity ranking source slice；排序位於 Top Signals 之後、Search relevance 之前

Spotify OAuth 使用 Authorization Code with PKCE。真實帳號 token refresh 已驗證。

### Spotify saved/liked personalization slice

- `user-library-read` 已重新授權成功。
- 真實帳號已對三首使用者收藏歌曲讀回 `saved=true`。
- Library membership path 與 server-owned candidate boundary 已驗證。
- Library timeout / 401 / 403 / 429 / malformed response 會安全退回原 deterministic 順序。
- saved status 不進 AI、Shortcut 或一般 API response。

2026-09-20 current-source read-only acceptance probe 使用固定 20 個 bare-title queries，加上最多 50 個只在記憶體中使用的 Recently Played title seed；得到 20 個 genuine ambiguity、1 個 saved membership、0 個 library error、0 個 API error。Accepted case 中 saved candidate 從原始 Search position 1 提升到 final position 0，ambiguity 保留，沒有 playback 或 Library write。Recently Played seed 只用來擴大搜尋語料，saved probe 的 ranking client 只暴露 Search 與 Library membership，因此這是 saved-only reorder evidence。Slice A 已取得 bounded real-account acceptance，但不代表所有未來搜尋語料都一定有 saved reorder。可重跑方法位於 `scripts/spotify_saved_ranking_acceptance.py --from-recent`；詳細精確結果見 [`docs/SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md)。

### Spotify Top Tracks / Top Artists source slice

- 固定使用 `GET /me/top/tracks` 與 `GET /me/top/artists`，不接受 client endpoint、權重、Spotify ID 或 URI。
- Top track / artist 只在既有最多三個 trusted genuine-ambiguity candidates 內作排序 evidence。
- saved → top track → top artist → deterministic relevance → popularity 的順序只影響 candidate ordering；explicit artist / album / version 仍優先，ambiguity 不會變成自動播放。
- malformed 或失敗的 top lookup 只忽略該訊號；Library lookup 失敗時整體回到原 deterministic order。
- source/unit regression 已完成。2026-09-20 token 已重新授權並包含 `user-top-read`、`user-read-recently-played` 與 `user-library-read`；current-source read-only probe 使用固定 20 個 bare-title 加上 bounded in-memory 的 50 個 Top Track title seed，得到 34 個 genuine ambiguity、34 個可比對 raw candidate set、0 個 API/library error，並觀察到 1 個 `top_track` candidate 從原始位置 1 提升到 final position 0，ambiguity 保留，沒有 playback 或 Library write。Top Artist data 在 19 個 candidates 命中，但本次沒有獨立的 Top-Artist-only reorder，因此目前是 **partial acceptance**，不可宣稱 Top Artist standalone real-account acceptance。後續 bounded Top-Artist-only probe 遭遇 Spotify Development Mode `429 QUOTA_EXCEEDED`，`Retry-After=3600` 秒；probe 沒有重試或 busy-loop，quota 清除前不再重跑。詳細結果見 [`docs/SPOTIFY_TOP_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_TOP_RANKING_ACCEPTANCE_2026-09-20.md)。

### Spotify Recently Played source slice

- 固定呼叫 `GET /me/player/recently-played`，只使用 server-owned track ID / artist name 作為既有最多三個 genuine-ambiguity candidates 的 ranking evidence。
- 排序順序維持 saved → top track → top artist → recent track → recent artist → deterministic relevance → popularity；explicit artist / album / version 仍優先，ambiguity 不會變成自動播放。
- response limit 固定 bounded；empty/malformed history、timeout、401、403、429、缺少 scope 或 optional method 都安全忽略並退回既有 deterministic ranking。
- source/unit regression 已完成；bounded probe 的 candidate/membership boundary 已修正為比對 server-owned URI set，不受個人化排序改變順序影響。2026-09-20 重新授權 token 的真實只讀 run 完成了 20 個 genuine ambiguity / 20 個 raw candidate set，Recently Played 命中 6 個 candidates，但沒有 saved/top signal 缺席且 recent-only 重排的 qualifying case；Search、Library、Top、Recently Played error 均為 0。Recently Played real-account acceptance 仍未通過，沒有播放或 Library write。精確證據見 [`docs/SPOTIFY_RECENT_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_RECENT_RANKING_ACCEPTANCE_2026-09-20.md)。

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

目前完整 source test run為 **246 passed**，另有 2 個既有 dependency deprecation warnings；本次 compileall、pip check、git diff check 也都通過。GitHub 目前沒有對 HEAD 提供 Actions workflow / commit status，因此這些是 repo 記錄的本機 source evidence，不等於 hosted CI。

新增的 `docs/LOCAL_AI_FAIL_CLOSED_MATRIX_2026-09-20.md` 與 `tests/unit/test_local_ai_promotion_matrix.py` 固定記錄 malformed output、connection/timeout、busy、oversized response、ungrounded track、invented optional slots 與 policy rejection 的 source/unit fail-closed 結果；targeted Local AI suite 為 **38 passed**。這補齊可重跑的本機矩陣，但不等於 live transport fault injection。

2026-09-20 的 loopback benchmark 三個模型、兩種模式的固定 corpus rows 已完成；完整 sanitized evidence 位於 `docs/LOCAL_AI_BENCHMARK_2026-09-20.md`，中斷過程仍保留在 `docs/LOCAL_AI_BENCHMARK_2026-09-20_PARTIAL.md`。本次未改變 production AI 設定，也沒有模型推薦：`qwen3.5-0.8b` 兩種模式均無法產生可解析 JSON；`qwen2.5-coder-1.5b-instruct` 兩種模式為 95.24% supported semantic、100% semantic-retry；`qwen3-4b` strict-schema row 已完成但為 28.57% supported semantic、16.67% semantic-retry。所有已完成 rows 的 observed false execution 與 post-grounding false acceptance 都是 0%，但這仍不是 Windows/Spotify/Siri acceptance。`LOCAL_AI_FALLBACK_APPROVED` 仍必須維持 `false`。

2026-09-20 real Windows Agent 已完成 loopback/shadow safe、hostile、resolver-retry、server-owned clarification probes；結果與 evidence boundary 記錄在 `docs/LOCAL_AI_SHADOW_ACCEPTANCE_2026-09-20.md`。live probe 沒有讓 AI 結果形成 executable action；malformed/timeout/busy/oversized/grounding edge cases目前以 source/unit evidence 為主，仍不是完整 promotion acceptance。Installed Agent 的 Local AI 相關 source hash 與 current tree 相同；read-only runtime 設定仍為 `shadow`、loopback、`qwen2.5-coder-1.5b-instruct`、2 秒、32 KiB、`LOCAL_AI_FALLBACK_APPROVED=false`，但 installed `config.py` 尚非 current exact tree，故不能視為 exact promotion commit。`LOCAL_AI_FALLBACK_APPROVED` 仍必須維持 `false`。

新的 exact-evidence independent review 位於 `docs/LOCAL_AI_PROMOTION_REVIEW_2026-09-20.md`，結論為 **NO-GO**：live transport fault matrix、Siri/real-account acceptance 與 exact executable-fallback promotion boundary 尚未全部完成。新的 source/unit matrix 只補強 B1 的本機證據，沒有清除上述 live blocker。這不是模型推薦，也不改變 `LOCAL_AI_FALLBACK_APPROVED=false`。

### Promotion gate

production fallback 仍是 **NO-GO**，直到完成：

1. 完整 current exact commit / model / config 的 production-loopback shadow acceptance（目前 real Agent safe/hostile probes 已部分完成）
2. durable sanitized benchmark evidence summary（含 commit、fixture、model、LM Studio、prompt/schema/config 與 aggregate metrics）
3. 完整 source/security regression
4. real Windows Agent + Spotify safe cases / fail-closed cases（目前 live safe/hostile/clarification 部分完成；transport fault matrix 仍以 unit evidence 為主）
5. deterministic commands 與 clarification regression（source suite 已通過；Siri voice acceptance仍另計）
6. separate independent promotion review（2026-09-20 review 已完成但結論為 NO-GO，需先清除列出的 blockers）

不得因 benchmark 變好而直接設定 `LOCAL_AI_FALLBACK_APPROVED=true`。

## Local Semantic Recovery / Alias Memory

Phase 1 source implementation 已完成一個可 review 的 Slice 1–10 vertical implementation；2026-09-20 的 current-source Windows lifecycle harness 也已通過，但尚未宣稱 installed runtime / real-world acceptance complete。詳細證據與界線見 [`docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md)。

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
- 已建立 bounded domain models、schema-versioned SQLite persistence、RAM exact index、candidate-only RapidFuzz evidence、MemoryLearner、EntityRecoveryService、optional runtime config 與 aggregate-only metrics。
- `Sad overlxrd` 首次 trusted clarification + successful mocked playback 會建立 alias；第二次相同 artist text 走 exact RAM canonicalization；mocked playback failure 不會學習。
- source/security/concurrency regression 已納入完整 pytest suite；memory 預設仍 disabled，`LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY` 以 code-level false gate fail closed。
- current-source Windows harness 已驗證 disabled startup、fresh SQLite schema v1/FK、controlled enabled startup、restart persistence/RAM rebuild、corrupt/unavailable fallback、fuzzy candidate-only、conflict 與 8-way concurrent confirmation；exact lookup 1,000 次的 P50/P95 為 0.0174/0.0231 ms（temporary fixture，非 installed-host benchmark）。
- current-source staged runtime 已用真實 Spotify 帳號完成 token refresh、trusted canonical search、server-owned clarification selection、實際 playback、MemoryLearner confirmation、restart persistence 與第二次 exact hit（exact=1、fuzzy=0）；但 candidate 是由 canonical trusted search 控制性 seed，不能代替 ASR alias 的 first-occurrence candidate recovery。
- 真實 `Sad overlxrd` first-occurrence path（使用帳號實際存在的 `死亡不是生命的終點`）仍回傳 `SPOTIFY_TRACK_NOT_FOUND`、沒有 clarification candidates；installed Windows Agent 仍沒有 Semantic Memory modules/config flags/SQLite artifact，iPhone Siri voice E2E 也尚未執行，因此仍不可設定 `LOCAL_SEMANTIC_MEMORY_ENABLED=true`。詳細 follow-up 見 [`docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md)。

規格位於 `docs/semantic_recovery/`。

## Not Yet Proven / Remaining Work

### Highest priority

1. **Spotify Top-Artist-only genuine-ambiguity acceptance**
   - Top Track 已有 1 個 real-account partial acceptance；如要完成 combined Top Tracks / Top Artists gate，需補一個沒有 Top Track / saved / recent 強訊號、由 Top Artist 單獨提升的 case。
   - 驗證 Top Artist 只改善候選順序、不覆蓋 explicit metadata、不消除 genuine ambiguity、不自動播放。
   - 目前被 Spotify Development Mode quota 阻塞：最近一次 bounded probe 收到 `429 QUOTA_EXCEEDED`、`Retry-After=3600`；最小下一步是 quota window 清除後只跑一次 bounded read-only probe。

2. **Spotify personalization real acceptance and next signal**
   - Top Track 的 genuine-ambiguity ordering 已取得 1 個 real-account partial acceptance；仍需決定是否補一個 Top-Artist-only reorder 以完成 combined Top Tracks / Top Artists gate。
   - `user-read-recently-played` 已在 2026-09-20 重新授權取得；仍需單獨驗證 Recently Played 的 genuine-ambiguity ordering。
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
   - current-source Windows SQLite/create/restart/RAM/fallback harness 已完成；source/unit與mocked Spotify regression已通過。
   - current-source staged runtime 已完成 partial real Spotify playback/write/restart/exact-hit；但 normal `Sad overlxrd` first-occurrence candidate recovery 仍 blocked，不能宣稱完整 acceptance。
   - 仍需 updated installed Agent、正常 ASR alias → trusted candidate → clarification path、iPhone/Siri voice E2E 與 installed-host acceptance；memory 保持 disabled。
   - rollout evidence 見 [`docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md) 與 [`docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md)。

5. **Local AI promotion evidence**
   - 保持 off/shadow。
   - 2026-09-20 three-model/two-mode benchmark 與 sanitized combined evidence 已完成；`qwen3-4b` 未達初始品質門檻，且不得據此自動選定模型或啟用 fallback。
   - 下一步是 current exact commit/configuration 的 production-aligned loopback shadow acceptance，再做 deterministic regressions 與 separate promotion review。

### Smaller validation gaps

- exact Windows volume：尚缺 Siri voice E2E / independent physical-speaker check。
- clarification store bounded attempts / concurrency hardening：source/unit 已完成，但未因這個內部修正另外重跑完整 Siri E2E。
- Recently Played 尚缺 real Spotify account acceptance；boundary assertion 已修正，但本次 bounded real-account run 未找到 recent-only reorder case。沒有 playback 或 Library write；下一步是新的 bounded corpus 或明確接受「source slice 完成、real-account gate 未證明」的產品決策。
- Spotify OAuth callback 曾出現「瀏覽器顯示通用失敗，但 status/token 實際成功保存」的不一致；功能可用，但 UI/root cause 尚未釐清。
- GitHub hosted CI 尚未建立；目前 source test evidence 主要由本機執行與狀態文件記錄。

## Current Recommended Order

```text
1. Top-Artist-only genuine-ambiguity acceptance (if completing the combined Top gate; after quota clears)
2. Recently Played real-account acceptance after `user-read-recently-played` reauthorization
3. deterministic Spotify playback-state controls
4. Local Semantic Recovery Phase 1 runtime acceptance
5. Local AI production-loopback shadow acceptance
6. sanitized promotion evidence
7. independent Local AI promotion review
8. only then consider guarded fallback execution
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
