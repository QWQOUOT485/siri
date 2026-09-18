# Apple Shortcuts (捷徑) 設定指南

本指南將教您如何設定 iPhone 上的「捷徑」(Shortcuts) App，讓您可以透過 Siri 語音控制您的 Windows 電腦。整個設定過程非常簡單，不需要編寫任何複雜的程式碼！

## 1. 捷徑運作原理

我們將在 iPhone 上建立一個名為「**控制電腦**」的捷徑。

**運作流程：**
1. 您對著 iPhone 說：「嘿 Siri，控制電腦」
2. Siri 會啟動捷徑並聽取您的指令（例如：「開啟 Discord」）
3. 捷徑將您的文字指令透過區域網路安全地傳送到 Windows 電腦
4. Windows 電腦執行動作後回傳結果
5. Siri 語音告訴您執行結果（例如：「已開啟 Discord」）

> 💡 **小提醒**：所有的智慧解析與判斷都由 Windows 電腦端處理，因此您的 iPhone 捷徑只需要最基本的「傳送與接收」功能，保持極度簡單！

## 2. 建立「控制電腦」捷徑

請在 iPhone 上開啟「捷徑」App，點擊右上角的「+」新增捷徑，並將捷徑名稱命名為 **控制電腦**。

接著，請依序加入以下幾個動作：

### 步驟 A：取得語音指令
加入 **聽寫文字 (Dictate Text)** 動作。
- 當 Siri 啟動此捷徑時，會自動聆聽您接下來要說的話。

### 步驟 B：傳送指令到電腦
加入 **取得 URL 內容 (Get Contents of URL)** 動作。
- **URL**：請輸入您電腦的 API 網址，例如 `http://192.168.x.x:8000/command`（請替換為您電腦實際的區域網路 IP）。
- **方法 (Method)**：選擇 `POST`
- **標頭 (Headers)**：
  - 新增一個標頭，鍵 (Key) 填入 `X-API-Key`
  - 值 (Value) 填入您在 Windows 電腦端產生的 API 密碼。
- **要求主體 (Request Body)**：選擇 `JSON`，並新增一個文字欄位：
  - 鍵 (Key) 填入 `text`
  - 值 (Value) 選擇步驟 A 的「聽寫的文字」

### 步驟 C：讀取電腦的回應
Windows 電腦處理完畢後，會回傳一段包含結果的 JSON 格式訊息。捷徑會自動解析這些內容。
- 從「取得 URL 內容」的結果中，取得 `message` 欄位的值。

### 步驟 D：Siri 語音回報
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
- 「下一首」
- 「上一首」

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

如果歌名太模糊，例如只說「播放 Stay」而 Spotify 找到多個合理結果，Agent 不會亂選；它會最多列出三個候選，並朗讀：「找到多個可能的 Stay，請說第一首、第二首或第三首。」

若捷徑要支援這個第二輪流程，需保留回應中的 `clarification_token`，再把使用者的回答與 token 一起送回同一個 `/command`。Token 只短時間有效且只能使用一次；捷徑不能自行組造 Spotify URI 或 track ID。若目前捷徑尚未保存 token，請重新說出包含歌手／專輯的完整歌曲指令。

---

## 4. 關機的二次確認流程 (進階安全)

為了防止誤觸關機指令，Windows Siri Agent 內建了「二次確認」機制。如果您希望捷徑能支援此功能，您可以在取得回應後加入一個簡單的 `If` 判斷：

1. 檢查回應的 `confirmation_required` 是否為 `true`。
2. 如果是，捷徑彈出一個確認視窗：「確定要關閉 Windows 電腦嗎？」
3. 如果您點擊「確定」，捷徑會將回應中附帶的 `confirmation_token` 再次 `POST` 到伺服器，完成關機。
4. 如果您點擊「取消」，則什麼都不做。

*(為保持捷徑簡潔，此步驟為選用，您也可以選擇單純聆聽 Siri 的拒絕回應。)*

---

## 5. 區域網路權限提醒

當您第一次執行這個捷徑時，iPhone 可能會跳出提示，詢問是否允許「捷徑」存取您的**區域網路 (Local Network)**。

⚠️ **請務必點選「允許」**，否則 iPhone 將無法連線到您的 Windows 電腦。
如果您不小心按到拒絕，請至 iPhone 的「設定」>「隱私權與安全性」>「區域網路」中，將「捷徑」的開關打開。

---

## 6. 常見的 Siri 回應與錯誤訊息

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

## 7. 語音指令範例

您可以嘗試對 Siri 說以下指令：

**中文指令：**
- 「開啟 Discord」 / 「打開 YouTube Music」
- 「關閉 Chrome」
- 「播放」 / 「播放音樂」→ Spotify 恢復播放
- 「播放晴天」 / 「播放周杰倫的晴天」 / 「播放周杰倫的晴天 (葉惠美)」→ Spotify 搜尋並播放指定歌曲
- 「暫停」 / 「暫停音樂」 / 「下一首」 / 「上一首」→ 控制 Spotify
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
