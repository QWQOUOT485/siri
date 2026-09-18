# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Spotify 真實播放驗收（Windows Agent 控制已通過，token refresh 與 Shortcut 待驗收）**

規格層與 Spotify-only 實作已完成；目前安裝在 Windows 的 Agent 已完成 OAuth 狀態、Connect 裝置、指定歌曲播放與基本播放控制驗收。下一個關卡是驗證 token refresh 與 Siri Shortcut 端到端流程。

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
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。

## Real-World Acceptance (2026-09-18)

以下結果來自目前安裝的 `D:\ai\windows-siri-agent`，不是 mock test：

- `/spotify/status` 回報已授權，scope 為目前播放控制所需的兩項 scope。
- Spotify Connect 裝置已被 Agent 找到。
- `播放周杰倫的晴天 (葉惠美)` 實際回傳成功，播放曲目為 `晴天`，專輯為 `葉惠美`。
- `暫停` 與 `下一首` 實際回傳成功。
- 未指定專輯的 `播放晴天` 實際回傳成功並選到 `晴天` / `葉惠美`；測試最後再次暫停。
- 測試完成後 Agent 已停止，8000 port 已釋放。
- API key 未出現在測試 log 中。

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
   - token refresh
   - iPhone Siri Shortcut 端到端播放
7. 以上成功後，才算完成 V1 的完整播放驗收。

## Important: What Is NOT Yet Proven

除非有新的實機測試結果，**不要把以下項目寫成已完成**：

- Spotify token refresh 已在真實帳號驗證。
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
