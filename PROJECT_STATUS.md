# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Local AI Phase 0.5 可行性 PoC 準備 + Siri clarification E2E 待驗收**

先前的 Spotify studio/Live、繁簡正規化、最多三候選與 server-side clarification source/runtime 驗證已完成。2026-09-18 產品決策新增：V1 不再禁止本地 LLM，可在安全邊界下使用 LM Studio 作 rule-first 的 fallback 語意解析器。正式接入前先做獨立 Phase 0.5 模型可行性 PoC；iPhone Siri Shortcut 的候選朗讀、token 保存與第二輪選擇仍未完成 E2E。

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
- `播放周杰倫的晴天 (葉惠美)` 已支援以專輯/版本提示縮小同名歌曲結果；提示只進 Spotify Search API，不進 shell、path 或 arbitrary URL。
- 目前程式碼已支援自然語音 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`、`播放晴天現場版`、`播放晴天原版`；明確 Live 會安全拒絕，不會播放 Live。
- `SpotifyCatalog` 已有通用版本分類、繁簡正規化、ISRC / duration 與 confidence-based matching；Live / Concert / Tour / 演唱會 / 現場候選會直接排除。
- 消歧修正與播放控制回歸測試的完整 unit/security tests 已通過（91 passed，2 個既有 dependency deprecation warnings）；這不等同於 Siri 實機端到端驗收。
- Spotify Search 的 optional `isrc`／`duration_ms` 已解析到 `SpotifyTrackRef`；同 ISRC 只作為接近候選的同錄音證據，duration 不會單獨觸發自動播放。
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。
- 真實帳號 token refresh 已驗證；refresh 後仍可成功執行 Spotify 播放控制。
- `scripts/start.bat` 啟動失敗時會保留視窗並提示 port/Agent 問題，不再靜默關閉。
- `暫停`、`暫停音樂`、`pause music` 與簡體 `暂停音乐` 都收斂到封閉的 `spotify_pause` action；不回退到通用系統媒體控制。

## Local AI Phase 0.5 Preparation (2026-09-18)

- 使用者已在 LM Studio 下載三個 planned benchmark candidates：
  - Qwen3 0.6B
  - Qwen2.5 1.5B Instruct
  - Qwen3 4B
- 以上模型目前只確認「已下載」，**尚未完成 benchmark、尚未選定 production model**。
- Phase 0.5 實測 runbook 已建立：`docs/LOCAL_AI_MODEL_POC_RUNBOOK.md`。
- Runbook 要求三個模型使用同一份固定測資，分別測 prompt-only JSON 與 structured-output（若支援），並量測 intent/semantic accuracy、hallucination、post-grounding false accept、false execution、clarification accuracy、P50/P95 latency 與資源使用。
- 實測預計由 Codex 在真實 Windows + LM Studio 環境依 runbook 執行；尚未執行前，不得把任何模型標成通過。
- 目前 LM Studio 開發 endpoint 由使用者回報為 `http://192.168.0.199:1234`；production same-host target 仍為 loopback `127.0.0.1:1234`。

## Local AI Phase 0.5 PoC Execution Attempt (2026-09-19)

- 已新增隔離的 `scripts/ai_model_poc.py`、`tests/fixtures/ai_intent_cases.json`（103 筆固定測資）與 `tests/unit/test_ai_model_poc.py`。
- PoC 目前只呼叫 LM Studio OpenAI-compatible API，使用 strict Pydantic schema、OpenCC canonical grounding、hostile-input fail-closed 檢查與本地 CSV/JSONL/SUMMARY 輸出；未接入 `/command`、`app.main`、Spotify 播放、Windows adapters、shutdown、firewall 或 `start.bat`。
- 新增 PoC unit test 6 passed；完整 `tests/unit` 為 92 passed，保留 2 個既有 dependency deprecation warnings。
- 實機 preflight 的最後讀回為：`http://192.168.0.199:1234/v1/models` 僅回傳 `text-embedding-nomic-embed-text-v1.5`；`lms ps` 顯示沒有載入模型；`lms load qwen3.5-0.8b --identifier=qwen3.5-0.8b -y` 回報找不到目前 indexed model key。
- 三個候選 GGUF 實體仍存在於 `D:\ai` 下，且固定前 4 bytes 均為 `GGUF`：Qwen3.5 0.8B（529,297,312 bytes）、Qwen3 4B（2,497,280,800 bytes）、Qwen2.5 Coder 1.5B Instruct（986,048,576 bytes）。目前 LM Studio library / `lms ls` / `/v1/models` 沒有列出它們；因此現況較符合「外部下載檔尚未被目前 LM Studio library 登記/匯入」，不是檔案已刪除。
- 因此三個候選 LLM 的 benchmark 尚未執行，沒有任何模型通過、沒有 production model recommendation，也沒有 Local AI production integration claim。
- Blocker / 下一步：使用 LM Studio 的 import/rescan 流程把現有 GGUF 納入目前 models library（優先採保留原檔的 copy/link 方式，尚未執行），再讀回 exact `/v1/models` ID，依 runbook 用同一份 103-case fixture 執行 prompt/schema 兩種模式。不得把 embedding 模型當候選或重新下載相同檔案。

## Local AI Product Decision (2026-09-18)

- 舊規則「V1 不得加入 LLM integration」已取消。
- V1 允許 **Local LLM**，目前指定 runtime 方向為 LM Studio；不使用雲端 LLM fallback。
- AI 採 rule-first / fallback-only；第一版 AI scope 只處理 Spotify free-form semantic parsing 與 clarification selection。
- AI 輸出必須通過 strict closed schema 與 deterministic slot grounding；`track` 未 grounded 時不得建立 `spotify_play_track`。
- shutdown / shutdown confirmation / force-close / firewall / system-administration 永久不交給 AI 解析。
- LM Studio 若與 Agent 同機，production acceptance 目標為 loopback (`127.0.0.1:1234`)；目前使用者回報的 `192.168.0.199:1234` 只視為開發/測試 endpoint，尚未視為正式安全配置。
- 完整架構提案見 `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md`。
- 下一步是獨立 **Phase 0.5 model feasibility PoC**；此決策不代表 Local AI 已接入正式 Agent。

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
- 上述 controlled run 已正常停止，port 8000 已釋放；目前沒有宣稱 Agent 正在運行。
- 以過期 clock 觸發真實 Spotify refresh endpoint 後，`暫停` 仍實際回傳成功；token 未輸出到終端或 log。
- API key 未出現在測試 log 中。

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

## Siri Shortcut Stable Dictation Flow Documentation (2026-09-19)

- `docs/SIRI_SHORTCUT.md` 已改成穩定版流程：Shortcut 自己先 Speak「請說電腦指令」→ Dictate Text → POST `/command` → Speak response。
- clarification 必須在同一次 Shortcut 執行內完成第二次 Speak + Dictate Text + POST token；避免 Shortcut 已結束後，Siri 把「下一首／第二首」當成 iPhone 原生指令。
- 文件建議 Dictate Text 語言設為「中文（台灣）」並使用較獨特的 Shortcut 名稱（例如「Windows 管家」）降低 Siri 原生語意衝突。
- 已加入排查分流：Agent 沒收到 POST → iPhone/Shortcut 問題；收到 `text=下一週` → Siri ASR 問題；收到 `text=下一首` 但未執行 → Agent parser/service 問題。
- 這只是文件與操作流程修正，**尚未完成 iPhone 實機 clarification E2E 驗收**。

## Known Blocker: Siri Shortcut clarification E2E (2026-09-18)

- 實機重現時，Siri Shortcut 實際送到 Agent 的文字只有 `播放晴天`，沒有帶歌手或專輯提示。
- 舊的實機重現中，Spotify 搜尋回報 `SPOTIFY_AMBIGUOUS_TRACK`，候選包含原版 `晴天`／`葉惠美`、`2004無與倫比演唱會` 及其他 `Live` 版本；Agent 當時正確拒絕隨機播放。因此問題不是 OAuth、Connect 裝置或 Spotify 播放控制失敗，而是 Shortcut 語音輸入與選曲消歧尚未完成。
- 現有 `播放周杰倫的晴天 (葉惠美)` 可作為文字測試提示，但括號形式不是可靠的語音介面；Siri 可能把括號內容念成普通詞語或改變順序。
- 最新產品決策已不再支援 Live 播放：Live / Concert / Tour / 演唱會 / 現場候選應直接排除；明確要求 Live 時回覆只支援正式錄音版本。
- 繁簡中文 matching normalization、Live 排除、最多三首 trusted candidates 與短效 clarification context 已完成 source/runtime 驗證。
- 目前仍未驗證 iPhone Shortcut 能朗讀候選、保存 token、把第二輪「第一首／第二首／第三首／歌手／專輯」與 token 一起送回，並完成真實播放。完成前不得把完整 Shortcut 驗收標成成功。
- 基本 Spotify Shortcut 控制路徑已有「播放原版」「暫停音樂」成功紀錄；`下一首歌` / `上一首歌` 的 Siri 端到端流程尚未重新驗證，歌曲消歧／三選一 clarification E2E 仍待使用者實機重測。

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
7. 已跑 unit/security tests 並部署 Windows Agent；仍需把 clarification token 流程接到 iPhone Shortcut。
8. 最後重新驗證 iPhone Siri Shortcut 端到端播放與三選一反問流程。
9. Siri Shortcut 成功後，才算完成 V1 的完整播放驗收。

## Important: What Is NOT Yet Proven

除非有新的實機測試結果，**不要把以下項目寫成已完成**：

- Local AI 已接入正式 Agent 或已通過模型可行性驗收。
- LM Studio 已完成 production loopback-only 安全配置。
- Phase 0.5 的 Qwen3 0.6B / Qwen2.5 1.5B Instruct / Qwen3 4B 模型比較已完成。
- Siri Shortcut 已能朗讀候選、反問使用者並完成第二輪 clarification。
- Siri Shortcut 已完成包含歌曲消歧、候選反問與第二輪選擇的完整端到端播放驗收。

另外，server 端實際完成第二輪選擇播放的 Windows + Spotify E2E 尚未在本輪執行；目前由 unit tests 與 API/token 邊界測試覆蓋。以上仍是「下一階段驗收項目」，不是既成事實。

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
