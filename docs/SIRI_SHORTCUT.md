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

**穩定版運作流程：**

1. 對 Siri 說捷徑名稱，例如：「嘿 Siri，Windows 管家」
2. 捷徑先用「朗讀文字」說：「請說電腦指令」
3. 捷徑立刻執行「聽寫文字」，由 Shortcut 自己接住下一句
4. 使用者說：「下一首」「播放晴天」「開啟 Discord」等
5. 捷徑把聽寫結果 POST 到 Windows Agent
6. Agent 回傳 JSON
7. 捷徑朗讀 `message`
8. 如果需要 clarification，捷徑在**同一次捷徑執行內**再次朗讀候選並執行第二次「聽寫文字」

> **核心原則：** 「下一首」「第二首」等語句必須在 Shortcut 的「聽寫文字」動作正在等待輸入時說出。若捷徑已經結束，Siri 會把下一句當成 iPhone 自己的普通 Siri 指令，而不是送到 Windows Agent。

## 2. 建立穩定版 Siri Shortcut

請在 iPhone 上開啟「捷徑」App，點擊右上角的「+」新增捷徑。

### 2.1 捷徑名稱

建議使用：

```text
Windows 管家
```

或其他不容易和 Siri 原生功能撞名的名稱。

### 步驟 A：朗讀提示

加入 **朗讀文字 (Speak Text)**：

```text
請說電腦指令
```

這一步很重要，目的是讓使用者知道接下來的語音會由捷徑自己的 Dictate Text 收取，而不是交回一般 Siri。

### 步驟 B：取得語音指令

加入 **聽寫文字 (Dictate Text)** 動作。

設定建議：

- 語言：**中文（台灣）**
- 聽寫結果作為後續 POST 的 `text`
- 不要在這個動作前結束捷徑

正常體驗：

```text
你：嘿 Siri，Windows 管家
捷徑：請說電腦指令
你：下一首
→ 「下一首」進入 Dictate Text
→ POST 到 Windows Agent
```

錯誤體驗：

```text
你：嘿 Siri，Windows 管家
捷徑：已完成
你：下一首
→ 此時「下一首」已不屬於捷徑
→ Siri 可能控制 iPhone 媒體或誤判成其他原生指令
```

### 步驟 C：傳送指令到電腦
加入 **取得 URL 內容 (Get Contents of URL)** 動作。
- **URL**：請輸入您電腦的 API 網址，例如 `http://192.168.x.x:8000/command`（請替換為您電腦實際的區域網路 IP）。
- **方法 (Method)**：選擇 `POST`
- **標頭 (Headers)**：
  - 新增一個標頭，鍵 (Key) 填入 `X-API-Key`
  - 值 (Value) 填入您在 Windows 電腦端產生的 API 密碼。
- **要求主體 (Request Body)**：選擇 `JSON`，並新增一個文字欄位：
  - 鍵 (Key) 填入 `text`
  - 值 (Value) 選擇步驟 B 的「聽寫的文字」

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
第一次 Dictate Text
→ POST /command
→ clarification_required == true
→ Speak message
→ 保存 clarification_token
→ 第二次 Dictate Text
→ POST /command + clarification_token
→ Speak final message
```

第二次語音例如：

```text
第一首
第二首
第三首
劉若英那首
```

都必須由第二個 Dictate Text 接住。

不要讓第一次 POST 後就直接結束捷徑，否則使用者接著說「第二首」時，Siri 會把它當一般 iPhone 指令。

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

## 5. Siri 優先執行手機指令的排查

如果你說：

```text
嘿 Siri，Windows 管家
```

之後再說：

```text
下一首
```

卻出現 iPhone 自己的媒體控制、提醒事項、日期/時間追問，優先檢查以下項目：

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
