# Bug Proposal: Spotify / Siri 同名歌曲與原版・Live 版本消歧

> **Temporary document — 必須刪除**
>
> 這份文件是暫時性的 bug / implementation proposal。
> 當本問題完成實作、單元測試通過，並且完成真實 Siri Shortcut 端到端驗收後，**必須刪除本檔案**，避免已解決問題長期殘留在文件中。
>
> 刪除條件請見本文最後的「完成與刪除條件」。

## 問題摘要

目前 Spotify 指定歌曲播放最大的 blocker 是：

- Siri Shortcut 可能只傳入裸歌名，例如 `播放晴天`
- Spotify Search 可能回傳多個同名版本
- 常見情況包含：
  - 正式錄音室 / 原始專輯版本
  - Live / 演唱會版本
  - Remaster / Reissue
  - Compilation 收錄版本
  - Acoustic / Alternate version
- 現行 `SpotifyCatalog.find_track()` 在未提供歌手時，只要有多個 exact track-name matches，就直接視為 ambiguous
- 因此即使存在一個很明顯的正式專輯版本，Agent 仍會回傳 `SPOTIFY_AMBIGUOUS_TRACK`

目前這個行為符合「不要亂播」的安全原則，但 Siri 使用體驗過度保守。

## 已知實機案例

目前已知 Siri Shortcut 實際可能只送出：

```text
播放晴天
```

Spotify 搜尋可能同時出現：

```text
晴天 — 周杰倫 — 葉惠美
晴天 — 周杰倫 — 2004無與倫比演唱會
晴天 — 周杰倫 — 其他 Live / 演唱會版本
```

現行行為會因同名歌曲存在多個候選而拒絕自動播放。

期望行為：

- 使用者沒有說「Live / 現場版」時，優先正式錄音室 / 原始專輯版本
- 使用者明確說「現場版 / Live」時，才優先 Live 候選
- 若仍然存在多個合理候選，才要求使用者補充資訊
- 不得單純取 Spotify 搜尋結果第一筆後直接播放

## 根本原因

### 1. Parser 可理解的版本提示太有限

目前 Parser 主要支援：

```text
播放晴天
播放周杰倫的晴天
播放周杰倫的晴天 (葉惠美)
```

其中括號形式適合文字測試，但不是可靠的 Siri 語音介面。

需要支援更自然的語句，例如：

```text
播放周杰倫的晴天，專輯葉惠美
播放葉惠美專輯的晴天
播放晴天原版
播放晴天錄音室版
播放晴天現場版
播放周杰倫的晴天現場版
```

### 2. Spotify ranking 沒有「版本語意」

目前 `SpotifyCatalog` 主要依：

- track name similarity
- artist similarity
- album similarity

排序。

它沒有理解：

- Live
- 演唱會
- Concert
- Tour
- Acoustic
- Remaster
- Deluxe
- Compilation
- Original / Studio

等版本資訊。

### 3. 裸歌名 exact matches 被一律視為 ambiguous

目前若沒有 artist，且 exact track-name matches 超過一個：

```python
if artist is None and len(exact_track_matches) > 1:
    return TrackResolution(track=None, ambiguous=True, ...)
```

這個規則太粗。

「同歌名、多版本」不等於「完全無法安全排序」。

## 建議修改方向

### A. 增加自然中文版本提示解析

Parser 應從語音文字抽出：

```text
track
artist
album
version_hint
```

例如：

```text
播放周杰倫的晴天，專輯葉惠美
```

可解析為：

```text
track = 晴天
artist = 周杰倫
album = 葉惠美
version_hint = null
```

而：

```text
播放周杰倫的晴天現場版
```

可解析為：

```text
track = 晴天
artist = 周杰倫
album = null
version_hint = live
```

若不希望立即修改 `ValidatedAction` schema，也可以先把版本提示作為 Spotify service/catalog 內部 ranking hint，但最終結構必須維持封閉且可驗證。

版本提示只屬於 Spotify 搜尋資料。

**絕對不可**因此放寬既有安全邊界。

### B. 建立「未指定 Live 時，正式版本優先」規則

當使用者沒有明確指定 Live / 現場版時，ranking 建議：

1. 歌名 exact match
2. artist exact / strong match
3. album exact match（若有提供）
4. 正式 studio album 候選加權
5. 明顯 Live / Concert / Tour / 演唱會候選降權
6. Compilation / Karaoke / Tribute / Cover 等非主要版本降權
7. 若 top candidate 與第二名仍過近，再回 ambiguous

不可只因為有兩個 exact track names 就直接 ambiguous。

### C. 明確支援 Live 意圖

若使用者說：

```text
現場版
live
演唱會版
concert version
```

應反向：

- Live 候選加權
- Studio 候選降權
- 如果有多場演唱會版本仍然接近，再要求補充

### D. 所有歌曲都必須使用同一套通用消歧策略

本問題不能以 `晴天`、周杰倫或任何特定歌曲建立 hardcoded 特例。

所有 Spotify 指定歌曲都應先把候選分類，再決定是否可以安全自動選擇。

至少區分以下三種 ambiguity：

#### Case A — 同一歌手、同一歌曲、不同版本

例如：

```text
告白氣球 — 周杰倫 — 周杰倫的床邊故事
告白氣球 — 周杰倫 — 地表最強世界巡迴演唱會
```

這屬於 version ambiguity。

若使用者未指定 Live：

- studio / original release 優先
- Live / Concert / Tour / 演唱會版本降權
- 若有明顯優勢，可直接播放

若使用者明確指定 Live：

- Live 候選優先
- 若多個 Live 版本仍無明顯差異，再要求補充

#### Case B — 不同歌手的同名歌曲

例如：

```text
I Will Always Love You — Whitney Houston
I Will Always Love You — Dolly Parton
```

這不是「原版 vs Live」問題，而是不同作品 / 不同表演者之間的 artist ambiguity。

如果使用者沒有提供歌手，而且不同歌手都有合理候選：

- 不得只因某一首比較熱門就自動選擇
- 不得把 Spotify 第一筆結果當成使用者意圖
- 應要求使用者補充歌手

例如可回：

```text
找到不同歌手的同名歌曲，請再說歌手名稱。
```

如果使用者已說歌手，則該歌手的 exact / strong match 必須明顯高於其他歌手。

#### Case C — 同一歌手、同一錄音、不同發行版本

例如同一錄音可能同時存在於：

```text
Original album
Deluxe edition
Remaster
Anniversary edition
Reissue
Compilation
```

這些候選不一定代表使用者能感知到的不同表演版本。

若能合理判定為同一錄音族群，可：

- 優先 original / canonical studio album
- 把 Deluxe / Remaster / Anniversary / Reissue 視為次要發行差異
- 不需要因每一個 re-release 都向使用者詢問

但如果 metadata 不足以安全判定它們屬於同一錄音，仍應保留 ambiguous，而不是猜。

#### 通用候選處理流程

建議所有歌曲走相同流程：

```text
Spotify Search candidates
        ↓
track title normalization / exactness
        ↓
artist grouping
        ↓
version classification
studio / live / acoustic / remix / remaster / etc.
        ↓
album / release context
        ↓
依使用者明確語意重新排序
        ↓
confidence gap 足夠 → 播放
confidence gap 不足 → 詢問
```

核心原則：

- 不為特定歌曲 hardcode album / artist / track ID
- 不以「熱門」代替 artist / version 意圖
- 同歌手不同版本可以使用版本規則排序
- 不同歌手同名通常需要使用者補充
- 同一錄音的 reissue/remaster 不必無條件視為完全不同歌曲
- 最終仍以「有明顯安全優勢才自動選，沒有就問」為準

### E. 播放次數 / 熱門度只能當輔助訊號

不要把「播放次數最高」當成「原版」。

原因：

- Spotify Web API 不提供穩定可依賴的歌曲總播放次數欄位
- Spotify Track 的 `popularity` 欄位已不適合作為長期核心依賴
- 熱門版本不一定是原版
- Live、remaster 或重新發行版本可能反而更熱門

若有可用熱門度資訊，只能作為 tie-breaker，不能高於：

```text
使用者明確版本意圖
> artist / album 精確匹配
> studio vs live 語意
> 搜尋結果品質
> 熱門度輔助
```

### F. 可考慮本機個人播放偏好

可選做，不應成為本次 blocker 的必要條件。

當 Agent 過去已成功解析某個：

```text
track + artist -> trusted Spotify track_id
```

可在本機保存非敏感的 preference / recent successful resolution。

之後遇到同樣歌曲歧義時，可作為最後的 ranking signal。

注意：

- 不保存 OAuth token
- 不把本機偏好資料傳給 Siri
- 不允許 remote client 直接指定 track URI
- trusted track reference 仍必須來自 Spotify API

## 建議的 Ranking 概念

以下只是設計方向，不要求直接照分數硬編碼：

```text
Exact track title
+ Exact artist
+ Exact album
+ User requested version match
+ Likely studio/original release

- Explicit Live mismatch
- Concert / Tour / 演唱會 when user did not request Live
- Karaoke / Tribute / Cover
- Weak fuzzy title
- Weak artist match
```

關鍵原則：

> 有明顯安全優勢時可以自動選；沒有明顯優勢時才詢問，不得猜。

## 建議新增 / 修改測試

至少增加：

```text
播放晴天
播放周杰倫的晴天
播放周杰倫的晴天，專輯葉惠美
播放葉惠美專輯的晴天
播放晴天原版
播放晴天現場版
播放周杰倫的晴天現場版
```

Spotify Catalog mocked cases：

1. studio + live 同名，未指定版本 → studio 勝出
2. studio + live 同名，指定 live → live 勝出
3. 多個 live 且無明顯優勢 → ambiguous
4. album 明確指定 → exact album 勝出
5. artist 明確指定 → 不得被其他歌手同名版本取代
6. popularity / result order 不得覆蓋明確版本語意
7. injection-like track / artist / album/version 字串只能進 Spotify search，不得進 shell/path/URL
8. 仍無法明確判斷時必須回 `SPOTIFY_AMBIGUOUS_TRACK`

## 建議驗收案例

真實 Windows + Spotify + Siri Shortcut 至少驗證：

### Case 1 — 裸歌名

對 Siri 說：

```text
播放晴天
```

若 Spotify 搜尋中原版與 Live 並存，應優先合理的 studio/original candidate，而不是立即報錯。

### Case 2 — 指定歌手

```text
播放周杰倫的晴天
```

應避免同名其他歌手。

### Case 3 — 指定專輯

```text
播放周杰倫的晴天，專輯葉惠美
```

應播放 `葉惠美` 專輯版本。

### Case 4 — 指定 Live

```text
播放晴天現場版
```

應優先 Live / 演唱會版本。

### Case 5 — 真正歧義

若仍有多個合理且無明顯優勢的候選：

- 不得亂播
- 回傳清楚的 Siri 可朗讀訊息
- 要求使用者補充歌手 / 專輯 / 版本

## 安全要求

本 bug 修正不得破壞既有安全資料流：

```text
Siri Text
→ Parser
→ ValidatedAction
→ SpotifyService
→ SpotifyCatalog
→ trusted SpotifyTrackRef
→ SpotifyPlayer
```

歌名、歌手、專輯、版本文字只能當 Spotify Search API 的搜尋資料。

不得成為：

- shell command
- CMD / PowerShell
- executable path
- command-line argument
- process ID
- local filesystem path
- arbitrary URL
- client-provided Spotify URI

## 完成與刪除條件

只有以下條件全部成立，才算此 bug 解決：

- [ ] 自然中文專輯 / 版本提示解析完成
- [ ] studio / original vs Live ranking 規則完成
- [ ] 未指定 Live 時，不會因為存在 Live 候選就一律報 ambiguous
- [ ] 明確指定 Live 時能優先 Live 版本
- [ ] 真正無法判斷時仍會安全回 ambiguous
- [ ] 相關 unit tests 通過
- [ ] security tests 未被削弱
- [ ] 真實 Windows Spotify 驗收通過
- [ ] 真實 iPhone Siri Shortcut E2E 驗收通過
- [ ] `PROJECT_STATUS.md` 已更新為最新真實狀態

**完成以上全部項目後，必須刪除：**

```text
docs/BUG_SPOTIFY_SIRI_DISAMBIGUATION.md
```

不要把本檔保留成永久規格文件。

若其中任何一項尚未完成，本檔仍應保留。
