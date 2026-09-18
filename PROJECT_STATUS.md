# Project Status

這份文件是給「新對話 / 新 coding agent」快速接手用的狀態摘要。

> 目的：不要靠長聊天紀錄維持專案上下文。真正的進度以 GitHub 內容、目前安裝的 Windows Agent、以及這份狀態檔為準。

## Current Phase

目前階段：**Spotify 消歧產品規則第二輪修正（Live 排除、繁簡正規化、最多三選一 Siri 反問）**

先前的 studio/Live 排序實作與 Windows + Spotify 驗收已完成。2026-09-18 新規則的 source implementation、unit/security tests 與 Windows Agent 直接驗證已完成；目前仍不能把 iPhone Siri Shortcut 的候選朗讀、token 保存與第二輪選擇標成完成。

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
  - 「暫停」/「暫停音樂」
  - 「下一首」
  - 「上一首」
- Spotify token 必須只保存在 Windows 本機，不進 Siri Shortcut、不進 Git、不進 API response/log。
- Spotify OAuth 採 Authorization Code with PKCE。
- Spotify 整合規格見 `docs/SPOTIFY.md`。
- `播放周杰倫的晴天 (葉惠美)` 已支援以專輯/版本提示縮小同名歌曲結果；提示只進 Spotify Search API，不進 shell、path 或 arbitrary URL。
- 目前程式碼已支援自然語音 `播放周杰倫的晴天，專輯葉惠美`、`播放葉惠美專輯的晴天`、`播放晴天現場版`、`播放晴天原版`；明確 Live 會安全拒絕，不會播放 Live。
- `SpotifyCatalog` 已有通用版本分類、繁簡正規化、ISRC / duration 與 confidence-based matching；Live / Concert / Tour / 演唱會 / 現場候選會直接排除。
- 消歧修正的完整 unit/security tests 已通過（82 passed，2 個既有 dependency deprecation warnings）；這不等同於 Siri 實機端到端驗收。
- Spotify Search 的 optional `isrc`／`duration_ms` 已解析到 `SpotifyTrackRef`；同 ISRC 只作為接近候選的同錄音證據，duration 不會單獨觸發自動播放。
- Spotify 控制 endpoint 的成功非 JSON 回應已視為成功，不會被誤報成回應格式錯誤。
- 真實帳號 token refresh 已驗證；refresh 後仍可成功執行 Spotify 播放控制。
- `scripts/start.bat` 啟動失敗時會保留視窗並提示 port/Agent 問題，不再靜默關閉。
- `暫停`、`暫停音樂`、`pause music` 與簡體 `暂停音乐` 都收斂到封閉的 `spotify_pause` action；不回退到通用系統媒體控制。

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
- `暫停` 與 `下一首` 實際回傳成功。
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
- 先加入回歸測試確認原行為失敗，再加入繁體、簡體與英文 `pause music` 的封閉 alias；目前完整 unit tests 為 82 passed，保留既有 2 個 dependency deprecation warnings。
- 部署到 `D:\ai\windows-siri-agent` 後，直接送出完整文字 `暫停音樂` 的真實 HTTP 回應為 `success=true`、`action=spotify_pause`，並成功找到 Windows Spotify 裝置。
- 直接 Agent 驗收後，使用者重新測試 iPhone Siri Shortcut，確認「暫停音樂」已能成功暫停 Spotify；這個基本控制路徑已通過，但不等同於新的歌曲消歧／三選一 clarification E2E。

## Known Blocker: Siri Shortcut clarification E2E (2026-09-18)

- 實機重現時，Siri Shortcut 實際送到 Agent 的文字只有 `播放晴天`，沒有帶歌手或專輯提示。
- 舊的實機重現中，Spotify 搜尋回報 `SPOTIFY_AMBIGUOUS_TRACK`，候選包含原版 `晴天`／`葉惠美`、`2004無與倫比演唱會` 及其他 `Live` 版本；Agent 當時正確拒絕隨機播放。因此問題不是 OAuth、Connect 裝置或 Spotify 播放控制失敗，而是 Shortcut 語音輸入與選曲消歧尚未完成。
- 現有 `播放周杰倫的晴天 (葉惠美)` 可作為文字測試提示，但括號形式不是可靠的語音介面；Siri 可能把括號內容念成普通詞語或改變順序。
- 最新產品決策已不再支援 Live 播放：Live / Concert / Tour / 演唱會 / 現場候選應直接排除；明確要求 Live 時回覆只支援正式錄音版本。
- 繁簡中文 matching normalization、Live 排除、最多三首 trusted candidates 與短效 clarification context 已完成 source/runtime 驗證。
- 目前仍未驗證 iPhone Shortcut 能朗讀候選、保存 token、把第二輪「第一首／第二首／第三首／歌手／專輯」與 token 一起送回，並完成真實播放。完成前不得把完整 Shortcut 驗收標成成功。
- 基本 Spotify Shortcut 控制路徑已有「播放原版」「下一首」「暫停音樂」成功紀錄；新的歌曲消歧／三選一 clarification E2E 仍待使用者實機重測。

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
