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
- 「下一首歌」→ Spotify 下一首歌曲
- 「上一首歌」→ Spotify 上一首歌曲
- 「開啟／關閉隨機播放」→ Spotify shuffle
- 「單曲循環／循環播放清單／關閉循環」→ Spotify repeat mode
- 「跳到一分三十秒」→ Spotify seek
- 「Spotify 音量 50」→ Spotify device volume
- 「喜歡這首」／「取消喜歡這首」→ 儲存／移除目前播放中的 Spotify track

## 前提

- 使用者需要 Spotify Premium 才能使用 Spotify Player API 的播放控制。
- Windows 電腦必須可以主動連線到 Spotify Accounts / Spotify Web API。
- Windows Agent 本身仍維持 LAN-only，不可從 Internet 直接連入。

## OAuth

使用 **Authorization Code with PKCE**。

- 不使用 Implicit Grant。
- Redirect URI 使用 loopback IP；本專案目前使用 `http://127.0.0.1:8000/spotify/callback`。
- 不使用 `localhost` alias。
- OAuth state 必須驗證。
- Access token / refresh token 僅保存在 Windows 本機。
- Token 不得傳給 iPhone、Siri Shortcut、遠端 API client。
- Token 不得寫入 Git、README、log 或錯誤回應。
- Access token 過期時由 Windows Agent 使用 refresh token 自動更新；refresh token 失效時才要求使用者重新授權。

### Scopes

遵循 least privilege，只要求目前功能需要的 scopes：
- `user-modify-playback-state`：播放、暫停、下一首歌、上一首歌、Transfer Playback。
- `user-read-playback-state`：讀取目前播放狀態與 Spotify Connect 裝置。
- `user-library-read`：讀取使用者 Spotify Library membership，判斷搜尋候選是否已保存／按讚。
- `user-library-modify`：只用於明確的「喜歡這首／取消喜歡這首」命令，管理使用者 Library。
- `user-top-read`：讀取使用者 Top Tracks / Top Artists，作為候選個人化排序訊號。
- `user-read-recently-played`：讀取 Recently Played，作為候選個人化排序訊號。

新增以上 scopes 後，既有 Spotify 授權需要重新走一次 OAuth consent，讓新 scopes 寫入 token。不得因為未取得新 scope 而讓既有播放控制全部失效；缺少個人化 scope 時退回既有 deterministic ranking。

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
6. 未提供歌手／專輯／版本時，若只有一個繁簡正規化後的精確歌名，優先選擇該 track；相似但非精確歌名不得把它降級成 ambiguity。
7. 歌名完全匹配 + 歌手高度匹配。
8. 繁簡正規化後的強匹配。
9. 其他候選。
10. Spotify 回傳的 `popularity` 只能作為最後的候選排列 tie-breaker；缺少或超出範圍的值忽略，不得改變 confidence gap、解除真正 ambiguity，或單獨決定播放。

若使用者明確要求 Live／現場版，服務會在搜尋前拒絕播放。未提供歌手且候選屬於不同歌手時，必須要求使用者補充歌手。若最高候選與第二名仍無足夠安全分差，不得播放。

若最高候選信心不足，或前兩個候選太接近，不得隨機播放。


### Local Semantic Recovery / ASR Alias Memory

Siri may mistranscribe stylized artist names before the Agent receives text, for example:

```text
spoken: SASIOVERLXRD
ASR: Sad overlxrd
```

Phase 1 adds local alias memory without giving memory new playback authority:

```text
normalize
→ exact confirmed alias lookup
→ normal Spotify resolver
→ fuzzy/track-first evidence only if unresolved
→ existing deterministic clarification
```

Only exact confirmed non-conflicted aliases may auto-canonicalize. RapidFuzz/track-first results remain candidate-only; they may help form clarification candidates but cannot silently rewrite the artist.

Automatic alias confirmation requires a trusted clarification selection and successful Spotify playback. AI/fuzzy/vector/popularity/personalization signals cannot independently confirm a mapping.

The implementation specification is in [semantic_recovery/README.md](semantic_recovery/README.md).

### Semantic Retry for Parser/Resolver Disagreement

歌曲語意解析不能把「rule parser 有輸出」等同於「語意一定正確」。例如：

```text
播放死亡是生命的終點
```

deterministic grammar 可能先切成：

```text
artist = 死亡是生命
track = 終點
```

這在語法上合法，但 Spotify resolver 若找不到可用候選，就是可能切錯 entity boundary 的證據。

長期流程：

```text
原始 Siri 文字
→ deterministic parser
→ deterministic Spotify resolver
   ├─ 高信心可用結果 → 照既有 deterministic 流程
   └─ no result / low confidence / 明確定義的 segmentation-risk
        → Local AI semantic retry（僅 spotify_play_track）
        → strict schema
        → deterministic grounding against 原始 Siri 文字
        → policy gate
        → 重新進入 deterministic Spotify resolver
```

規則：

- semantic retry 必須使用**原始 utterance**，不能只把第一次 parser 切錯後的 `track` / `artist` 餵給模型。
- AI 只可提出 `track` / `artist` / `album` 的語意抽取結果；第一版不處理 clarification ordinal、Spotify URI/track ID、candidate ranking 或 playback。
- grounded `track` 必須能由原始 utterance deterministic 支持；未 grounded 則整個 AI interpretation 失效。
- AI retry 後仍由既有 Live filtering、trusted `SpotifyTrackRef`、confidence/ambiguity、clarification store 決定是否可播放。
- 目前 resolver 的 safe confidence threshold 為 `0.70`：單一候選低於此分數才可產生 `SPOTIFY_LOW_CONFIDENCE_TRACK` retry signal；多候選或接近候選仍走 deterministic clarification，不交給 AI 猜測。
- `SPOTIFY_ENTITY_SEGMENTATION_RISK` 只在原始 utterance 確實符合 parser 的中文 `播放 X 的 Y` split、且原 split 與重建歌名搜尋都無結果時產生；普通 artist+track no-result 維持 `SPOTIFY_TRACK_NOT_FOUND`。
- 目前 Phase 0.5 未過 acceptance gate，因此 production execution 仍不啟用；先以 shadow mode 記錄「原 parser 結果 vs AI grounded 結果 vs resolver 結果」。
- 目前針對「的」的 reconstruction fallback 是 tactical deterministic repair；不要把它擴張成無限累積的特殊句型規則。

### Personalized Candidate Ranking

在 explicit artist / album / version、title identity、Live filtering 與既有安全 resolver 之後，候選可使用個人化訊號重新排序：

```text
saved / liked
→ Top Tracks / Top Artists
→ Recently Played
→ Spotify Search relevance
→ popularity-like signal only as final tie-breaker
```

這些訊號只能改善候選順序，不能單獨把真正的不同歌手同名歌曲變成「確定答案」。若仍然 genuine ambiguity，照舊回傳最多三個 trusted candidates 讓使用者選。

Top Items 使用 `GET /me/top/{type}`（`user-top-read`）；Recently Played 使用 `GET /me/player/recently-played`（`user-read-recently-played`）。這些結果只在 Windows Agent server-side 使用，不進 Shortcut、不進 AI prompt，也不接受 client 提供偏好權重。

### Saved / Liked Track Preference

在完成基本 title / artist / album / version / Live filtering 後，Agent 可對仍然有效的 trusted Spotify candidates 查詢目前使用者的 Library membership。

使用 Spotify read-only Library endpoint：

```text
GET /me/library/contains?uris=spotify:track:...
```

規則：

- 只檢查由 Spotify Search 建立的 server-owned candidate URI；client 不得提供 URI。
- 已保存／按讚的 track 可作為強個人化 ranking signal，優先排到 clarification 候選前面。
- saved status 不得覆蓋使用者明確指定的 artist / album / version。
- saved status 不得把真正不同歌手的合理同名歌曲直接自動消歧；仍應走 clarification，除非既有 deterministic resolver 本來就有足夠安全優勢。
- Library lookup timeout / 401 / 403 / 429 / unavailable 時，搜尋流程必須退回既有 deterministic ranking，不得讓播放功能整體失效。
- 此訊號只用於排序，不進 AI prompt，不進 Shortcut，不寫入一般 API response。
- 不使用 Library write scope，也不自動幫使用者按讚或取消按讚。

saved/liked 的第一個 deterministic source slice 已完成：Agent 只在既有 ambiguity 的最多三個 server-owned candidates 內查詢 membership，並只重排候選，不會改變自動播放或 ambiguity safety。Library lookup 失敗、缺少 scope 或回應格式異常時會退回原本 deterministic ranking。既有 token 需要重新授權取得 `user-library-read`；2026-09-20 read-only acceptance probe 仍未找到能證明 saved candidate 從原始 Search 順序被提升的 genuine ambiguity case，精確結果見 [`SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md`](SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md)。

Top Tracks / Top Artists 的 source slice 也已完成：Agent 只呼叫固定的 `GET /me/top/tracks` 與 `GET /me/top/artists`，並只對既有 server-owned ambiguity candidates 排序。Top signal 不會覆蓋 explicit artist / album / version、不會消除 ambiguity，也不會進入 AI、Shortcut 或一般 API response。top lookup malformed / timeout / 401 / 403 / 429 時會忽略該 signal；若 Library lookup 本身失敗，仍回到原 deterministic order。此 slice 需要 `user-top-read`，目前尚未完成 real-account acceptance。可用 `scripts/spotify_saved_ranking_acceptance.py` 執行 saved slice 的純讀取驗收；該 probe 不播放且不修改 Library。

Recently Played 的 source slice 也已完成：Agent 只呼叫固定的 `GET /me/player/recently-played`，將 server 回傳的 track ID / artist name 作為既有 ambiguity candidates 內的次級排序 evidence，順序位於 Top Tracks / Top Artists 之後、Search relevance 之前。它不建立新候選、不消除 genuine ambiguity、不覆蓋 explicit metadata，也不進 AI、Shortcut 或一般 API response。空歷史、malformed item、timeout、401、403、429、缺少 optional method 或其他 lookup failure 都會忽略該訊號並維持既有 deterministic ranking。此 slice 需要 `user-read-recently-played`；目前 token 未完成重新授權，因此 real-account acceptance 尚未完成。

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

Clarification context 使用 Windows Agent process 內的 bounded in-memory store：

- context 有短 TTL，Agent restart 後全部失效；
- 每次不清楚的第二輪回覆會增加失敗次數，但最多允許三次嘗試；
- 第三次仍不清楚時 context 立即失效，不再回傳 token；
- 成功選擇與失敗次數更新都在同一個 lock 內完成，因此同一 token 的並發請求最多只有一個成功選擇；
- 失敗次數與剩餘次數不會放入 Siri 回應，避免把內部防護細節變成 client 控制面。

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
├── duration_ms (optional metadata from Spotify)
└── popularity (optional metadata from Spotify; ordering tie-breaker only)
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

## Extended Playback Controls

以下功能列入 deterministic closed-action roadmap，不交給 Local AI：

- Shuffle：`PUT /me/player/shuffle`
- Repeat：`PUT /me/player/repeat`
- Seek：`PUT /me/player/seek`
- Spotify device volume：`PUT /me/player/volume`

這些功能沿用 `user-modify-playback-state` scope，且 Spotify Player API 只對 Premium 帳號可用。

安全規則：

- shuffle 只接受 boolean state；
- repeat 只接受封閉值 `off` / `track` / `context`；
- seek 只接受 parser 轉換後的非負整數毫秒；
- Spotify volume 只接受 0–100 整數，與 Windows master volume action 分開；
- 不接受 client 直接傳 Spotify endpoint、任意 query parameter 或任意 body。


### Shuffle / Repeat / Continue Semantics

Extended playback controls use closed deterministic actions:

```text
spotify_shuffle_on
spotify_shuffle_off

spotify_repeat_track
spotify_repeat_context
spotify_repeat_off

spotify_continue
```

Natural-language examples:

```text
隨機播放           → spotify_shuffle_on
關閉隨機播放       → spotify_shuffle_off
單曲循環           → spotify_repeat_track
循環播放清單       → spotify_repeat_context
關閉循環           → spotify_repeat_off
就一直播下去       → spotify_continue
正常播就好         → spotify_continue
```

`spotify_continue` has a precise meaning:

```text
repeat = off
→ resume playback
→ preserve current shuffle state
```

It does not invent a new queue or promise playback beyond the currently available Spotify context. Generic `繼續播放` remains the existing `spotify_resume`; the "normal/keep going" wording is what selects `spotify_continue`.

All of these controls remain deterministic-only and are not added to the initial Local AI allowlist.

### Spotify Device Volume vs Windows Master Volume

```text
音量 30%
→ Windows set_volume(30)

Spotify 音量 30%
→ spotify_set_volume(30)
```

Spotify device volume accepts only integers 0–100 and uses the fixed Player API endpoint. It never falls back to Windows master volume, and Windows exact-volume control never falls back to Spotify device volume.

See [PLAYBACK_CONTROLS.md](PLAYBACK_CONTROLS.md) for parser, action-schema, failure and acceptance requirements.

## Like / Unlike Current Track

第一版 Library write 只支援目前正在播放的 trusted Spotify track：

```text
喜歡這首
→ 讀取目前播放狀態
→ 取得 server-side trusted track URI
→ PUT /me/library

取消喜歡這首
→ 讀取目前播放狀態
→ 取得 server-side trusted track URI
→ DELETE /me/library
```

需要 `user-library-modify`。

不得讓 iPhone / Shortcut 提供 Spotify URI、track ID 或任意 Library item。若沒有目前歌曲、目前 item 不是可支援的 Spotify track、或 Spotify API 失敗，回傳明確錯誤且不猜。

Library read/write 使用目前 Spotify 推薦的通用 Library endpoints：

- `GET /me/library/contains`：檢查 saved status；
- `PUT /me/library`：儲存；
- `DELETE /me/library`：移除。

舊的 track-specific `/me/tracks/contains` / save/remove endpoints 已 deprecated，不作為新實作基線。

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
- popularity 只能改善同等 matching score 的候選排列，不能自動消除 genuine ambiguity；缺少或無效值必須安全忽略
- saved/liked candidate 可被提升排序，但不能覆蓋 explicit artist/album/version 或 genuine ambiguity
- Top Tracks / Top Artists 與 Recently Played 可作次級個人化排序訊號
- ranking precedence 必須維持 saved → top → recent → search relevance → final tie-breaker
- Library / Top / Recently Played lookup 失敗時必須安全 fallback 到既有 ranking
- shuffle on/off closed action
- repeat off/track/context closed action
- seek parser 將自然時間轉成 bounded milliseconds
- Spotify volume 僅接受 0–100
- like/unlike current track 只能操作 server-resolved current Spotify track
- client-provided Library URI / track ID 被拒絕
- Live 候選直接排除；明確 Live intent 不搜尋、不播放
- Traditional/Simplified identity normalization
- bare same-title tracks by different artists remain ambiguous
- same-ISRC release duplicates may collapse; duration alone must not auto-select
- ambiguous results 不自動播放
- ambiguous results 最多三個 trusted candidates，clarification token 短效、最多三次嘗試且只能一次成功選擇
- clarification failed-attempt bound 與 concurrent selection 必須由 unit tests 驗證
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
- production Local AI execution（目前仍 gated / disabled）
- AI 直接選 Spotify candidate、track ID、URI 或直接播放
- 自動產生 arbitrary Spotify API request
- 把 Spotify token 放進 Siri Shortcut

Local AI 若後續通過 shadow + benchmark gate，只能用於受限的 Spotify intent/entity extraction / semantic retry；最終仍必須收斂成既有 ValidatedAction 與本文件的 deterministic Spotify 安全資料流。
