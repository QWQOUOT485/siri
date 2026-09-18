# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Spotify 真實播放驗收（歌曲消歧實作與 Windows + Spotify 驗收已完成，Shortcut E2E 待進行）**

規格層與 Spotify-only 實作已完成；目前安裝在 Windows 的 Agent 已完成 OAuth 狀態、Connect 裝置、指定歌曲播放、基本播放控制、token refresh 與本次歌曲消歧驗收。Siri Shortcut 實機端到端流程仍待重新驗證。

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
- 已支援自然語音可使用的 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`、`播放晴天現場版`、`播放晴天原版`；版本意圖使用封閉的 `live`／`studio`／`original` 值，只進 Spotify 搜尋與排序。
- `SpotifyCatalog` 已對所有歌曲使用通用版本分類與安全排序：未指定 Live 時優先 studio/original，明確 Live 時優先 Live；不同歌手的裸歌名仍維持 ambiguous，不以搜尋第一筆代替意圖。
- 消歧修正的 unit tests 已通過（71 passed，2 個既有 dependency deprecation warnings）；這不等同於 Siri 實機端到端驗收。
- Spotify Search 的 optional `isrc`／`duration_ms` 已解析到 `SpotifyTrackRef`；同 ISRC 只作為接近候選的同錄音證據，duration 不會單獨觸發自動播放。
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。
- 真實帳號 token refresh 已驗證；refresh 後仍可成功執行 Spotify 播放控制。
- `scripts/start.bat` 啟動失敗時會保留視窗並提示 port/Agent 問題，不再靜默關閉。

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
- 期望的語音形式包括 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`；若使用者沒有說明 Live，產品也需要明確決定是否優先選原版／正式專輯，只有明確說「現場版」時才選 Live。若仍有多個合理候選，應繼續要求補充，不得隨機播放。
- 實作、unit tests 與 Windows + Spotify 實機驗證已完成；下一步是用自然語音重新跑 iPhone Siri Shortcut E2E。完成前不得把 Shortcut 驗收標成成功。

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
6. 尚待真實測試：
   - 修正後重新驗證 iPhone Siri Shortcut 端到端播放
7. Siri Shortcut 成功後，才算完成 V1 的完整播放驗收。

## Important: What Is NOT Yet Proven

除非有新的實機測試結果，**不要把以下項目寫成已完成**：

- Siri Shortcut 已完成端到端播放驗收；目前尚未重新驗證修正後的裸歌名流程。
- Siri 以自然語音表達專輯／版本提示時，Parser 能穩定抽取並完成選曲。

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
