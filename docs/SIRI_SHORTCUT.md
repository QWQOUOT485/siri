# Apple Shortcuts (捷徑) 設定指南

本指南將教您如何設定 iPhone 上的「捷徑」(Shortcuts) App，讓您可以透過 Siri 語音控制您的 Windows 電腦。整個設定過程非常簡單，不需要編寫任何複雜的程式碼！

## 1. 捷徑運作原理

建議在 iPhone 上建立一個**名稱獨特、不容易與 Siri 原生指令撞名**的捷徑。

例如：

```text
Windows 管家
電腦遙控器
我的電腦控制
```

不建議只依賴過於泛用的名稱，因為後續若捷徑已結束，像「下一首」「第二首」這類短句可能會被 Siri 當成 iPhone 自己的指令。

**目前實機驗收通過的穩定流程：**

1. 對 Siri 說捷徑名稱，例如：「嘿 Siri，電腦管家」
2. Shortcut 取得第一輪語音輸入並 POST 到 Windows Agent
3. Agent 若能直接執行，就完成一般控制
4. Agent 若回傳 `clarification_token`，Shortcut 先朗讀最多三個候選
5. **只有在 clarification 分支內**執行「關閉 Siri 並繼續（Dismiss Siri and Continue）」
6. 關閉 Siri 後立即執行第二次「聽寫文字」
7. 使用者說「第一首／第二首／第三首」等選擇
8. Shortcut 將第二輪文字 + 原 `clarification_token` POST 回 Agent
9. Agent 只在原 server-created candidate set 中選擇並播放

> **核心原則：** 「關閉 Siri 並繼續」不要放在捷徑最前面。它應放在「候選已朗讀完成」之後、第二次聽寫之前。這樣一般指令保持 Siri 語音體驗，只有歌曲需要消歧時才退出 Siri session，避免 Siri 把「第一首」誤判成自己的排程／提醒指令。

## 2. 建立穩定版 Siri Shortcut

請在 iPhone 上開啟「捷徑」App，點擊右上角的「+」新增捷徑。

### 2.1 捷徑名稱

建議使用：

```text
Windows 管家
```

或其他不容易和 Siri 原生功能撞名的名稱。

### 步驟 A：取得第一輪語音指令

使用目前可正常由 Siri 啟動的語音輸入動作取得第一輪指令，並將結果作為第一次 POST 的 `text`。

設定建議：

- 語言：**中文（台灣）**
- 第一輪不要先執行「關閉 Siri 並繼續」
- 一般指令直接沿用 Siri 語音流程

例如：

```text
你：嘿 Siri，電腦管家
你：播放 Stay
→ POST 到 Windows Agent
```

「關閉 Siri 並繼續」只在 Agent 回傳歌曲 clarification 時使用，位置見下方 Spotify 流程。

### 步驟 C：傳送指令到電腦
加入 **取得 URL 內容 (Get Contents of URL)** 動作。
- **URL**：請輸入您電腦的 API 網址，例如 `http://192.168.x.x:8000/command`（請替換為您電腦實際的區域網路 IP）。
- **方法 (Method)**：選擇 `POST`
- **標頭 (Headers)**：
  - 新增一個標頭，鍵 (Key) 填入 `X-API-Key`
  - 值 (Value) 填入您在 Windows 電腦端產生的 API 密碼。
- **要求主體 (Request Body)**：選擇 `JSON`，並新增一個文字欄位：
  - 鍵 (Key) 填入 `text`
  - 值 (Value) 選擇步驟 A 的第一輪語音輸入結果

### 步驟 D：讀取電腦的回應
Windows 電腦處理完畢後，會回傳一段包含結果的 JSON 格式訊息。捷徑會自動解析這些內容。
- 從「取得 URL 內容」的結果中，取得 `message` 欄位的值。

### 步驟 E：Siri 語音回報
加入 **朗讀文字 (Speak Text)** 動作。
- 將要朗讀的文字設定為步驟 C 取得的 `message` 內容。

---

## 3. Spotify 播放指定歌曲

第一版音樂功能固定使用 Spotify，因此 **不需要在捷徑裡選 YouTube Music / Apple Music / Spotify**。

你只要照平常方式把整句話送到 `POST /command`：

- 「播放」
- 「播放音樂」
- 「播放晴天」
- 「播放周杰倫的晴天」
- 「播放周杰倫的晴天 (葉惠美)」
- 「播放周杰倫的晴天，專輯葉惠美」
- 「播放葉惠美專輯的晴天」
- 「Spotify 播放周杰倫的晴天」
- 「暫停」/「暫停音樂」
- 「下一首歌」
- 「上一首歌」

Windows Agent 會自行解析：

```text
播放周杰倫的晴天
↓
track = 晴天
artist = 周杰倫
album = optional album/version hint
↓
Spotify 搜尋
↓
找到可信 Spotify track
↓
在 Windows Spotify 裝置播放
```

捷徑本身不需要保存 Spotify Token，也不需要直接呼叫 Spotify API；Spotify OAuth 與播放控制全部留在 Windows Agent。

如果歌名太模糊，例如只說「播放 Stay」而 Spotify 找到多個合理結果，Agent 不會亂選；它會最多列出三個候選並回傳 `clarification_required=true`。

穩定版 Shortcut 應在**同一次捷徑執行內**完成第二輪：

```text
第一輪語音輸入
→ POST /command
→ 從 URL 內容取得辭典
→ 取得 clarification_token
→ If Token 包含任何數值
→ Speak 候選 message
→ 關閉 Siri 並繼續
→ 第二次 Dictate Text
→ POST /command + clarification_token
→ 播放成功後結束 Shortcut
```

第二次語音例如：

```text
第一首
第二首
第三首
劉若英那首
```

都必須由第二個 Dictate Text 接住。

**已驗證的關鍵修正：** 先讓 Siri 朗讀候選，再執行「關閉 Siri 並繼續」，接著立刻啟動第二個 Dictate Text。若把「關閉 Siri 並繼續」放在捷徑最前面，後續輸入可能退成打字；若完全不關 Siri，第二輪「第一首」可能被 Siri 自己攔截並追問「要設在什麼時候」。

Shortcut 只能保存/回傳 opaque `clarification_token`，不得自行組造 Spotify URI 或 track ID。

---

## 4. 關機的二次確認流程 (進階安全)

為了防止誤觸關機指令，Windows Siri Agent 內建了「二次確認」機制。如果您希望捷徑能支援此功能，您可以在取得回應後加入一個簡單的 `If` 判斷：

1. 檢查回應的 `confirmation_required` 是否為 `true`。
2. 如果是，捷徑彈出一個確認視窗：「確定要關閉 Windows 電腦嗎？」
3. 如果您點擊「確定」，捷徑會將回應中附帶的 `confirmation_token` 再次 `POST` 到伺服器，完成關機。
4. 如果您點擊「取消」，則什麼都不做。

*(為保持捷徑簡潔，此步驟為選用，您也可以選擇單純聆聽 Siri 的拒絕回應。)*

---

## 5. Siri 第二輪搶走「第一首」的已驗證修正

如果歌曲需要 clarification，而你說「第一首／第二首／第三首」時 Siri 跳去自己的提醒事項、日期／時間流程，甚至追問「要設在什麼時候」，請確認 Shortcut 的順序是：

```text
朗讀候選
→ 關閉 Siri 並繼續
→ 第二次聽寫文字
→ POST②
```

這個順序已完成 iPhone 實機驗收，可保留全語音操作。

### 5.1 確認第二句是否發生在 Dictate Text 中

最重要。

若 Windows Agent 完全沒有收到 `POST /command`，代表第二句根本沒有進入 Shortcut。

### 5.2 將 Dictate Text 語言設為中文（台灣）

避免：

```text
下一首
```

被語音辨識成：

```text
下一週
下週
```

### 5.3 使用較完整的測試語句

定位問題時可以先說：

```text
下一首歌
Spotify 下一首
切到下一首
```

如果完整語句成功、單獨「下一首」失敗，問題多半在 Siri/Dictate Text 語音辨識，而不是 Windows Agent。

### 5.4 使用獨特捷徑名稱

例如：

```text
Windows 管家
```

比過於泛用或容易和系統語意混淆的名稱穩定。

### 5.5 判斷問題在 iPhone 還是 Agent

```text
Agent 沒收到 POST
→ iPhone / Shortcut / Siri 流程問題

Agent 收到 text=下一週
→ Siri Dictate Text 語音辨識問題

Agent 收到 text=下一首
但沒有執行
→ Windows Parser / Service 問題
```

這個判斷可以避免把 iPhone 語音辨識問題錯當成 Spotify 或 Agent bug。

---

## 6. 區域網路權限提醒

當您第一次執行這個捷徑時，iPhone 可能會跳出提示，詢問是否允許「捷徑」存取您的**區域網路 (Local Network)**。

⚠️ **請務必點選「允許」**，否則 iPhone 將無法連線到您的 Windows 電腦。
如果您不小心按到拒絕，請至 iPhone 的「設定」>「隱私權與安全性」>「區域網路」中，將「捷徑」的開關打開。

---

## 7. 常見的 Siri 回應與錯誤訊息

您的捷徑會自動朗讀以下幾種 Windows 傳回的訊息：

- ✅ **執行成功**：
  - 「已開啟 Discord。」
  - 「音量已提高。」
  - 「已鎖定電腦。」
- ❌ **執行失敗 (錯誤)**：
  - 「找不到 Discord。」
  - 「無法啟動該程式，請檢查設定。」
- ❓ **需要釐清 (歧義)**：
  - 「找到多個可能的 Stay，請說第一首、第二首或第三首。」

---

## 8. 語音指令範例

您可以嘗試對 Siri 說以下指令：

**中文指令：**
- 「開啟 Discord」 / 「打開 YouTube Music」
- 「關閉 Chrome」
- 「播放」 / 「播放音樂」→ Spotify 恢復播放
- 「播放晴天」 / 「播放周杰倫的晴天」 / 「播放周杰倫的晴天 (葉惠美)」→ Spotify 搜尋並播放指定歌曲
- 「暫停」 / 「暫停音樂」 / 「下一首歌」 / 「上一首歌」→ 控制 Spotify
- 「音量大一點」 / 「靜音」
- 「鎖定電腦」
- 「重新掃描程式」
- 「強制關閉 Line」 *(請謹慎使用)*

**英文指令 (English Commands):**
- "Open Discord" / "Launch Photoshop"
- "Close Chrome"
- "Play" → resume Spotify
- "Play Blinding Lights by The Weeknd" → search Spotify and play the matching track
- "Pause" / "Next track" / "Previous track" → control Spotify
- "Volume up" / "Mute"
- "Lock PC"
- "Refresh apps"

> ✨ 盡情享受用語音控制 Windows 電腦的便利吧！
