# Siri Shortcut Spotify Clarification E2E Report

日期：2026-09-19

## 目的

驗證 iPhone Siri Shortcut 是否能完成 Windows Siri Agent 的 Spotify 歌曲消歧流程：

1. 使用者以 Siri 啟動 Shortcut。
2. Shortcut 將第一輪歌曲指令 POST 到 Windows Agent。
3. Agent 回傳最多三個 trusted candidates 與 opaque `clarification_token`。
4. 使用者選擇候選。
5. Shortcut 將第二輪選擇文字與同一個 token POST 回 Agent。
6. Agent 只在原 server-created candidate set 中完成選擇並播放。

本次驗收不改變既有安全邊界：client 不傳 Spotify URI / track ID，token 只作為 server-side clarification context 的 opaque reference。

## 實機結果摘要

### 已驗證成功

- 第一輪 `POST /command` 可正常回傳歌曲候選。
- Shortcut 可將第一次 HTTP response 由文字轉為辭典後讀取：
  - `message`
  - `clarification_token`
- `clarification_token` 保存成 Shortcut 變數後，可在第二次 POST 正確帶回。
- 第二次 POST 的 request body 使用：
  - `text` = 第二輪使用者選擇
  - `clarification_token` = 第一輪 server 回傳的 token
- 使用「第一首」作為第二輪選擇時，Windows Agent 能成功解析並播放候選歌曲。
- 第二次 POST 成功後可直接結束 Shortcut；不需要再次朗讀 final message 才能完成播放。
- 因此 server-side clarification selection + Spotify playback 的實機 E2E 已由 iPhone Shortcut 成功觸發。

## Shortcut 實作重點

### 第一輪

```text
輸入歌曲指令
→ POST /command
→ 從 URL 內容取得辭典
→ 取得 clarification_token
→ 設定變數 Token
→ If Token 包含任何數值
```

iOS Shortcut 的 If 在此不直接依賴 `clarification_required` 的 true/false 判斷，而是檢查 `clarification_token` 是否存在，避免「false 仍然是一個值」造成誤判。

### 第二輪

```text
取得候選 message
→ 顯示／朗讀候選
→ 取得第二輪使用者選擇
→ POST /command
   text = 第二輪選擇
   clarification_token = Token
→ 播放成功後結束 Shortcut
```

第二次 POST 的 `Token` 必須是 Shortcut 變數，不可手動輸入字串 `"Token"`。

每一次 POST response 都應先執行「從 URL 內容取得辭典」，不可直接把 HTTP response 文字拿去做「取得辭典值」。

## 本次除錯中確認的失敗模式

### 1. HTTP response 是文字，不是 Shortcut 辭典

症狀：

```text
取得辭典值失敗，因為捷徑無法從「文字」轉換到「辭典」
```

修正：

```text
POST
→ 從 URL內容 取得辭典
→ 從該辭典取得 message / clarification_token
```

### 2. Token 指向錯誤值

如果先取得 `message`，再把模糊名稱「辭典值」存成 Token，可能實際保存到 message 而不是 `clarification_token`。

修正：取得 `clarification_token` 後立刻設定明確的 `Token` 變數。

### 3. 第二次 POST 的 Token 被當成普通文字

若 request body 實際送出：

```json
{
  "text": "第一首",
  "clarification_token": "Token"
}
```

server 不會收到真正的 clarification context。

修正：第二列 value 必須選取 Shortcut 的 `Token` magic variable。

### 4. 第二次 response 抓到第一次辭典

第二次 POST 後若仍讀第一輪 response，會再次顯示／朗讀原本的候選訊息。

修正：第二次 POST 後建立新的 response dictionary；若不需要成功語音回覆，也可以直接在播放成功後結束 Shortcut。

## Siri 二次語音交接問題

### 現象

Shortcut 本身從「捷徑」App 手動執行正常，但從：

```text
嘿 Siri，電腦管家
```

啟動後，後續第二輪短語音（例如「第一首」）有時會被 Siri 自己攔截，並出現與本專案無關的原生 Siri 追問，例如：

```text
要設在什麼時候？
```

此時 Windows Agent 沒有取得預期的第二輪輸入，問題位於 Siri → Shortcut 的互動交接，而不是 Spotify clarification service。

### 已驗證 workaround

在 Shortcut 前段使用「關閉 Siri 並繼續（Dismiss Siri and Continue）」後，可避免 Siri 繼續攔截後續輸入。

代價：後續「要求輸入」實測會落到文字輸入，因此目前穩定可用版本不是完整 hands-free voice clarification。

## 目前驗收結論

### 通過

- iPhone Shortcut → Windows Agent 第一輪歌曲搜尋。
- Agent → iPhone trusted candidates + clarification token。
- iPhone 保存 token。
- iPhone 第二輪回傳 selection + token。
- Agent server-side candidate selection。
- 真實 Spotify 播放。

### 尚未通過

- 從「嘿 Siri」啟動到第二輪候選選擇，全程 hands-free 語音且不被 Siri 原生功能攔截。
- 「關閉 Siri 並繼續」workaround 下仍維持第二輪純語音輸入。

因此本次應記錄為：

> **Spotify clarification iPhone E2E 已成功，但目前穩定 workaround 的第二輪需要文字輸入；完整 hands-free Siri clarification 仍未驗收。**

## 額外觀察：Spotify 候選品質

實機流程成功後發現，不帶歌手的模糊歌名可能出現偏冷門的 Spotify 候選。

目前程式的 candidate ranking 主要依賴：

- track title similarity
- artist similarity（若使用者有提供）
- album similarity（若使用者有提供）
- studio / secondary / live version classification

目前 Search request 未指定 `market=TW`，ranking 也沒有 popularity tie-breaker。這是後續搜尋品質改善項目，但不能用 popularity 取代 ambiguity safety：不同歌手的合理同名歌曲仍應要求使用者選擇，不應偷偷自動播放。

## Security Notes

- Shortcut 不保存 Spotify OAuth token。
- client 不得傳 Spotify URI 或 track ID 作為 clarification 選擇。
- `clarification_token` 保持 opaque，只能回傳 server 原本產生的 token。
- 本次除錯截圖曾顯示部分 API key；不得把 API key 寫入本報告、Git 或 log，建議將該 API key 旋轉後再繼續使用。

## 建議後續

1. 保留目前可穩定運作的 clarification flow。
2. 若要追求完全 hands-free，再獨立研究 Siri / Shortcuts 第二輪語音輸入限制，不應因此放寬 Agent parser 或安全邊界。
3. 另開 Spotify search quality 工作：
   - 評估 `market=TW`
   - 評估 popularity 只作 tie-breaker
   - 新增模糊中文歌名的 regression fixtures
4. API key 旋轉後更新 iPhone Shortcut 與 Windows Agent 設定。
