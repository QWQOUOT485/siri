# Windows Siri Agent 

這是一個讓你透過 iPhone 的 Siri 來語音控制 Windows 電腦的工具。
只要在同一個家中網路（Wi-Fi），你就可以對著手機說：「嘿 Siri，控制電腦」，接著說「開啟 Spotify」或「關機」，電腦就會自動執行！

## 這是什麼專案？
本專案透過區域網路（LAN），讓 iPhone 的 Siri 捷徑能夠安全地發送指令給 Windows 電腦上的代理程式（Agent），並執行對應的操作。

## 它可以做什麼？
- **開啟/關閉應用程式**（例如：Discord, Chrome, Steam 等）
- **Spotify 音樂控制**（播放、暫停、上一首、下一首，以及「播放周杰倫的晴天」這類指定歌曲播放）
- **音量控制**（調高、調低、靜音）
- **系統控制**（鎖定電腦、關機。關機會有防呆兩步確認）

## 基本架構
```text
iPhone → Siri → Apple Shortcuts (捷徑) → 家中區域網路 (LAN) → Windows Agent → Windows 系統
```

## 快速開始

### 第一步：安裝
1. 下載本專案資料夾。
2. 點擊或執行 `setup.ps1` 來安裝所需的環境與套件。

### 第二步：啟動
1. 執行 `start.bat` 來啟動 Agent 伺服器。
2. （選擇性）你可以將其設定為透過「工作排程器 (Task Scheduler)」開機自動啟動。

### 第三步：連結 Spotify
指定歌曲播放使用 Spotify Web API，需要 Spotify Premium 與一次性的 Spotify OAuth 授權。Spotify Token 只保存在 Windows 本機，不放進 iPhone 捷徑。詳細規格請見：[Spotify 整合](docs/SPOTIFY.md)。

### 第四步：設定 Siri 捷徑
1. 在 iPhone 上建立一個名為「控制電腦」的捷徑。
2. 詳細設定步驟請參考：[Siri 捷徑設定教學](docs/SIRI_SHORTCUT.md)。

---

## 網路健康度測試步驟
如果在 iPhone 上無法控制電腦，請按照以下步驟測試：
1. **Windows 端確認**：確認 `start.bat` 已經執行，且伺服器顯示執行中。
2. **iPhone Safari 測試**：確保手機連上家裡 Wi-Fi。在 Safari 瀏覽器中輸入 `http://<你的電腦IP>:<通訊埠>/health`。如果畫面顯示健康資訊，代表網路連線正常。
3. **疑難排解**：如果 Safari 無法連上，請參考下方的「常見問題與疑難排解」。

---

## 跨樓層使用問題：「1樓可以用但4樓不能用？」
如果你家有多個樓層或是不同的 Wi-Fi 路由器：
- 只要不同的 Wi-Fi（例如1樓與4樓）是在同一個**內部網路 (LAN)** 並且可以互相路由 (Routing)，這個工具就能正常運作。
- 如果4樓的 Wi-Fi 是另一個獨立的網段且沒有連接到1樓的網路，Siri 將無法找到電腦。
- 更多跨樓層連線細節請參考：[網路連線疑難排解](docs/NETWORKING.md)。

---

## 常見問題與疑難排解

- **如何找到 Windows IP？**：在命令提示字元 (CMD) 輸入 `ipconfig`，找到 IPv4 位址。
- **DHCP 固定 IP 建議**：建議在路由器的設定中，為你的 Windows 電腦設定 DHCP 保留 (固定 IP)，這樣 IP 就不會一直變動。
- **如何測試 /health？**：在瀏覽器輸入 `http://<電腦IP>:埠號/health`。
- **如何檢查 Agent 找到了哪些程式？**：造訪 `http://<電腦IP>:埠號/apps` 來查看已偵測到的應用程式。
- **如何重新整理應用程式清單？**：可以重新啟動 Agent 或呼叫更新 API (若有提供)。
- **如何設定別名 (Aliases)？**：在設定檔中編輯程式的 aliases 欄位即可，例如把 `Google Chrome` 加上 `瀏覽器` 的別名。
- **如何設定網站？**：在網站設定檔 (website configuration) 中新增網址與對應名稱。
- **如何建立 iPhone 捷徑？**：簡要來說是使用「取得 URL 的內容」動作。詳細教學請見 [Siri 捷徑設定](docs/SIRI_SHORTCUT.md)。
- **如何設定 API Key？**：在安裝時或 `.env` 檔案中設定，並在 iPhone 捷徑的 Header 中加入 `Authorization` 欄位。
- **如何使用 Siri？**：對手機說「嘿 Siri，控制電腦」，然後說出指令（如：開啟記事本）。
- **不同樓層 Wi-Fi 無法使用？**：請參考 [NETWORKING.md](docs/NETWORKING.md)。
- **不同子網段 (Subnet) 處理**：確保路由器之間有設定好路由，且防火牆未阻擋。
- **訪客 Wi-Fi (Guest Wi-Fi) 疑難排解**：訪客網路通常有隔離功能，請確保手機連上的是**主要區域網路**。
- **AP 隔離 (AP Isolation) 疑難排解**：如果路由器開啟了 AP 隔離，裝置間將無法通訊，請進入路由器設定關閉此功能。
- **Windows 防火牆疑難排解**：確保 Windows 防火牆允許 Agent 的通訊埠 (Port) 通過。
- **公用網路設定 (Public Network Profile) 疑難排解**：請確認 Windows 的網路類型設定為「私人 (Private)」，否則防火牆預設會阻擋外部連線。
- **如何解除安裝？**：刪除專案資料夾，並到工作排程器移除自動啟動任務即可。

---

## 文件導覽
- [架構說明](docs/ARCHITECTURE.md)
- [API 規格](docs/API.md)
- [安全性說明](docs/SECURITY.md)
- [產品規格](docs/SPEC.md)
- [Siri 捷徑設定](docs/SIRI_SHORTCUT.md)
- [Spotify 整合](docs/SPOTIFY.md)
- [網路連線疑難排解](docs/NETWORKING.md)
- [Windows 整合](docs/WINDOWS.md)
- [測試規範](docs/TESTING.md)

---
> [!WARNING]
> **安全性與 HTTP 注意事項**：
> 本工具在區域網路內傳輸未經加密（無 HTTPS），其安全性完全仰賴於你的「可信賴家庭網路」、「Windows 防火牆」、「API Key 驗證」以及「絕不暴露於網際網路 (Internet)」。**絕對不要**使用 Port Forwarding 等方式將此 Agent 公開到網際網路上。
