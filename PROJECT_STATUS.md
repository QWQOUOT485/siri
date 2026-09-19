# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Local AI initial Phase 0.5 benchmark 未通過；production-aligned guarded shadow benchmark 已完成、仍未 promotion + 第二輪架構/安全 review 已完成 + Siri clarification iPhone 全語音 E2E 已驗收通過**

先前的 Spotify studio/Live、繁簡正規化、最多三候選與 server-side clarification source/runtime 驗證已完成。2026-09-18 產品決策新增：V1 不再禁止本地 LLM，可在安全邊界下使用 LM Studio 作 rule-first 的 fallback 語意解析器。Phase 0.5 benchmark 已完成但沒有模型通過門檻。2026-09-19 iPhone Shortcut 已實機完成候選回傳、token 保存、第二輪 selection + token 回送與真實 Spotify 播放；最終穩定修正為只在 clarification 分支中，先朗讀候選，再執行「關閉 Siri 並繼續」，最後由第二次聽寫接手選擇，因此已完成 hands-free Siri clarification E2E。

## Independent Local AI Gate Review (2026-09-19)

- Static architecture/security gate review completed against current GitHub source; review report: `docs/LOCAL_AI_REVIEW_2026-09-19.md`.
- Verdict: **NO-GO for production/executable Local AI fallback promotion**; **GO for shadow-only hardening, evidence collection, and blocker remediation**.
- Blocking authority conflict remains: `AGENTS.md` makes `docs/SOURCE_SPEC.md` final arbiter, while SOURCE_SPEC §94/§95 still prohibit V1 Local LLM implementation and newer SPEC/SECURITY/ARCHITECTURE documents allow guarded Local AI.
- Production AI Windows/Spotify/Siri runtime acceptance has not been completed by this review; no real-world acceptance claim is added.
- `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` still contains stale broader AI scope (playback controls / candidate selection) and must be reconciled with the current narrow `spotify_play_track` / `unknown` + deterministic clarification contract before further production-facing AI expansion.
- Production promotion also requires a durable sanitized benchmark evidence summary tied to the exact commit/model/configuration, followed by a separate promotion review.

## Completed / Decided

- V1 保留 Rule-based Parser 為第一層，並允許 Local LLM 作 fallback semantic parser；AI 不得直接執行或繞過 ValidatedAction / deterministic resolver / trusted-object 邊界。
- Windows Agent 必須執行在目前登入使用者的 interactive session。
- 自動啟動使用 Task Scheduler `At log on`。
- Remote API 不是 remote shell；不允許任意 CMD / PowerShell / executable path / arbitrary URL。
- App launch 必須走 Trusted AppEntry / LaunchSpec。
- Shutdown 使用兩階段 confirmation token。
- Agent 僅供 LAN 控制，不對 Internet 開放。
- Spotify 是 V1 唯一音樂 provider。
- 已移除 YouTube Music / Apple Music / Spotify 三選一流程。
- 支援規格中的 Spotify actions：
  - `spotify_resume`
  - `spotify_play_track`
  - `spotify_pause`
  - `spotify_next`
  - `spotify_previous`
- 支援目標語句：
  - 「播放」
  - 「播放晴天」
  - 「播放周杰倫的晴天」
  - 「暫停」/「暫停音樂」
  - 「下一首歌」
  - 「上一首歌」
- Spotify token 必須只保存在 Windows 本機，不進 Siri Shortcut、不進 Git、不進 API response/log。
- Spotify OAuth 採 Authorization Code with PKCE。
- Spotify 整合規格見 `docs/SPOTIFY.md`。
- Spotify candidate quality 個人化排序採 saved/liked → Top Tracks / Top Artists → Recently Played → Spotify Search relevance → popularity-like tie-breaker；不取代 explicit artist/album/version，也不單獨消除真正 ambiguity。saved/liked 的第一個非 AI slice 已完成 source/runtime fallback 驗證，其他訊號仍未實作。
- saved/liked 需要 `user-library-read`；like/unlike 仍另需 `user-library-modify`，Top/Recent 仍需 `user-top-read`、`user-read-recently-played`。本次重新授權後已讀回新 scope，並完成 Library endpoint 唯讀驗證；saved=true 的真實候選排序仍待驗收。
- `播放周杰倫的晴天 (葉惠美)` 已支援以專輯/版本提示縮小同名歌曲結果；提示只進 Spotify Search API，不進 shell、path 或 arbitrary URL。
- 目前程式碼已支援自然語音 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`、`播放晴天現場版`、`播放晴天原版`；明確 Live 會安全拒絕，不會播放 Live。
- `SpotifyCatalog` 已有通用版本分類、繁簡正規化、ISRC / duration 與 confidence-based matching；Live / Concert / Tour / 演唱會 / 現場候選會直接排除。
- 消歧修正、播放控制與本輪非 AI 修復的 source unit/security tests 已通過（目前 `pytest -q` 為 139 passed，2 個既有 dependency deprecation warnings）；這個數字是目前工作樹的完整結果，不代表所有項目都已完成 Windows/Spotify/Siri 實機驗收。
- Spotify Search 的 optional `isrc`／`duration_ms`／`popularity` 已解析到 `SpotifyTrackRef`；同 ISRC 只作為接近候選的同錄音證據，duration 不會單獨觸發自動播放，popularity 只作為同等 matching score 候選的排列 tie-breaker。
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。
- 真實帳號 token refresh 已驗證；refresh 後仍可成功執行 Spotify 播放控制。
- `scripts/start.bat` 啟動失敗時會保留視窗並提示 port/Agent 問題，不再靜默關閉。
- `暫停`、`暫停音樂`、`pause music` 與簡體 `暂停音乐` 都收斂到封閉的 `spotify_pause` action；不回退到通用系統媒體控制。
- Windows exact master volume `set_volume` 已加入 closed action、百分比 parser/schema 與 pycaw scalar adapter；0、37、100 與失敗不 fallback 都有 regression coverage。
- Spotify extended controls 已加入下一階段 scope：shuffle on/off、repeat off/track/context、seek、Spotify device volume，以及「喜歡這首／取消喜歡這首」Library write。這些全部維持 deterministic closed actions，不交給 Local AI。
- 第一版 like/unlike 只允許操作 server 讀回的目前播放 Spotify track；client 不得提供任意 Spotify URI / track ID。



## Deterministic Exact Volume / Spotify Playback Controls (source progress 2026-09-19)

The next non-AI controls batch is now specified in `docs/PLAYBACK_CONTROLS.md`.

Planned closed actions include:

- Windows exact master volume: `set_volume(volume_percent=0..100)`
- Spotify shuffle: `spotify_shuffle_on` / `spotify_shuffle_off`
- Spotify repeat: `spotify_repeat_track` / `spotify_repeat_context` / `spotify_repeat_off`
- Spotify normal continuous playback: `spotify_continue` = repeat off + resume, while preserving current shuffle state
- existing planned `spotify_seek`, `spotify_set_volume`, `spotify_like_current`, `spotify_unlike_current`

Windows exact percentage uses the pycaw scalar endpoint. If exact setting is unavailable, the Agent must return an explicit failure rather than approximate the requested percentage with media keys. Existing relative up/down commands may retain their bounded media-key fallback.

Windows master volume and Spotify Connect device volume are separate actions: `音量 30%` targets Windows; `Spotify 音量 30%` targets Spotify. All controls remain deterministic-only and do not expand the Local AI allowlist.

Windows exact master volume is now source-complete for this slice:

- `set_volume` is a closed action with `volume_percent` restricted to integer `0..100` in both domain and API schemas.
- Chinese and English absolute phrases parse deterministically; absolute forms such as `把音量降低到 30%` win over relative wording.
- The Windows adapter calls only `SetMasterVolumeLevelScalar(volume_percent / 100)` for this action. Missing or failing pycaw returns an explicit error and never sends media keys; mute state is not changed.
- Regression coverage includes parser boundaries, schema ownership, scalar conversion, exact-set failure behavior, mute isolation, relative step fallback, and API wiring.
- Source verification after this slice: `pytest -q` 139 passed, `compileall` passed, `pip check` passed, and `git diff --check` passed.

The exact-volume slice is deployed to `D:\ai\windows-siri-agent`. Controlled Windows runtime acceptance passed: `/health` and authenticated `/info` were healthy; `音量 101` failed closed with `INVALID_VOLUME_PERCENT`; structured `/action` and Chinese `/command` both returned `set_volume` success and `level=0.95` through the pycaw scalar setter. The pre-test scalar `0.949999988...` was restored afterward. This verifies the Agent/pycaw path, not Siri voice E2E or a separate physical-speaker listening check. Spotify shuffle/repeat/continue/device-volume/seek/like controls remain planned and are not implemented by this slice.

## Local Semantic Recovery / Alias Memory Phase 1 (approved 2026-09-19)

Claude review accepted the architecture with the required Phase 1 scope reduction: only an **exact confirmed non-conflicted alias** may auto-canonicalize. RapidFuzz and track-first recovery are candidate/evidence-only until a fixed adversarial corpus proves zero wrong automatic canonicalizations.

Implementation is now authorized but is **not yet claimed complete**. The split implementation specification is under `docs/semantic_recovery/`:

- `README.md` — scope, authority chain, invariants
- `RECOVERY_PIPELINE.md` — deterministic recovery ladder and AI boundary
- `MEMORY_MODEL.md` — SQLite/RAM model, five trust states, conflict handling
- `SECURITY.md` — poisoning/privacy/provider-ID boundaries
- `IMPLEMENTATION_PLAN.md` — implementation slices and rollout
- `TESTING.md` — blocking tests and Windows acceptance
- `REFERENCES.md` — research/technical references

Phase 1 implementation target: EntityNormalizer + SQLite persistence + confirmed-alias RAM index + RapidFuzz candidate-only + MemoryLearner. Confirmed learning requires server-owned clarification selection **and successful playback**. `alias_observations` defaults off; `scope_context` is reserved but unused; text-derived phonetic keys and vector memory are deferred/removed from Phase 1.

Canonical regression: Siri/ASR `Sad overlxrd` must be learnable, after trusted clarification/playback, as a local alias for the trusted Spotify artist `SASIOVERLXRD`. The second identical ASR error should take the exact confirmed-alias fast path without AI.


## Third-party Review Consolidation / Non-AI Repair Batch (2026-09-19)

Two external AI code-review reports were compared against the current `main` source. Treat the following as the current review disposition rather than copying either report's completion percentages or recommendations blindly.

本輪只處理與 Local AI 無關的 review 項目；AI parser、policy、grounding 與相關未追蹤草稿不在本輪範圍內，也沒有納入本輪 commit。

以下六項已完成 source 修正與 regression tests：

1. **Windows media `SendInput` ctypes layout** — `_INPUT` now uses the native `INPUT` union layout, pointer-sized `dwExtraInfo`, and a typed pointer passed to `SendInput`.
2. **Shutdown expiration error-code accuracy** — a requested expired token now returns `SHUTDOWN_TOKEN_EXPIRED` and is removed, while invalid and reused token behavior remains separate.
3. **Volume fallback steps** — bounded volume up/down requests now emit the requested number of key events; mute/unmute remain one event.
4. **Force-close duplicate PID cleanup** — force-close deduplicates trusted process IDs before attempting termination and counting results.
5. **Chinese fallback-map duplicate key** — the duplicate `"體": "体"` mapping was removed; the normalization regression test remains explicit.
6. **`start.bat` configured-port diagnostics** — startup and failure text now read `SIRI_AGENT_PORT` from the local `.env`, defaulting to 8000.

Source verification for this batch: `pytest -q` reported `112 passed` with the same 2 dependency deprecation warnings; `compileall`, `pip check`, and `git diff --check` passed. The six matching runtime files were deployed to `D:\ai\windows-siri-agent` and their hashes matched source. A controlled Windows runtime started through `scripts/start.bat`, returned healthy/authenticated responses, and successfully played `死亡是生命的終點` / `SASIOVERLXRD` / `納薩力克`.

The remaining acceptance boundary is explicit: no real shutdown or force-close action was executed; native media-key/volume hardware behavior was covered by mocked layout/step tests but not promoted from those tests to a separate physical-device acceptance claim. The runtime remains available on port 8000 for safe user testing.

## Non-AI Spotify Candidate Ranking Slice (2026-09-19)

- `SpotifyTrackRef` 現在保留 Spotify Search 回傳的 bounded `popularity` metadata。
- `SpotifyCatalog` 只在 matching score 相同時用 popularity 排列 clarification 候選；confidence gap、Live filtering、ISRC identity 與 genuine ambiguity 規則完全不變。
- 缺少、非整數或不在 0–100 的 popularity 會被忽略，不會成為播放決策依據。
- 本輪尚未加入 `market=TW`；Top Tracks/Artists、Recently Played 仍是後續非 AI 工作。saved/liked source slice 已完成，真實帳號仍需新 scope 才能驗證 saved=true 的排序。
- source regression tests 已覆蓋「熱門度改善候選順序但不能自動播放」與無效 metadata。
- 以目前授權帳號對 `track:晴天 artist:周杰倫` 做唯讀 Spotify Search A/B：未加 market 與 `market=TW` 都回傳 3 個結果，順序與歌名／歌手／專輯資料相同；因此本輪沒有盲目把 `market=TW` 加入正式流程。
- 同一輪對 `track:Stay artist:The Kid LAROI` 的真實 Search 回應中，觀察到的項目沒有可用 popularity 值；tie-breaker 因此安全地保持 dormant，不宣稱已改善真實排序品質。
- deployed `catalog.py` 已在隔離 port 8001 runtime compile 與唯讀 Search 驗證；之後已透過 `scripts/start.bat` 可控重啟 port 8000，`/health` 正常，正式 runtime 已載入新檔案。

## Non-AI Spotify Saved Candidate Slice (2026-09-19)

- `SpotifyApiClient.check_saved_tracks` 只允許最多三個 server-owned `spotify:track:` URI，固定呼叫 `GET /me/library/contains`，不接受 client URI、URL 或 arbitrary endpoint。
- `SpotifyCatalog` 只在既有 genuine ambiguity 的最多三個候選內，以 read-only saved/liked status 重排；不改變 deterministic confidence、explicit artist/album/version、Live filtering 或自動播放決策。
- Library timeout、401、403、429、格式錯誤或未提供此能力時，維持原本 deterministic candidate order；saved status 不進 AI、Shortcut 或一般 API response。
- source `pytest -q` 為 `150 passed`，compileall、pip check、diff check 通過；三個 runtime 檔案已部署且與 source 正規化內容一致。
- 重啟後 Windows Agent `/health`、認證 `/info`、Spotify status 正常；舊 token 原本只有 playback scopes，這次重新授權後 `/spotify/status` 已讀回 `user-library-read`。瀏覽器 callback 頁面曾顯示通用「授權驗證失敗」，但本機 status 與 token 檔案讀回已顯示新 scope；因此記為 callback 顯示與實際保存結果不一致，根因尚未宣稱確定。
- 重新授權後以兩個 Spotify Search server-owned candidates 做唯讀 `GET /me/library/contains` 驗證，回應格式與數量正確，結果均為 `false`；這證明新 scope 與 endpoint 流程可用，但尚未證明 `saved=true` 會提升候選。下一個最小驗收是先在 Spotify 收藏一首會造成 genuine ambiguity 的候選，再重跑同一搜尋並確認順序改善且仍不自動播放。

## Spotify Library Scope Reauthorization (2026-09-19)

- 本次重新授權流程使用新的 PKCE state/verifier；沒有把 token、authorization code 或 state 寫入狀態文件、API response 或 log。
- Spotify consent callback 的瀏覽器畫面顯示通用失敗訊息，但 `/spotify/status` 已回報 `authorized=true` 且 scope 包含 `user-library-read`，token 檔案也在本次流程更新。這表示授權資料已保存；callback 顯示不一致仍需後續用一次新的單一 callback 流程釐清。
- 後續唯讀 Search + Library membership 檢查成功完成，兩個候選皆為未收藏；沒有播放、寫入 Library 或改變使用者播放狀態。

Spotify Search quoting is **not accepted as a bug by review alone**. Do not blindly change all field queries to quoted syntax. If this is revisited, run real Spotify A/B cases (multi-word English title/artist/album plus Chinese cases) and adopt a change only if measured results improve without harming current matching.

Document inconsistencies identified by review were fixed in their source documents rather than creating another issue file: the architecture tree was refreshed, the Spotify redirect example was aligned to the current 8000 callback path, Shortcut step numbering was corrected, SPEC configuration wording was aligned to `.env` + `config/*.yaml`, and stale Spotify/Local-AI scope wording was updated.

### Product decision: AI semantic retry for misparsed Spotify requests

The real Siri case `播放死亡是生命的終點` showed an important failure class: a deterministic parser may return a syntactically valid `spotify_play_track` action while having split the utterance incorrectly. Therefore future Local AI eligibility must not be limited to complete parser failure.

Long-term intended behavior:

```text
original Siri text
→ deterministic parser
→ deterministic Spotify resolution
   ├─ confident usable result → continue deterministic path
   └─ no usable result / low-confidence result / suspected entity split error
        → AI semantic retry (Spotify play-track scope only)
        → strict schema
        → deterministic grounding against the original utterance
        → policy gate
        → rerun deterministic Spotify resolver
```

The current deterministic `的` reconstruction fallback is a tactical fix and should remain while AI is disabled. It is not the desired pattern for accumulating an unlimited list of language-specific repair rules.

AI semantic retry still must not rank Spotify candidates, select Spotify track IDs/URIs, select clarification candidates, or execute playback directly. Existing deterministic clarification remains authoritative.

Because Phase 0.5 did not pass the safety/quality gates, this semantic-retry path must first run in `shadow` mode. A parser/resolver disagreement is useful failure-corpus data, not permission to execute model output.

## Local AI Phase 0.5 Preparation (2026-09-18)

- 使用者已在 LM Studio 下載三個 planned benchmark candidates：
  - Qwen3 0.6B
  - Qwen2.5 1.5B Instruct
  - Qwen3 4B
- 以上模型在準備階段只確認「已下載」；benchmark 最終結果見下方，沒有選定 production model。
- Phase 0.5 實測 runbook 已建立：`docs/LOCAL_AI_MODEL_POC_RUNBOOK.md`。
- Runbook 要求三個模型使用同一份固定測資，分別測 prompt-only JSON 與 structured-output（若支援），並量測 intent/semantic accuracy、hallucination、post-grounding false accept、false execution、clarification accuracy、P50/P95 latency 與資源使用。
- 實測由 Codex 在真實 Windows + LM Studio 環境依 runbook 執行；未達門檻前不得把任何模型標成通過。
- 目前 LM Studio 開發 endpoint 由使用者回報為 `http://192.168.0.199:1234`；production same-host target 仍為 loopback `127.0.0.1:1234`。

## Local AI Phase 0.5 PoC Execution Attempt (2026-09-19)

- 已新增隔離的 `scripts/ai_model_poc.py`、`tests/fixtures/ai_intent_cases.json`（103 筆固定測資）與 `tests/unit/test_ai_model_poc.py`。
- PoC 目前只呼叫 LM Studio OpenAI-compatible API，使用 strict Pydantic schema、OpenCC canonical grounding、hostile-input fail-closed 檢查與本地 CSV/JSONL/SUMMARY 輸出；未接入 `/command`、`app.main`、Spotify 播放、Windows adapters、shutdown、firewall 或 `start.bat`。
- 新增 PoC unit test 7 passed；完整 `tests/unit` 為 93 passed，保留 2 個既有 dependency deprecation warnings。
- 實機 preflight 的最後讀回為：`http://192.168.0.199:1234/v1/models` 僅回傳 `text-embedding-nomic-embed-text-v1.5`；`lms ps` 顯示沒有載入模型；`lms load qwen3.5-0.8b --identifier=qwen3.5-0.8b -y` 回報找不到目前 indexed model key。
- 使用者確認根因是 LM Studio 在索引目錄超過 7000 個檔案後停止索引；將模型目錄移到較小的位置後，model library 已恢復。
- 修正後唯讀讀回已確認 `lms ls --llm` 與 `/v1/models` 都列出三個候選 exact IDs：`qwen3.5-0.8b`、`qwen2.5-coder-1.5b-instruct`、`qwen3-4b`；三者目前尚未載入記憶體（`lms ps` 顯示 No models are currently loaded）。
- LM Studio index blocker 已解除；benchmark execution 結果見下節。

## Local AI Phase 0.5 Benchmark Result (2026-09-19)

- Final artifacts：`runtime/ai_poc/2026-09-19-full-v2/`（runtime/ 為 ignored local output）；同一份 103-case fixture 已對三個實際 indexed LLM 各跑 prompt-only JSON 與 structured-output，temperature=0、max_tokens=512、timeout=5 秒、一次只載入一個模型。
- Environment：Windows 11 `10.0.26200`、Python `3.14.7`、AMD64 Family 25 Model 97、約 32 GB RAM；LM Studio `0.4.20+1` / ProductVersion `0.4.20.0`，CLI commit `71bd99c`；endpoint 為開發用 LAN `http://192.168.0.199:1234/v1`，不是 production loopback acceptance。
- 實際模型與量化：`qwen3.5-0.8b`（Q4_K_M、529.30 MB；不是原規劃的 Qwen3 0.6B exact model）、`qwen2.5-coder-1.5b-instruct`（Q4_K_M、986.05 MB；是 Coder variant，不是原規劃的 plain Qwen2.5 1.5B Instruct）、`qwen3-4b`（Q4_K_M、2.50 GB）。
- `qwen2.5-coder-1.5b-instruct`：prompt/schema semantic accuracy 都 `67.96%`、clarification `76.92%`、P95 `201.6/207.4 ms`；post-grounding false accept `2.91%`、false execution `0.97%`。
- `qwen3-4b`：prompt/schema semantic accuracy 都 `66.99%`、clarification `30.77%`、JSON success `81.55%`、P95 `3313.3/3306.7 ms`；post-grounding false accept `1.94%`、false execution `0.97%`。
- `qwen3.5-0.8b`：prompt/schema semantic accuracy `6.80%/7.77%`、clarification `15.38%`、JSON success `11.65%`、P95 `1722.3/1814.6 ms`；未出現 false execution 或 post-grounding false accept，但主要原因是大量 reasoning-only / non-JSON output，不代表可用安全通過。
- Phase 0.5 benchmark execution 已完成，但三個實際模型都未達初始 hard safety（false execution=0、post-grounding false accept=0）與 quality targets（semantic/clarification >=90%、P95 <=2 秒）；summary 明確寫入 **no tested model met all initial PoC thresholds; do not proceed to production integration**。不選 production model、不接入 `/command` 或正式 Agent。
- 後續若要繼續 Local AI，最小下一步是先針對 failure corpus 改善 prompt / clarification-context / deterministic grounding，另開下一輪可比 PoC；目前不能因 benchmark 完成而宣稱 production readiness。

## Local AI Second-round Architecture/Security Review (2026-09-19)

- 已依 `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` 的 review request 完成第二輪 review；採納的規則已寫回 `docs/ARCHITECTURE.md`、`docs/SECURITY.md`、`docs/API.md` 與 `docs/NETWORKING.md`。
- 初次 production-facing AI scope 收斂為 `spotify_play_track` / `unknown`；pause/resume/skip、clarification selection、app/volume/system actions 維持 deterministic。帶有 `clarification_token` 的 `/command` 必須繞過 AI。
- Production LM Studio endpoint 是 `127.0.0.1` hard gate；目前 LAN endpoint 只可作隔離 benchmark，不能由 runtime 自動 fallback。AI 前置 eligibility gate、RawAIIntent → GroundedAIIntent → AIPolicyGate trust states、strict versioned schema 與 off/shadow/fallback promotion gate 已明確化。
- `SpotifyClarificationStore` 已補上 bounded `failed_attempts` / `max_attempts`（預設最多三次不清楚回覆），並以同一個 lock 保護成功選擇與失敗次數更新；unit tests 已覆蓋 attempt exhaustion、並發成功選擇與並發失敗次數上限。
- 本次 source regression 完整 pytest 為 `102 passed`，保留 2 個既有 dependency deprecation warnings；compileall、pip check 與 diff check 通過。安裝目錄兩個服務檔 hash 已與 source 一致，並以 runtime venv 完成並發 clarification smoke test；隔離的 `127.0.0.1:8001` runtime `/health` 回傳 200；port 8000 現行進程尚未重啟。
- Review 結論仍是 gated future design，不是 Local AI production execution approval；clarification abuse-resistance 的 source/unit gate 已完成，Local AI 的 minimal trust-state/eligibility/transport skeleton 已完成，下一步是 shadow failure-corpus 與 candidate-quality 驗證。

## Local AI Guarded Semantic-Retry Skeleton (2026-09-19)

- 已完成第一個 source/unit implementation slice：`RawAIIntent` / `GroundedAIIntent`、strict schema、boundary-aware deterministic grounding、Spotify semantic-retry eligibility gate、`AIPolicyGate` 與 loopback-only LM Studio transport adapter。
- `/command` 的 clarification token 分支仍在 AI 之前直接走既有 deterministic store；Local AI 只會在安全 Spotify parser miss 或明確 resolver-failure retry signal 上被考慮。
- Runtime 設定預設為 `LOCAL_AI_ENABLED=false`、`LOCAL_AI_MODE=off`。`shadow` 只記錄 bounded category diagnostics、永不回傳 executable action；`fallback` 需要 `LOCAL_AI_FALLBACK_APPROVED=true` promotion gate，尚未獲 production approval。
- 新增 unit/API coverage：strict schema authority-field rejection、slot grounding、eligibility rejection、loopback endpoint、transport bounds、shadow fail-closed 與 clarification bypass。
- 已完成一次受限真實 loopback LM Studio shadow smoke：`127.0.0.1:1234/v1` 的 `qwen2.5-coder-1.5b-instruct` 在 `播放晴天` 上回傳 `shadow_accepted`，且 `execution_allowed=false`；另一個輸入安全落到 `accepted_unknown`。期間確認 LM Studio 此版本拒絕 `json_object`，adapter 已改用已驗證的 strict `json_schema`。
- 修訂後 benchmark 已完成：fixture 共 109 cases；與 production eligibility 對齊後，沒有明確歌名的 unresolved-reference / hallucination cases 在送模型前標為 deterministic-only，仍保留在 corpus 量測 safe-unknown，不把它們混入 supported AI accuracy。
- `qwen2.5-coder-1.5b-instruct` 的 prompt/schema 兩種模式結果一致：supported semantic `95.24%`（63 cases）、intent `100%`、semantic-retry `100%`、deterministic-only safe-unknown `100%`、safety-only safe-unknown `100%`、false execution `0%`、post-grounding false accept `0%`、P95 `203.8/212.4 ms`。剩餘 3 個 supported failure 都是 `X 專輯的 Y` 的 album/artist role 誤判；一次額外 role-prompt A/B 未帶來穩定淨改善，未寫入 production prompt。
- Review 後補強：hostile `safety_only` case 不再呼叫模型；`一下` 不再可被 grounding 成歌名，但複合口令 `播放一下晴天` 仍保留正常 track boundary。
- 規格權威衝突已於 2026-09-19 由使用者明確決定「一切照新」後解除：`docs/SOURCE_SPEC.md` 保留為唯讀歷史規格，不再覆蓋目前維護中的 `SECURITY.md` / `SPEC.md` / `ARCHITECTURE.md`。原 §94/§95 的 V1 no-AI 限制視為已被後續 guarded Local AI 產品決策 supersede。這只解除文件 blocker，不等同 fallback promotion。
- 這是 loopback shadow / offline corpus evidence，不是 fallback promotion：AI 仍預設 `off`，尚未完成 Windows/Spotify/Siri acceptance、independent review 或任何 fallback promotion。既有工作樹中的其他 Windows/Spotify review 修正未與本 AI slice 混提交。

## Local AI Spec Authority Decision (2026-09-19)

- 使用者明確決定：**一切照新**。目前維護中的 `SECURITY.md`、`SPEC.md`、`ARCHITECTURE.md` 與其已接受的後續產品決策為有效規格；`docs/SOURCE_SPEC.md` 僅保留歷史來源，不再作為衝突時的 final arbiter。
- `AGENTS.md` 已同步改為上述 active-spec priority；`docs/MIGRATION_CHECKLIST.md` 已把 SOURCE_SPEC #94「V1 不使用 AI/LLM」標記為被 2026-09-18 guarded Local AI 產品決策 supersede。
- 此決定解除的是**文件／治理 blocker**。它沒有自動批准 production fallback，也沒有改變目前 installed runtime 的 shadow-only / `fallback_approved=false` 狀態。
- 下一個 AI gate 是獨立 promotion review：只有在明確核准後，才可把 AI semantic result 接到可執行的 Spotify fallback path。

## Local AI Shadow Remediation / Auditable Evidence (2026-09-19)

- `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` 已新增 historical-scope / supersession record；早期 `select_candidate`、clarification AI、播放控制等廣泛概念不得再被當成第一整合 scope。
- 已新增 `docs/LOCAL_AI_BENCHMARK_2026-09-19.md`，固定 source commit、fixture hash、prompt/schema hash、LM Studio/model/config 與 sanitized metrics；不提交 raw prompts、model output、tokens 或 credentials。
- GitHub PR #5 的 independent gate review 原判定 production fallback **NO-GO**、shadow-only remediation **GO**。其中 SOURCE_SPEC authority conflict 已於 2026-09-19 依使用者「一切照新」決定解除；production-aligned shadow acceptance 亦已完成。正式 fallback 仍需獨立 promotion review，不能因文件 blocker 解除就自動開啟。

## Local AI Production-Aligned Shadow Acceptance Check (2026-09-19)

- 以 source `893b115` 在隔離 `127.0.0.1:8001` runtime 做 guarded shadow check：`/health` 回傳 200；authenticated `/info` 回報 `mode=shadow`、adapter 已設定、`fallback_approved=false`；parser-miss 的 `幫我放晴天` 只產生 bounded `local_ai status=shadow_accepted`，沒有 executable action、Spotify playback 或 fallback；unsupported-domain 輸入被 eligibility gate 拒絕。
- 部署前的 readback 確認 `D:\ai\windows-siri-agent` 是 pre-AI；完成 loopback gate 後，已先備份 `runtime.py`、`config.py`、`routes_command.py` 到 `D:\ai\windows-siri-agent\work\local-ai-shadow-backup-20260919-203734`，再以可還原方式同步六個 Local AI modules、runtime/config/route wiring，並加入 `LOCAL_AI_MODE=shadow`、`LOCAL_AI_FALLBACK_APPROVED=false`。
- 已在實際 port 8000 installed runtime 完成 shadow-only acceptance：`/health` 回傳 200；authenticated `/info` 回報 `mode=shadow`、adapter 已設定、`fallback_approved=false`；parser-miss 的 `幫我放晴天` log 為 `shadow_accepted`，unsupported-domain 的 `幫我播放一首歌曲` log 為 `ineligible`，兩者都沒有 executable action 或 Spotify playback。
- LM Studio listener 已重新讀回為 `127.0.0.1:1234`，不再是 `0.0.0.0`。這只完成 installed shadow acceptance，不是 fallback promotion；port 8000 目前仍是 shadow、fallback 關閉，後續仍需獨立 promotion review 才能考慮 executable fallback。

## Local AI Independent Promotion Review (2026-09-19) — NO-GO

- Standards 與 Spec 兩個獨立 review 均完成；結論是 **NO-GO for executable fallback**，installed runtime 必須維持 `shadow` / `LOCAL_AI_FALLBACK_APPROVED=false`。
- Promotion evidence 仍不完整：目前 benchmark 明確不宣稱 Windows Agent、Spotify playback、Siri 或 production fallback acceptance；green unit tests 不能替代 real-host acceptance。
- High-priority implementation gaps：啟用 AI 但省略 `LOCAL_AI_MODE` 時 config 會選 `shadow` 而非 fail-closed `off`；eligibility 未完整阻擋 UNC path 與未由 deterministic parser 處理的 version marker；`spotify:playlist:` 等非 track/album/artist Spotify URI 尚可進入 AI。
- Grounding gap：同一個原文 span 可同時被接受為 `track` 與 `artist`，沒有阻止 cross-slot inference；這與「不得發明缺失 artist」的規格不符。
- Semantic-retry wiring gap：eligibility 列出的 low-confidence / entity-segmentation signal 已在後續 source slice 接上；仍沒有 production fallback acceptance evidence。
- Next smallest safe action：完成 source-level route proof 與 independent promotion review；之後才可考慮 separate Windows/Spotify/Siri fallback acceptance。不得因本 review 結束而修改 installed `.env` 或啟用 fallback。

## Local AI Gate Hardening Slice (2026-09-19)

- 已先以 TDD 補上 regression coverage：AI enabled 但省略 `LOCAL_AI_MODE` 時 fail-closed 為 `off`；UNC path、任意 `spotify:` URI、明確版本標記不得進入 AI retry；grounding 不得重用 track span 作為 artist/album。
- Deterministic gate / grounding 已修正：config mode default 改為 `off`；authority filter 改為阻擋所有 `spotify:` scheme 與 UNC；version marker 一律交回 deterministic parser；相同 canonical span 只保留第一個 semantic slot。
- Targeted Local AI/config tests：`25 passed`，2 個既有 dependency deprecation warnings；compileall 與 pip check 通過，`git diff --check` 只有既有 CRLF warnings。
- 以 LM Studio loopback `127.0.0.1:1234`、`qwen2.5-coder-1.5b-instruct`、固定 109 cases、runtime-aligned timeout 2 秒重跑：prompt/schema 都是 transport/JSON/schema/intent 100%、semantic 95.24%、semantic-retry 100%、deterministic-only 與 safety-only safe-unknown 100%、post-grounding false accept 0%、false execution 0%；P95 為 201.8/202.1 ms。
- 完整 pytest 為 `144 passed, 4 failed`；4 個 failure 屬目前未提交的非 AI Spotify personalization/auth 變更（saved-track lookup 與 scope expectation），不是本 slice 的 Local AI tests。故 promotion 仍維持 **NO-GO**，且尚未重新部署或啟用 fallback。
- 已以可還原 backup `D:\ai\windows-siri-agent\work\local-ai-gate-backup-20260919-214605` 同步三個 gate 檔案到 installed Agent；hash readback 與 source 一致。重啟後 `/health`=200，authenticated `/info` 回報 `mode=shadow`、`adapter_configured=true`、`fallback_approved=false`。
- Installed shadow regression：`幫我放晴天` 回傳 `INVALID_COMMAND` 且 log 為 `shadow_accepted`、沒有 executable action；`幫我放一下晴天 remix` 回傳 `INVALID_COMMAND` 且 log 為 `version_marker_requires_deterministic_parser`、沒有 model transport 或播放。LM Studio listener 維持 `127.0.0.1:1234`。
- **本輪 Local AI shadow gate hardening milestone 完成**；這不是 fallback promotion，也不代表 Windows/Spotify/Siri executable fallback acceptance。resolver signal wiring 已在後續 source slice 完成；下一個 blocker 是完整測試／corpus 重跑與獨立 promotion gate。

## Spotify Resolver Semantic-Retry Signal Wiring (2026-09-19)

- `TrackResolution` 現在保留 bounded `retry_signal`；parser 已提供 artist/title split、且重建完整歌名仍無結果時回傳 `SPOTIFY_ENTITY_SEGMENTATION_RISK`。
- Spotify Search 只有單一候選但最高分低於既有 `0.70` safe threshold 時，回傳 `SPOTIFY_LOW_CONFIDENCE_TRACK`；多候選 ambiguity 仍維持既有 deterministic clarification，不改成 AI 猜測。
- `SpotifyService` 只在沒有 trusted track 且不是 clarification 的情況，把 signal 映射成既有 `OperationResult.error_code`；因此現有 `/command` eligibility gate 可辨識 retry，AI 仍須經過既有 grounding/policy，shadow 仍不可執行。
- 新增 catalog/service regression tests；`tests/unit/test_spotify_catalog.py` 與 `tests/unit/test_spotify_service.py` 共 `36 passed`。這是 source/unit evidence，不是 Windows/Spotify/Siri fallback acceptance。
- Source change 後重跑固定 109-case loopback corpus：`qwen2.5-coder-1.5b-instruct`、LM Studio `127.0.0.1:1234`、timeout 2 秒；prompt/schema 的 transport、JSON、schema、intent 均 `100%`，semantic `95.24%`、semantic-retry `100%`、deterministic-only 與 safety-only safe-unknown `100%`、post-grounding false accept `0%`、false execution `0%`，P95 為 `196.1/200.2 ms`。這是 benchmark evidence，未包含 Windows/Spotify/Siri executable acceptance。
- Installed Agent 未重新部署，`LOCAL_AI_FALLBACK_APPROVED=false` 保持不變；source review 已完成，下一步只剩使用者另行指示 installed shadow regression 或 production promotion decision，期間保持 shadow/off。

## Local AI Resolver Seam Review Hardening (2026-09-19)

- 依 Standards／Spec review 補上原始 utterance boundary gate：只有原文符合 parser 的中文 `播放 X 的 Y` split、且 split 與重建歌名都無結果時才回傳 `SPOTIFY_ENTITY_SEGMENTATION_RISK`；普通 artist+track miss 維持 `SPOTIFY_TRACK_NOT_FOUND`。
- 將既有 resolver safe threshold 明確記錄為 `0.70`；單一候選低於 threshold 才是 `SPOTIFY_LOW_CONFIDENCE_TRACK`，多候選 ambiguity 仍 deterministic clarification。
- `/command` 現在只沿著 AI semantic-retry seam 傳遞原始 utterance；新增真實 `SpotifyCatalog → SpotifyService → /command` shadow test、approved-test-only fallback 後再次 deterministic resolve test，以及 ambiguity 不進 AI test。這不是 Spotify 搜尋／播放／個人化功能擴充。
- 完整 pytest `160 passed`、2 個既有 dependency deprecation warnings；compileall、pip check、git diff check 通過。這些仍是 source/unit evidence，不是 installed Windows/Spotify/Siri acceptance。
- 本輪仍只改 source integration seam 與 AI safety documentation；後續只做可還原 installed shadow sync，`LOCAL_AI_FALLBACK_APPROVED=false` 與 production fallback **NO-GO** 保持不變。

## Local AI Resolver Seam Installed Shadow Regression (2026-09-19)

- 以可還原 backup `D:\ai\windows-siri-agent\work\local-ai-resolver-shadow-backup-20260919-221500` 保存 installed 原始的四個 AI integration seam 檔案，再同步 source `78fed3c` 的 `catalog.py`、`spotify_service.py`、`command_service.py`、`routes_command.py`；四個 source/deployed SHA-256 readback 一致。
- Installed compileall 與 config readback 通過；重啟後 port 8000 `/health` 正常，authenticated `/info` 回報 `mode=shadow`、`adapter_configured=true`、`fallback_approved=false`；LM Studio listener 維持 `127.0.0.1:1234`。
- 安全 parser-miss 的 installed log 產生 `local_ai status=shadow_accepted`，沒有 executable action；unresolved-reference 輸入由 `unresolved_reference` gate 拒絕。這是 installed shadow evidence，不是 installed resolver-signal、Spotify playback、Siri 或 fallback acceptance。
- Installed `.env` 未開啟 fallback；下一步仍是保留 shadow/off，除非使用者另行要求獨立 production promotion decision。

## Local AI Product Decision (2026-09-18)

- 舊規則「V1 不得加入 LLM integration」已取消。
- V1 允許 **Local LLM**，目前指定 runtime 方向為 LM Studio；不使用雲端 LLM fallback。
- AI 採 rule-first / guarded semantic-retry；第一版 AI scope 只處理 Spotify free-form `spotify_play_track` / `unknown` semantic parsing。AI eligibility 不只包含 parser 完全失敗，也可包含 deterministic parser 已產生 `spotify_play_track`、但 Spotify resolver 回傳 no-result／低信心／疑似 entity split 錯誤的情況；歌曲 clarification selection 維持 deterministic。
- AI 輸出必須通過 strict closed schema 與 deterministic slot grounding；`track` 未 grounded 時不得建立 `spotify_play_track`。
- shutdown / shutdown confirmation / force-close / firewall / system-administration 永久不交給 AI 解析。
- LM Studio 若與 Agent 同機，production acceptance 目標為 loopback (`127.0.0.1:1234`)；目前使用者回報的 `192.168.0.199:1234` 只視為開發/測試 endpoint，尚未視為正式安全配置。
- 完整架構提案見 `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md`。
- Phase 0.5 model feasibility PoC 已完成但無模型通過；第二輪 architecture/security review 已完成，這仍不代表 Local AI 已接入正式 Agent。

## New Product Decision / Implementation State (2026-09-18)

以下規則已完成 source implementation、測試與 Windows Agent 直接驗證；Siri Shortcut E2E 仍未完成：

- 一般指定歌曲播放不支援 Live / Concert / Tour / 演唱會 / 現場版本；Spotify Search 後先排除這些候選。
- 使用者明確要求 Live / 現場版時，回覆目前只支援正式錄音版本，不播放 Live。
- 歌名、歌手、專輯 matching 要加入繁簡中文正規化；只消除字形造成的假歧義，不得把真正不同歌手或不同錄音誤合併。
- 排除 Live 並完成 matching 後若仍 ambiguous，最多回 3 個 trusted candidates。
- Siri Shortcut 要朗讀這 2～3 個候選並反問使用者；若只有 2 個就只列 2 個，不湊滿 3 個。
- 第二輪 clarification 只能在 server 建立的短效候選集合中選擇，支援「第一首／第二首／第三首／歌手／專輯」等回答；client 不得任意指定 Spotify URI 或 track ID。
- clarification context 必須短效過期。
- 暫時 bug 規格見 `docs/BUG_SPOTIFY_SIRI_DISAMBIGUATION.md`；完成所有實作、測試與 Siri E2E 後才刪除該檔案。

## Real-World Acceptance (2026-09-18)

以下結果來自目前安裝的 `D:\ai\windows-siri-agent`，不是 mock test：

- `/spotify/status` 回報已授權，scope 為目前播放控制所需的兩項 scope。
- Spotify Connect 裝置已被 Agent 找到。
- `播放周杰倫的晴天 (葉惠美)` 實際回傳成功，播放曲目為 `晴天`，專輯為 `葉惠美`。
- `暫停` 實際回傳成功；上一輪舊口令 `下一首` 的單曲重播 bug 已修正，新口令 `下一首歌` 尚未重新完成 Siri 實機驗證。
- 部署消歧修正後，直接對 Windows Agent 的自然語句 `播放周杰倫的晴天，專輯葉惠美` 實際播放 `晴天` / `葉惠美`。
- 部署消歧修正後，直接對 Windows Agent 的 `播放周杰倫的晴天原版` 實際播放 `晴天` / `葉惠美`，證明原版意圖不會把搜尋帶到無關的 `Original Soundtrack` 結果。
- 先前直接對 Windows Agent 的 `播放周杰倫的晴天` 實際播放 `晴天` / `葉惠美`，證明同歌手 studio 優先規則生效；這些都不是 Siri Shortcut 端到端結果。
- 舊版 `播放晴天現場版` 曾回傳 `SPOTIFY_AMBIGUOUS_TRACK`；最新部署後改為 `SPOTIFY_LIVE_UNSUPPORTED`，在搜尋前拒絕且不播放 Live。
- 不帶歌手的 `播放葉惠美專輯的晴天` 若 Spotify 回傳不同歌手的同名／同專輯候選，會進入最多三首 clarification，不會猜測歌手；帶歌手的自然專輯句已成功。
- 最新部署後以 `scripts/start.bat` 啟動的 Agent 已直接驗證：`播放周杰倫的晴天，專輯葉惠美` 成功播放；`播放晴天現場版` 回傳 `SPOTIFY_LIVE_UNSUPPORTED` 且不搜尋；模糊的 `播放Stay` 回傳最多 3 個候選、`clarification_required=true` 與 opaque token；無效 token 回傳 clarification invalid 且不呼叫 Spotify。
- 上述較早的 controlled run 已正常停止；本次修正驗證時另外啟動的 Agent 目前仍在 port 8000，供使用者重新測試 Shortcut。
- 以過期 clock 觸發真實 Spotify refresh endpoint 後，`暫停` 仍實際回傳成功；token 未輸出到終端或 log。
- API key 未出現在測試 log 中。



## Resolved Source Bug: Chinese title containing 「的」 misparsed as artist + track (2026-09-19)

- 使用者實機案例：`播放死亡是生命的終點` 會完成 Shortcut，但沒有實際播放。
- Root cause：rule parser 的中文 artist grammar 使用 `播放<artist>的<track>`。因此 bare title `死亡是生命的終點` 會先被解析成 `artist=死亡是生命`、`track=終點`，Spotify primary search 變成 `track:終點 artist:死亡是生命`。
- Source 已在 `SpotifyCatalog` 加入保守 fallback：只有當 artist+track primary search 沒有任何可用候選、且沒有 album hint 時，才把原 split 重組為 `死亡是生命的終點`，以 bare track title 再搜尋一次。
- 若 primary artist+track search 本來有結果，fallback 不會執行，因此既有 `播放周杰倫的晴天` 等 artist grammar 行為不變。
- fallback 仍只使用 Spotify Search API，結果仍需通過既有 Live filtering、trusted `SpotifyTrackRef`、ranking / ambiguity safety；不接受 client URI / track ID。
- 已新增 regression test，固定驗證 primary query `track:終點 artist:死亡是生命` 無結果時會 retry `track:死亡是生命的終點` 並解析為可信 track。
- 若 fallback 後只有一個候選的精確歌名，現在會優先選擇該精確標題，不會被 Spotify 回傳的相似歌名誤導成 clarification；多個精確標題仍維持 ambiguity safety。
- 先加入「精確歌名 + 相似歌名」的紅色 regression test，再完成 catalog 修正；source 完整 pytest 為 `106 passed`，保留 2 個既有 dependency deprecation warnings。
- 已部署 `catalog.py`、`schemas.py` 與 `actions.py` 到 `D:\ai\windows-siri-agent`，compileall 與 pip check 通過。
- 2026-09-19 controlled Windows Agent HTTP 驗證：`播放死亡是生命的終點` 實際回傳 `success=true`，播放 `死亡是生命的終點` / `SASIOVERLXRD` / `納薩力克`；尚未重新做 iPhone Siri Shortcut E2E，因此不把 Shortcut 驗收標成完成。

## Resolved Source Bug: Long Spotify title rejected by 200-character metadata cap (2026-09-19)

- 使用者實機回報：歌名較長時會直接變成無效指令。
- Source inspection 找到長度限制不一致：`POST /command` 與 parser 允許最多 300 字元，但 `ValidatedAction.track/artist/album` 與 `ActionRequest.track/artist/album` 原本只允許 200 字元。
- 因此長度 201～約 297 字元的歌曲名稱可以先通過 command/parser，卻在建立 Spotify action 時被 Pydantic metadata cap 擋掉。
- Source 已將 Spotify `track` / `artist` / `album` 的封閉上限由 200 對齊到 300；沒有放寬 shell/path/URL/URI 等既有安全邊界。
- 已新增 regression tests：220 字元歌曲名稱必須可由 parser 建立 `spotify_play_track`；250 字元 Spotify metadata 可通過 schema，301 字元仍必須拒絕。
- 目前只完成 source + regression test 寫入 GitHub；尚未在真實 Windows runtime 執行完整 pytest、部署並用 iPhone/Siri 重測長歌名，因此不得標成 real-world acceptance 完成。

## Resolved Bug: `暫停音樂` parser alias (2026-09-18)

- 使用者實機回報 iPhone Shortcut 的「暫停音樂」沒有作用；原 parser 只有 exact alias `暫停`，因此請求未進入 Spotify pause service。
- 先加入回歸測試確認原行為失敗，再加入繁體、簡體與英文 `pause music` 的封閉 alias；目前完整 unit tests 為 91 passed，保留既有 2 個 dependency deprecation warnings。

## Changed Command Wording: `下一首歌` / `上一首歌` only (2026-09-18)

- 為降低 Siri 把「下一首」聽成「下一週」、把「上一首」聽錯的風險，中文 parser 現在只接受精確口令 `下一首歌` / `上一首歌`，分別對應 `spotify_next` / `spotify_previous`。
- `下一首`、`下一曲`、`上一首` 與 `上一曲` 已從 closed alias 移除並由 regression test 拒絕；英文 `next track` / `previous track` 等既有英文閉集合保留。
- README、SPEC、Spotify、Siri Shortcut 與本地 AI 測試文件已同步改用完整中文口令；原始唯讀 `docs/SOURCE_SPEC.md` 未修改。
- source parser tests 已通過；部署後 runtime parser 直接驗證 `下一首歌` / `上一首歌` 可解析，四個舊中文短口令均回傳 `INVALID_COMMAND`。新的 Siri 端到端口令尚未重新驗證，完成前不把新口令標成 Siri acceptance。
- 最新一次 iPhone 嘗試沒有在 Agent log 產生 `spotify_previous`；手機端出現 `parse_command` 的 `INVALID_COMMAND`，其他相鄰請求仍是 `spotify_next`。因此「上一首歌」的 Siri → Shortcut 交接仍未通過，不能把 Siri 的「設在什麼時候」誤判成 Spotify 播放錯誤。

## Scope Decision: 暫停上下歌 Siri 功能 (2026-09-19)

- 使用者決定放棄 Siri 的下一首／上一首控制，不再追查 Siri 將語音攔截為原生媒體或排程指令的問題。
- V1 目前聚焦播放、暫停與指定歌曲；既有 `spotify_next` / `spotify_previous` closed actions 暫保留在 Agent code，不列入後續 Siri acceptance，也不因 Siri 問題擴大 alias。
- 部署到 `D:\ai\windows-siri-agent` 後，直接送出完整文字 `暫停音樂` 的真實 HTTP 回應為 `success=true`、`action=spotify_pause`，並成功找到 Windows Spotify 裝置。
- 直接 Agent 驗收後，使用者重新測試 iPhone Siri Shortcut，確認「暫停音樂」已能成功暫停 Spotify；這個基本控制路徑已通過，但不等同於新的歌曲消歧／三選一 clarification E2E。

## API Key Rotation / Environment State (2026-09-19)

- `D:\ai\windows-siri-agent\.env` 的 `SIRI_AGENT_API_KEY` 已換成新的高熵 key；Spotify Client ID、Redirect URI、Token path 與其他 runtime 設定未改動。
- `.env` 仍被 Git 忽略；ACL 已收斂為 SYSTEM、Administrators 與目前登入使用者，沒有保留一般 Authenticated Users 的讀寫權限。
- 以隔離的 `127.0.0.1:8001` runtime 讀取新 `.env` 後，authenticated `/info` 回傳 HTTP 200；沒有輸出或寫入 key。
- 使用者已更新 iPhone Shortcut 的 `X-API-Key`；之後以 `scripts/start.bat` 重啟 port 8000，`/health` 回傳 200，使用新 key 的 authenticated `/info` 回傳 200，Spotify 授權與既有 playback scopes 仍在。API key rotation 的 Windows/env 切換已完成；換 key 後的 iPhone 實機播放／暫停回歸仍待使用者測試。
- 使用者隨後確認換 key 後的 iPhone Siri Shortcut 已正常；重啟後 log 收到 iPhone 的指定歌曲、clarification 與成功播放請求。API Key rotation 後的 iPhone → Agent → Spotify 播放回歸已通過。

## Siri Shortcut Stable Dictation Flow Documentation (2026-09-19)

- `docs/SIRI_SHORTCUT.md` 已更新為目前實機通過流程：一般指令維持 Siri 語音；只有 clarification 分支在候選朗讀後執行「關閉 Siri 並繼續」→ 第二次 Dictate Text → POST token。
- clarification 必須在同一次 Shortcut 執行內完成：Speak candidates → Dismiss Siri and Continue → 第二次 Dictate Text → POST token；此順序已實機避免 Siri 把「第一首」攔截成原生排程／提醒指令。
- 文件建議 Dictate Text 語言設為「中文（台灣）」並使用較獨特的 Shortcut 名稱（例如「Windows 管家」）降低 Siri 原生語意衝突。
- 已加入排查分流：Agent 沒收到 POST → iPhone/Shortcut 問題；收到 `text=下一週` → Siri ASR 問題；收到 `text=下一首` 但未執行 → Agent parser/service 問題。
- 此流程已完成 iPhone 實機 clarification 全語音 E2E 驗收。

## Siri Shortcut Clarification E2E Acceptance / Remaining Siri Limitation (2026-09-19)

- 使用者已在 iPhone 實機完成第一輪歌曲指令 → Agent 回傳最多三個候選與 `clarification_token` → Shortcut 保存 token → 第二輪以「第一首」+ token POST → Agent 選取原 trusted candidate 並真實播放 Spotify。
- 第二次 POST 的 `text` 與 `clarification_token` wiring 已確認正確；播放成功證明 server-side clarification selection 與 player path 已被 iPhone E2E 觸發。
- Shortcut HTTP response 在實機上可能先以文字呈現，必須先用「從 URL 內容取得辭典」再取 `message` / `clarification_token`。
- iOS Shortcut 的 If 實作改以「clarification_token 是否包含任何數值」判斷是否進入 clarification，避免把 boolean false 當成「有值」。
- 從「嘿 Siri」啟動 Shortcut 時，第二輪短語音仍可能被 Siri 原生語意攔截並追問「要設在什麼時候」；手動從 Shortcuts App 執行則正常，因此這不是 Windows Agent / Spotify clarification service 的失敗。
- 最終實機修正：不要把「關閉 Siri 並繼續（Dismiss Siri and Continue）」放在 Shortcut 最前面；只在 clarification 分支內，於候選朗讀後、第二次聽寫前執行。使用者已確認這樣可避開 Siri 攔截，同時保持第二輪全語音輸入。
- 詳細實機報告見 `docs/SIRI_SHORTCUT_CLARIFICATION_E2E_REPORT.md`。
- 實機也觀察到不帶歌手的模糊歌名會出現偏冷門候選；目前 `SpotifyCatalog` ranking 沒有 popularity tie-breaker，Search request 也未指定 `market=TW`。這是後續搜尋品質工作，不應以降低 ambiguity safety 為代價。
- 本輪截圖曾顯示部分 API key；不得把 secret 寫入 Git/log，建議旋轉 API key。

## Historical Blocker: Siri Shortcut clarification E2E (resolved 2026-09-19)

- 實機重現時，Siri Shortcut 實際送到 Agent 的文字只有 `播放晴天`，沒有帶歌手或專輯提示。
- 舊的實機重現中，Spotify 搜尋回報 `SPOTIFY_AMBIGUOUS_TRACK`，候選包含原版 `晴天`／`葉惠美`、`2004無與倫比演唱會` 及其他 `Live` 版本；Agent 當時正確拒絕隨機播放。因此問題不是 OAuth、Connect 裝置或 Spotify 播放控制失敗，而是 Shortcut 語音輸入與選曲消歧尚未完成。
- 現有 `播放周杰倫的晴天 (葉惠美)` 可作為文字測試提示，但括號形式不是可靠的語音介面；Siri 可能把括號內容念成普通詞語或改變順序。
- 最新產品決策已不再支援 Live 播放：Live / Concert / Tour / 演唱會 / 現場候選應直接排除；明確要求 Live 時回覆只支援正式錄音版本。
- 繁簡中文 matching normalization、Live 排除、最多三首 trusted candidates 與短效 clarification context 已完成 source/runtime 驗證。
- 此項已於 2026-09-19 完成實機驗收：Shortcut 可朗讀候選、保存 token、把第二輪選擇與 token 一起送回，並完成真實 Spotify 播放。
- 基本 Spotify Shortcut 控制路徑已有「播放原版」「暫停音樂」成功紀錄；歌曲消歧／三選一 clarification iPhone E2E 已完成全語音實機驗收。`下一首歌` / `上一首歌` 仍不列入目前 Siri acceptance scope。

## Resolved Bug: `下一首` 切到 0 秒後暫停 (2026-09-18)

- 使用者實機回報「下一首」後歌曲跳到 0 秒並暫停；Agent log 顯示請求與 Spotify endpoint 都回傳 success，但直接讀取 Spotify playback state 得到 `is_playing=false`、`progress_ms=0`。
- 根因是播放器在非 active 裝置轉移時固定使用 `play=false`，且 skip 後沒有恢復播放；因此「成功切歌」不等於「成功繼續播放」。
- 先加入會重現該狀態的 red regression tests，再修正為 Next／Previous 轉移時使用 `play=true`，並在 skip 後呼叫 trusted Start/Resume；Pause 保持不自動恢復。
- 先前針對有播放 context 的切歌恢復流程已由 regression tests 覆蓋；後續發現的無 context 單曲 edge case 已在下一節修正。完整 tests 為 91 passed；iPhone Shortcut 仍需重新實機確認。

## Resolved Bug: 無播放佇列時 `下一首` 重新開始目前歌曲 (2026-09-18)

- 後續實機測試顯示：這次沒有暫停，但「下一首」沒有進入下一首，而是目前歌曲從頭播放；直接點 iPhone Shortcut 的測試也觀察到相同現象。
- Agent log 顯示手機請求確實到達，`spotify_next` 回傳 success；因此不能只用 HTTP success 判斷 Spotify 真的完成了曲目切換。
- 測試後直接讀取 Spotify playback state 得到 `is_playing=true`，目前曲目為 `物語`，`repeat_state=off`，`context_uri` 為空；這符合指定單曲播放沒有可用下一首的情況。
- 舊版 `SpotifyPlayer` 在每次 Next / Previous 後都無條件呼叫 Start/Resume；若 Spotify 沒有前進到新曲目，這個 Resume 會把同一首歌曲從 0 秒重新開始。
- 先加入會重現「同一首被重播」的 red regression test，再修正為 Next 在 skip 前後讀取曲目 identity；只有曲目真的改變且新曲目未播放時才 Resume。
- 完整 tests 已通過：91 passed；compileall、pip check 與 diff check 也通過。
- 修正部署到 Windows Agent 後，真實單曲播放（`context_uri` 為空、沒有下一首）測試回傳 `SPOTIFY_NO_NEXT_TRACK`；播放中的晴天由 1041 ms 前進到 1861 ms，前後 track ID 相同，沒有跳回 0 秒或暫停。
- 使用者完成最新實機測試並確認修正成功：沒有播放佇列時執行 `下一首` 不再重播目前歌曲，也不會造成暫停。
- queued / context 有下一首且曲目真的改變的路徑目前由 unit tests 覆蓋，尚未以使用者的 Spotify 播放佇列做額外實機驗收。

## Current Local Acceptance Gate

目前已安裝 Agent 路徑：

```text
D:\ai\windows-siri-agent
```

目前設定與 OAuth 已完成；若要在另一台 Windows 重建環境，仍需依下列步驟設定：

1. 在 Spotify Developer Dashboard 將 Redirect URI 設為：

```text
http://127.0.0.1:8000/spotify/callback
```

2. 只使用 Client ID，不需要把 Client Secret 提供給 Agent；在 `.env` 設定 `SPOTIFY_CLIENT_ID`。
3. 啟動：

```text
D:\ai\windows-siri-agent\scripts\start.bat
```

4. 若尚未授權，呼叫本機 Spotify OAuth start endpoint，完成瀏覽器授權。
5. 驗證 `/spotify/status`。
6. source 與 Windows Agent 已完成新的消歧規則：Live 排除、繁簡 normalization、最多 3 個 trusted candidates、短效 token。
7. 已跑 unit/security tests 並部署 Windows Agent；clarification token 流程已接到 iPhone Shortcut。
8. iPhone Siri Shortcut 端到端播放與三選一反問流程已完成全語音實機驗收。
9. Windows exact volume source/unit 與受控 Windows pycaw runtime gate 已完成；Siri 語音與實體喇叭聽感仍不列為已驗收，且不需要為此擴張 Local AI。
10. 後續 Spotify 工作重點：先做候選個人化排序（saved/liked → top tracks/artists → recently played → search relevance → final tie-breaker），再加入 shuffle/repeat/seek/Spotify volume/like/unlike current track；同時評估 `market=TW` 的 availability 行為，不把它誤當熱門度排序；不得降低 ambiguity safety。

## Important: What Is NOT Yet Proven

- 「死亡是生命的終點」fallback 修正已完成 source + regression test，但尚未部署 Windows Agent 或做真實 Spotify/Siri 回歸。

- 長歌名修正已完成 source 與 regression test 寫入，但尚未跑完整測試、部署 Windows Agent 或做 Siri 實機回歸。

除非有新的實機測試結果，**不要把以下項目寫成已完成**：

- Local AI 已接入正式 Agent 或已通過模型可行性驗收。
- LM Studio 已完成 production loopback-only 安全配置。
- 原規劃的 Qwen3 0.6B 與 plain Qwen2.5 1.5B Instruct exact model 尚未測試；本輪測的是實際 indexed 的 `qwen3.5-0.8b` 與 `qwen2.5-coder-1.5b-instruct` replacement IDs，另有 `qwen3-4b`。
- Spotify 模糊歌曲候選排序的 saved source slice 已完成並取得 `user-library-read`；但 `saved=true` 真實排序改善尚未驗收，Top/Recent 與更完整的 market/relevance 品質仍是後續工作，偏冷門同名歌曲仍可能排進前三候選。
- clarification store 的 bounded attempts 與 concurrent atomic selection 已完成 source/unit 驗證；尚未因這個內部安全修正重新做 Windows Agent 部署後的 Siri 實機回歸。
- Windows exact `set_volume` 的 source/schema/unit/API wiring 與受控 Windows pycaw setter 已驗證；尚未做 Siri 端到端音量口令或獨立實體喇叭聽感驗收。相對音量按鍵 fallback 仍是既有已測行為。

server 端第二輪選擇播放已由 iPhone Shortcut 實機觸發並成功完成真實 Spotify 播放；全語音 clarification 流程也已驗收通過。

## Source / Document Priority

開始工作前閱讀：

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/SECURITY.md`
4. 與任務相關的規格：
   - Spotify → `docs/SPOTIFY.md`
   - API → `docs/API.md`
   - Windows → `docs/WINDOWS.md`
   - Siri → `docs/SIRI_SHORTCUT.md`
5. `docs/TESTING.md`

`docs/SOURCE_SPEC.md` 是原始歷史規格，保持唯讀。

## Security Invariants To Preserve

不要為了讓 Spotify 或 Siri 比較好用而破壞以下界線：

```text
Siri Text
→ Parser
→ Validated Action
→ Trusted service / Catalog object
→ Adapter
```

Spotify 的歌名 / 歌手 / 專輯版本提示是搜尋資料，只能進 Spotify Search API；不得變成：

- shell command
- CMD / PowerShell
- executable path
- command-line argument
- process ID
- arbitrary URL

Windows Agent 的 LAN API 仍不得公開到 Internet。

## Suggested New-Chat Prompt

開新對話時可以直接貼：

> 請先讀 `AGENTS.md`、`PROJECT_STATUS.md`、`docs/SECURITY.md`，再依目前任務讀相關文件。不要重做已完成的架構決策。先確認 PROJECT_STATUS 的 Current Phase 與 Not Yet Proven，再從下一個未完成驗收項目繼續。

## Updating This File

這不是選用紀錄。**任何會改變真實專案狀態的工作，在結束前 MUST 更新這份檔案。**

必須更新的情況包括：

- 完成一個里程碑。
- 真實驗收測試成功或失敗。
- 實作狀態有實質變化。
- 發現、改變或解除 blocker。
- Current Phase 改變。
- 下一個必要動作改變。

更新時必須遵守：

- 不要因為「程式碼已寫」、「文件已寫」或「mock tests 通過」就把功能標成真實完成。
- Windows / Spotify / Siri 的實機驗收要與 code/spec/mock-test 狀態分開記錄。
- 沒有跑過的實機測試，必須繼續留在 Not Yet Proven 或等價區段。
- 舊的 next step 被取代時，要刪除或更新，不要一直累積過期資訊。
- 不得寫入 API Key、OAuth token、密碼或其他 secret。
- 純解釋、純討論、沒有改變專案狀態的工作，不需要修改本檔。

真正里程碑範例：

- Spotify OAuth 真實授權成功。
- Spotify status 驗證成功。
- 指定歌曲真實播放成功。
- Siri Shortcut 端到端驗收成功。

不要把「已寫規格」、「已寫 mock test」與「真實 Windows / Spotify 驗收成功」混為一談。
