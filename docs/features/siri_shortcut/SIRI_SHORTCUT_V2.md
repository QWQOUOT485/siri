# iPhone 捷徑「Windows 管家」V2 建置稿

狀態：**已完成設計，尚未在 iPhone 安裝或驗收。** 2026-09-24 的現場問題是「換一批」後捷徑無聲結束；Windows Agent 已收到第二輪請求並回傳候選或釐清訊息。本稿取代只處理一次選歌的舊流程。

## 固定設定

- 捷徑名稱：`Windows 管家 V2`。先另建一個捷徑，保留現有捷徑供比較。
- `AgentURL`：沿用現有捷徑的區域網路網址，結尾為 `/command`。
- API key：沿用現有捷徑的 `X-API-Key` 值，只填在 iPhone 捷徑內；不要貼到截圖、聊天或本檔。
- 兩個「聽寫文字」都選中文（台灣）。
- 每次「取得 URL 內容」都用 `POST`、要求主體選 `JSON`、標頭 `X-API-Key` = 原捷徑的 API key。正常指令只送 `text`；歌曲追問只送 `text` 與 `clarification_token`。
- 每次 HTTP 回應都先取**該次回應**的 `message` 並「朗讀文字」，不以 `success` 或 `status` 決定要不要朗讀。候選頁的 `success=false`、`status=error` 是目前 API 的正常表示法。

## 動作順序

下列縮排表示捷徑的 `如果／否則／結束如果` 和 `重複／結束重複` 區塊。取字典值時，都明確指定該次「取得 URL 內容」的輸出，避免拿到第一次請求的舊值。

1. 加兩個 **URL** 動作：第一個填入原捷徑的 `http://<電腦區網IP>:8000/command` → 設變數 `AgentURL`；第二個將結尾改為 `/action` → 設變數 `ActionURL`。API key 只在新捷徑的 HTTP 動作標頭中填入。
2. **聽寫文字** → 設變數 `CommandText`。
3. **取得 URL 內容** `AgentURL`：`POST`；JSON `text` = `CommandText` → 設變數 `Reply`。
4. **取得字典值** `message`（從 `Reply`）。若為空，朗讀「電腦沒有回覆文字，請稍後再試」並結束；否則 **朗讀文字** `message`。
5. **取得字典值** `confirmation_required`（從 `Reply`）。如果為 `true`，執行下方「關機確認分支」並結束。
6. **取得字典值** `clarification_required`（從 `Reply`）。如果不是 `true`，結束。
7. **取得字典值** `clarification_token`（從 `Reply`）→ 設變數 `CurrentToken`。若沒有值，朗讀「沒有收到歌曲選擇資訊，請重新說出歌曲」並結束。
8. **關閉 Siri 並繼續**。這個動作只放一次，位置在首次候選朗讀之後、第二次聽寫之前。
9. **重複 5 次**：
   1. **聽寫文字** → 設變數 `FollowUpText`。若為空，朗讀「沒有聽到選擇，請重新開始」並結束。
   2. **取得 URL 內容** `AgentURL`：`POST`；JSON `text` = `FollowUpText`，`clarification_token` = `CurrentToken` → 設變數 `Reply`。
   3. **取得字典值** `message`（從新的 `Reply`）。若沒有值，朗讀「電腦沒有回覆文字，請稍後再試」並結束；否則 **朗讀文字** `message`。
   4. **取得字典值** `clarification_required`（從新的 `Reply`）。如果不是 `true`，結束捷徑。選歌成功、過期、已用過、驗證失敗等結果都已在上一個朗讀動作回報。
   5. **取得字典值** `clarification_token`（從新的 `Reply`）。如果有值，**覆蓋** `CurrentToken`；否則朗讀「沒有收到下一輪歌曲選擇資訊，請重新說出歌曲」並結束。
10. 若 5 次追問後仍需釐清，朗讀「這次選歌次數已到上限，請重新說出完整歌名與歌手」並結束。

「結束」可用「停止並輸出」，輸出方式選「不執行任何動作」。它必須在已朗讀回應後執行。第 8 步的 5 次是捷徑對話上限；Agent 自己仍只允許最多兩次成功換批，並維持短效 token。`SPOTIFY_CLARIFICATION_UNCLEAR` 或沒有更多候選時，Agent 可能保留同一 token，捷徑仍會朗讀其訊息並容許使用者選目前的歌曲。

## 關機確認分支

第一輪回應的 `confirmation_required=true` 時，已先朗讀 Agent 的確認訊息。接著：

1. **取得字典值** `confirmation_token`（從第一輪 `Reply`）。若沒有值，朗讀「沒有收到關機確認資訊」並結束。
2. **從選單中選擇**：`確認關機`、`取消`。`取消` 分支直接結束；**絕不自動選「確認關機」**。
3. 只有 `確認關機` 分支才用「取得 URL 內容」向 `ActionURL` 送 `POST`；JSON `action` = `confirm_shutdown`、`confirmation_token` = 上一步讀取的值；標頭仍是 `X-API-Key`。
4. 取這次 `/action` 回應的 `message` 並朗讀，然後結束。

## 驗收順序

1. 先在 iPhone 捷徑編輯器直接執行一般安全指令（例如「播放音樂」或「暫停」），確認有朗讀 Agent 的訊息。
2. 用容易出現多首候選的歌名，確認第一批被朗讀。說「換一批」，確認第二批或「沒有更多候選」**一定被朗讀**。
3. 若有第二批，說「第一首」等選擇，確認 Agent 朗讀播放結果；再試一次「換一批」確認 token 更新且沒有重用舊 token。
4. 最後用 Siri 啟動新捷徑做全語音測試。記錄是否出現第二次聽寫、每次是否朗讀，不把捷徑編輯器測試當作 Siri 驗收。
5. 關機分支只檢查「取消」能安全結束；若要做實際關機驗收，另行安排受控測試。

## 目前證據邊界

這是可照著建置的動作稿，**不是已安裝的 `.shortcut` 檔或可點擊的 iCloud 分享連結**。目前工作環境無法控制 iPhone 捷徑編輯器，故安裝、Siri 朗讀、解鎖狀態與真實換批驗收仍待 iPhone 實測。

Apple 官方說明：[POST/JSON 的「取得 URL 內容」](https://support.apple.com/en-sg/guide/shortcuts/apd58d46713f/ios)、[字典取值](https://support.apple.com/en-ca/guide/shortcuts/apdf01294032/ios)、[條件](https://support.apple.com/en-ie/guide/shortcuts/apd83dcd1b51/ios)、[重複](https://support.apple.com/en-gu/guide/shortcuts/apdc11deb2c1/ios)、[停止並輸出](https://support.apple.com/en-is/guide/shortcuts/apda9578f70f/ios)、[選單](https://support.apple.com/guide/shortcuts/use-the-choose-from-menu-action-apdd7bf369da/10.0/ios/27)。
