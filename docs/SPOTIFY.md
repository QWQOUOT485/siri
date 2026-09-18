# Spotify Integration

本文件定義 Windows Siri Agent V1 的 Spotify 整合規格。Spotify 是 V1 唯一支援的指定歌曲播放來源。

## 目標

支援以下 Siri 指令：
- 「播放」/「播放音樂」→ 恢復 Spotify
- 「播放晴天」→ 搜尋並播放歌曲
- 「播放周杰倫的晴天」→ 用歌曲名 + 歌手搜尋並播放
- 「播放周杰倫的晴天 (葉惠美)」→ 以專輯/版本提示縮小同名歌曲結果
- 「播放周杰倫的晴天，專輯葉惠美」→ 以自然語音提供專輯提示
- 「播放葉惠美專輯的晴天」→ 以專輯前置語法提供專輯提示
- 「播放晴天現場版」→ 明確回覆目前只支援正式錄音版本，不播放 Live
- 「播放晴天原版」→ 以原版意圖搜尋正式錄音版本
- 「暫停」/「暫停音樂」→ 暫停 Spotify
- 「下一首」→ Spotify 下一首
- 「上一首」→ Spotify 上一首

## 前提

- 使用者需要 Spotify Premium 才能使用 Spotify Player API 的播放控制。
- Windows 電腦必須可以主動連線到 Spotify Accounts / Spotify Web API。
- Windows Agent 本身仍維持 LAN-only，不可從 Internet 直接連入。

## OAuth

使用 **Authorization Code with PKCE**。

- 不使用 Implicit Grant。
- Redirect URI 使用 loopback IP，例如 `http://127.0.0.1:8787/callback`。
- 不使用 `localhost` alias。
- OAuth state 必須驗證。
- Access token / refresh token 僅保存在 Windows 本機。
- Token 不得傳給 iPhone、Siri Shortcut、遠端 API client。
- Token 不得寫入 Git、README、log 或錯誤回應。
- Access token 過期時由 Windows Agent 使用 refresh token 自動更新；refresh token 失效時才要求使用者重新授權。

### Scopes

遵循 least privilege，只要求目前功能需要的 scopes：
- `user-modify-playback-state`：播放、暫停、下一首、上一首、Transfer Playback。
- `user-read-playback-state`：讀取目前播放狀態與 Spotify Connect 裝置。

若未來新增功能需要更多 scopes，必須先更新本規格與 SECURITY.md，不可預先要求不必要權限。

## Spotify 模組責任

建議新增：

```text
app/
├── infrastructure/
│   └── spotify_auth.py
├── services/
│   └── spotify_service.py
└── adapters/
    └── spotify/
        ├── client.py
        ├── catalog.py
        └── player.py
```

責任：
- `spotify_auth.py`：PKCE、token storage、refresh、OAuth callback。
- `catalog.py`：Spotify Search API、搜尋結果正規化與排序。
- `player.py`：devices、transfer playback、play/pause/next/previous。
- `spotify_service.py`：協調 parser 的 ValidatedAction 與 Spotify adapters。

Domain 不應直接依賴 Spotify HTTP SDK。

## 指定歌曲播放資料流

```text
Siri: 播放周杰倫的晴天
↓
Parser
↓
ValidatedAction(
  action = spotify_play_track,
  track = 晴天,
  artist = 周杰倫,
  album = 葉惠美  # optional album/version hint
  version_hint = null  # live / studio / original, optional closed hint
)
↓
SpotifyService
↓
Spotify Search API
↓
可信 SpotifyTrackRef
↓
Spotify Connect device resolution
↓
Start/Resume Playback
```

### Search

使用 Spotify `GET /search` 搜尋 track。

搜尋 query 可以由歌名、歌手與可選的專輯/版本提示組成，但只能作為 Spotify 搜尋資料。

排序與版本規則：
1. 歌名完全匹配 + 歌手完全匹配。
2. 歌名完全匹配 + 歌手完全匹配 + 專輯完全匹配（若提供專輯提示）。
3. 使用者明確的 `live`／`studio`／`original` 版本意圖。
4. Live／Concert／Tour／演唱會／現場候選直接排除；它們不會因 Spotify 搜尋排序而被播放。
5. 未指定版本時，正式 studio/original 候選優先；次要發行仍需有明顯安全優勢。
6. 歌名完全匹配 + 歌手高度匹配。
7. 繁簡正規化後的強匹配。
8. 其他候選。

若使用者明確要求 Live／現場版，服務會在搜尋前拒絕播放。未提供歌手且候選屬於不同歌手時，必須要求使用者補充歌手。若最高候選與第二名仍無足夠安全分差，不得播放。

若最高候選信心不足，或前兩個候選太接近，不得隨機播放。

真正 ambiguous 時，回傳最多三個 server-owned、適合 Siri 朗讀的候選，並附帶短效 `clarification_token`：

> 找到多個可能的 Stay，請再說歌手名稱。

使用者下一次可用同一個 `POST /command` 傳回覆文字與 token，例如：

```json
{
  "text": "第二首",
  "clarification_token": "opaque-short-lived-token"
}
```

Agent 只會在原候選集合中解析序號、歌手或專輯；client 不得傳入 Spotify URI 或 track ID。選擇不清楚時會再次列出原候選，不會猜測。

## Trusted SpotifyTrackRef

Spotify Search API 回傳結果經 validation 後，轉成 server-side trusted object，例如：

```text
SpotifyTrackRef
├── track_id
├── track_uri
├── track_name
├── artist_names
├── album_name
├── isrc (optional metadata from Spotify)
└── duration_ms (optional metadata from Spotify)
```

只有由 Spotify API 回傳並通過 validation 的 `SpotifyTrackRef` 才能進入 player adapter。

遠端 client 不可直接傳 `track_uri` 或 Spotify API URL 要求執行。

## 播放裝置

使用 Spotify Connect device。

建議本機設定：

```text
spotify_device_name = 使用者 Windows 上 Spotify 顯示的裝置名稱
```

播放流程：
1. 讀取 Spotify 可用裝置。
2. 優先找設定的 Windows 裝置名稱。
3. 若沒有設定，可使用目前 active device。
4. 若找到目標但不是 active device，可 Transfer Playback。
5. 若沒有任何適合裝置，可透過既有 Trusted AppEntry 安全開啟 Spotify Desktop，等待後重新取得 devices。
6. 仍找不到時回傳清楚錯誤，不使用 shell fallback。

不要假設 Spotify device ID 永久不變；設定與比對應以使用者可辨識的 device name 為主，runtime 再取得當前 device ID。

## Playback

指定歌曲使用 Spotify Player API 的 Start/Resume Playback，播放目標必須是 server-side trusted `SpotifyTrackRef.track_uri`。

基本控制：
- Resume: Start/Resume Playback
- Pause: Pause Playback
- Next: Skip To Next，完成切換後保持／恢復播放
- Previous: Skip To Previous，完成切換後保持／恢復播放

若指定的 Windows Connect 裝置目前不是 active，Next／Previous 轉移播放權時使用
`play=true`；若目前已暫停，切歌後再以固定的 Start/Resume 操作恢復播放。Pause
不會走這個恢復流程。Next 會在 skip 前後讀取目前曲目 identity；只有確認曲目真的改變
後才會 Resume。若目前是沒有播放佇列的單曲、Spotify 沒有可用下一首，會回傳
`SPOTIFY_NO_NEXT_TRACK` 並保留目前歌曲，不會用 Resume 把它從頭重播。Previous 保留
Spotify 在目前曲目播放超過一段時間時重播目前曲目的正常語義。

如果 Spotify 回傳 401：嘗試 refresh token；若仍失敗，要求重新授權。

如果 Spotify 回傳 403：回傳權限 / Premium / account 狀態相關的友善錯誤，不繞過 Spotify 限制。

如果 Spotify 回傳 429：遵循 `Retry-After`，不可 busy-loop 重試。

## 安全邊界

使用者的 `track` / `artist` / `album` 是不可信輸入，但允許送進 Spotify Search API。

它們永遠不能進入：
- shell
- CMD
- PowerShell
- subprocess executable target
- executable path
- command-line argument
- filesystem path
- process ID
- arbitrary URL

Spotify integration 不得新增 remote shell 或 generic HTTP proxy。

Agent 只允許呼叫程式內固定的 Spotify API endpoints。

## iPhone / Siri Shortcut

iPhone 仍只呼叫 Windows Agent：

```text
POST http://WINDOWS-IP:8000/command
X-API-Key: ...

{
  "text": "播放周杰倫的晴天"
}
```

iPhone 不直接連 Spotify API，也不保存 Spotify OAuth token。

## 測試要求

Unit tests 必須 mock Spotify API，不真的播放音樂。

至少測試：
- `播放` → `spotify_resume`
- `播放晴天` → `spotify_play_track(track=晴天)`
- `播放周杰倫的晴天` → track + artist
- `播放周杰倫的晴天 (葉惠美)` → track + artist + album/version hint
- `播放周杰倫的晴天，專輯葉惠美` → natural album hint
- `播放葉惠美專輯的晴天` → leading album hint
- `播放晴天現場版` / `播放晴天原版` → closed version intent
- 英文 `Play Blinding Lights by The Weeknd`
- exact track + artist ranking
- Live 候選直接排除；明確 Live intent 不搜尋、不播放
- Traditional/Simplified identity normalization
- bare same-title tracks by different artists remain ambiguous
- same-ISRC release duplicates may collapse; duration alone must not auto-select
- ambiguous results 不自動播放
- ambiguous results 最多三個 trusted candidates，clarification token 短效且只能一次選擇
- no results
- token refresh
- 401 / 403 / 429 handling
- device not found
- transfer playback mocked flow
- track/artist/album injection strings 只能當搜尋文字
- client-provided Spotify URI 被拒絕
- tokens 不出現在 logs/API responses

## V1 不做

- Apple Music
- YouTube Music
- 多 provider 選擇
- LLM 解析歌曲名稱
- 自動產生 arbitrary Spotify API request
- 把 Spotify token 放進 Siri Shortcut

未來若加入本地 AI，只能用於 intent/entity extraction；最終仍必須收斂成既有 ValidatedAction 與本文件的 Spotify 安全資料流。
