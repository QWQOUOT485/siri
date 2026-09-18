# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Spotify 消歧產品規則第二輪修正（Live 排除、繁簡正規化、最多三選一 Siri 反問）**

先前的 studio/Live 排序實作與 Windows + Spotify 驗收已完成，但產品規則已於 2026-09-18 再次調整：一般指定歌曲不再支援 Live / 演唱會版本；真正無法判斷時，Siri 應最多列 3 首 trusted candidates 反問使用者。這些新規則尚未完成實作與實機驗收，因此現在不能直接進行最終 Shortcut E2E。

## Completed / Decided

- V1 使用 Rule-based Parser，不使用 LLM。
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
  - 「暫停」
  - 「下一首」
  - 「上一首」
- Spotify token 必須只保存在 Windows 本機，不進 Siri Shortcut、不進 Git、不進 API response/log。
- Spotify OAuth 採 Authorization Code with PKCE。
- Spotify 整合規格見 `docs/SPOTIFY.md`。
- `播放周杰倫的晴天 (葉惠美)` 已支援以專輯/版本提示縮小同名歌曲結果；提示只進 Spotify Search API，不進 shell、path 或 arbitrary URL。
- 目前程式碼已支援自然語音 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`、`播放晴天現場版`、`播放晴天原版`；但「明確 Live 時播放 Live」這部分已被新的產品決策取代，待修改。
- 目前 `SpotifyCatalog` 已有通用版本分類、ISRC / duration 與 confidence-based matching；新的產品決策要求 Live / Concert / Tour / 演唱會 / 現場候選直接排除，不再只是降權或明確 Live 時反向加權。
- 消歧修正的 unit tests 已通過（71 passed，2 個既有 dependency deprecation warnings）；這不等同於 Siri 實機端到端驗收。
- Spotify Search 的 optional `isrc`／`duration_ms` 已解析到 `SpotifyTrackRef`；同 ISRC 只作為接近候選的同錄音證據，duration 不會單獨觸發自動播放。
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。
- 真實帳號 token refresh 已驗證；refresh 後仍可成功執行 Spotify 播放控制。
- `scripts/start.bat` 啟動失敗時會保留視窗並提示 port/Agent 問題，不再靜默關閉。

## New Product Decision / Pending Implementation (2026-09-18)

以下是最新決策，**尚未全部實作完成**：

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
- `暫停` 與 `下一首` 實際回傳成功。
- 部署消歧修正後，直接對 Windows Agent 的自然語句 `播放周杰倫的晴天，專輯葉惠美` 實際播放 `晴天` / `葉惠美`。
- 部署消歧修正後，直接對 Windows Agent 的 `播放周杰倫的晴天原版` 實際播放 `晴天` / `葉惠美`，證明原版意圖不會把搜尋帶到無關的 `Original Soundtrack` 結果。
- 先前直接對 Windows Agent 的 `播放周杰倫的晴天` 實際播放 `晴天` / `葉惠美`，證明同歌手 studio 優先規則生效；這些都不是 Siri Shortcut 端到端結果。
- `播放晴天現場版` 實際回傳 `SPOTIFY_AMBIGUOUS_TRACK`，候選是多個 Live 發行；Agent 沒有選第一筆或誤播 studio，符合安全規則。
- 不帶歌手的 `播放葉惠美專輯的晴天` 若 Spotify 回傳不同歌手的同名／同專輯候選，實際回傳 `SPOTIFY_AMBIGUOUS_TRACK`，沒有猜測歌手；帶歌手的自然專輯句已成功。
- 本次最新實機測試最後再次 `暫停` 成功；修正後 Agent 目前仍在 `D:\ai\windows-siri-agent` 運行，供下一步 Shortcut 測試。
- 以過期 clock 觸發真實 Spotify refresh endpoint 後，`暫停` 仍實際回傳成功；token 未輸出到終端或 log。
- API key 未出現在測試 log 中。

## Known Blocker: Siri Shortcut 歌名／現場版本歧義 (2026-09-18)

- 實機重現時，Siri Shortcut 實際送到 Agent 的文字只有 `播放晴天`，沒有帶歌手或專輯提示。
- Spotify 搜尋回報 `SPOTIFY_AMBIGUOUS_TRACK`，候選包含原版 `晴天`／`葉惠美`、`2004無與倫比演唱會` 及其他 `Live` 版本；Agent 正確拒絕隨機播放。因此目前不是 OAuth、Connect 裝置或 Spotify 播放控制失敗，而是 Shortcut 語音輸入與選曲消歧尚未完成。
- 現有 `播放周杰倫的晴天 (葉惠美)` 可作為文字測試提示，但括號形式不是可靠的語音介面；Siri 可能把括號內容念成普通詞語或改變順序。
- 最新產品決策已不再支援 Live 播放：Live / Concert / Tour / 演唱會 / 現場候選應直接排除；明確要求 Live 時回覆只支援正式錄音版本。
- 仍需補上繁簡中文 matching normalization，避免 `周杰伦` / `周杰倫`、`叶惠美` / `葉惠美` 造成假歧義。
- 真正 ambiguous 時不再只回錯誤後結束；Shortcut 應最多列 3 首 trusted candidates 反問使用者，再以短效 clarification context 完成第二輪選擇。
- 先完成上述新規則的實作、unit/security tests 與 Windows + Spotify 驗證，再重新跑 iPhone Siri Shortcut E2E。完成前不得把 Shortcut 驗收標成成功。

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
6. 先完成新的消歧規則：
   - Live / 演唱會候選直接排除
   - 繁簡中文 normalization
   - ambiguous 最多 3 個 trusted candidates
   - Siri clarification 第二輪選擇
7. 跑 unit/security tests，再部署 Windows Agent 驗證。
8. 最後重新驗證 iPhone Siri Shortcut 端到端播放與三選一反問流程。
9. Siri Shortcut 成功後，才算完成 V1 的完整播放驗收。

## Important: What Is NOT Yet Proven

除非有新的實機測試結果，**不要把以下項目寫成已完成**：

- 新的 Live 排除規則已完成實作與實機驗收。
- 歌名／歌手／專輯的繁簡中文 normalization 已完成且不會誤合併真正不同候選。
- ambiguous response 已限制為最多 3 個 trusted candidates。
- Siri Shortcut 已能朗讀候選、反問使用者並完成第二輪 clarification。
- Siri Shortcut 已完成端到端播放驗收。

目前這些是「下一階段驗收項目」，不是既成事實。

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
