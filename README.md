# Windows Siri Agent

這是一個只在家中 LAN / Local Network 運作的 Windows Agent。你可以用 iPhone Siri 和一個 Apple Shortcut 說：

> 開啟 Discord

Agent 會在 Windows 本機的應用程式 catalog 裡找 Discord，再由 Windows 啟動它。Apple Shortcut 不需要維護一長串程式名稱或 `if/else`。

本專案不是 Remote Shell，也不是把 Windows 暴露到 Internet 的服務。它不提供 PowerShell、CMD、Python、任意 EXE、任意 URL 或檔案系統 API。

## 1. 第一次安裝

請在 Windows PowerShell 進入本資料夾：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

setup 會：

1. 檢查 Windows 與 Python 3.11+。
2. 建立隔離的 `.venv`。
3. 安裝 `requirements.txt`。
4. 建立 `.env` 並產生 256-bit 等級的隨機 API key。
5. 建立 `runtime`、`logs`，執行 application discovery 和 self-test。
6. 詢問是否建立只套用在 Private Profile 的 TCP 8000 Firewall rule。
7. 詢問是否用 Task Scheduler 的 **At log on** 啟動 Agent。

setup 不會偷偷改 Windows Network Profile、Router、NAT、UPnP，也不會安裝 Startup folder 項目或 Windows Service。若沒有 Python，請先從 [Python for Windows](https://www.python.org/downloads/windows/) 安裝；setup 不會未經確認自動安裝大量系統軟體。

若你沒有系統管理員權限，Firewall 規則可以先略過；Agent 本身仍可在本機測試。之後請用具備權限的 PowerShell 再執行 setup。

## 2. 啟動與停止

手動啟動：

```text
雙擊本資料夾的 scripts\start.bat
```

或：

```powershell
.\.venv\Scripts\python.exe -m app.main
```

啟動視窗保持開啟即可。手動啟動時按 `Ctrl+C` 停止。若你在 setup 中啟用 Task Scheduler，登入 Windows 後會以**目前使用者、Run only when user is logged on、Limited** 啟動，確保 GUI 程式和媒體控制落在正確的互動式桌面工作階段。

查看自動啟動狀態：

```powershell
Get-ScheduledTask -TaskName 'Siri Windows Agent'
```

重新安裝自動啟動：

```powershell
.\scripts\install-startup.ps1
```

移除自動啟動：

```powershell
.\scripts\uninstall-startup.ps1
```

不要把這個 Agent 當成一般 Windows Service 執行。非互動式 Session 可能回報成功但桌面上看不到 GUI。

## 3. 找 Windows IP 與測試 LAN

在 Windows 執行：

```powershell
ipconfig
```

找目前家用網卡的 IPv4，例如 `192.168.10.50`。setup 也會列出偵測到的 RFC1918 位址。建議在 Router 做 DHCP Reservation，讓 Windows 每次取得同一個 IP，不要優先在 Windows 裡手動設定 Static IP。

先在 Windows 瀏覽器測試：

```text
http://127.0.0.1:8000/health
```

再在 iPhone Safari 開：

```text
http://WINDOWS-IP:8000/health
```

例如：`http://192.168.10.50:8000/health`。應看到 `Agent online`。如果 iPhone Safari 都連不到，先處理 LAN、IP、Firewall 與網路隔離，再處理 Siri Shortcut。

不同樓層、不同 Wi-Fi 名稱或不同 Access Point 不一定有問題。例：

```text
iPhone  192.168.20.25
Windows 192.168.10.50
```

只要 Router / Layer 3 switch 允許 `192.168.20.0/24 -> 192.168.10.0/24` 的 routing 和 TCP 8000，Agent 就可以使用。`allowed_networks.yaml` 預設允許 RFC1918 的 `10/8`、`172.16/12`、`192.168/16`，並保留 loopback 測試；不要把 `0.0.0.0/0` 加進去。

## 4. Firewall 與 LAN 安全

setup 建立的規則名稱是 `Siri Windows Agent`，只允許：

- TCP 8000
- Private Profile
- RFC1918 private source networks

Public Profile 不會被偷偷改成 Private。HTTP 在可信任 LAN 上仍然**沒有傳輸加密**；安全邊界是家中可信任網路、Private Firewall、API key、不暴露 Internet 和不提供任意 shell。不要使用 Port Forwarding、UPnP、DDNS、Tailscale Funnel、Cloudflare Tunnel、ngrok 或公網 VPS。

下列情況會造成某些樓層能用、另一層不能用：

- Guest Wi-Fi
- AP Isolation / Client Isolation
- VLAN Isolation
- Inter-VLAN firewall 沒有允許到 Windows subnet 的 TCP 8000
- Windows Network Profile 是 Public
- Windows Firewall 沒有 Private rule
- Windows IP 變了，或使用了錯誤的網卡 IP
- Agent 沒啟動或 port 不是 8000
- Router 阻擋 LAN-to-LAN routing

## 5. iPhone Siri Shortcut

建立一個 Shortcut，名稱叫 **控制電腦**。第一次使用時 iOS 可能要求允許 Shortcuts 存取 Local Network；若拒絕，請到「設定 → 隱私權與安全性 → 區域網路」重新開啟 Shortcuts。

### 最簡單的正常指令流程

Shortcut 需要的主要動作只有：

1. **聽寫文字（Dictate Text）**。
2. **取得 URL 內容（Get Contents of URL）**。
3. **取得字典值（Get Dictionary Value）**，讀取回應的 `message`。
4. **朗讀文字（Speak Text）**。

在 `Get Contents of URL` 設定：

- URL：`http://WINDOWS-IP:8000/command`
- Method：`POST`
- Headers：`X-API-Key` = `.env` 裡的 `SIRI_AGENT_API_KEY`
- Request Body：`JSON`
- JSON：`text` = 前一步「聽寫文字」的結果

API key 只放在你自己的 Shortcut 和 Windows `.env`，不要貼到 GitHub、聊天或公開截圖。

完成後可以說：

> 嘿 Siri，控制電腦

接著說：

> 開啟 Discord

Shortcut 會把 JSON 回應中的 `message` 朗讀出來。

### 關機的唯一額外步驟

關機不能由單一自然語言請求直接執行。請在 Shortcut 加一個 `If`：

1. 讀取回應的 `confirmation_required`。
2. 如果是 `true`，顯示「確定要關閉 Windows 電腦嗎？」。
3. 使用者按 Confirm 後，再用第二個 `Get Contents of URL` POST 到 `/action`。
4. 第二個 JSON body 為：

```json
{
  "action": "confirm_shutdown",
  "confirmation_token": "上一個回應的 confirmation_token"
}
```

5. 朗讀第二個回應的 `message`。

Token 是一次性、隨機、60 秒內有效；錯誤、過期、缺失或重複使用都不能關機。Shortcut Cancel 就停止，不送第二次請求。

## 6. 可說的指令

### 應用程式

```text
開啟 Discord
打開 Chrome
啟動 Photoshop
open Discord
launch Spotify
關閉 Discord
退出 Chrome
close Discord
強制關閉 Discord
force close Discord
```

普通的「關閉」只會找目前互動式 Session 中有可靠 process identity 的 top-level window，先送 `WM_CLOSE`，不會自動 `taskkill /f`。只有明確說「強制」或 `force` 才進入高風險 force-close；若無法可靠判定 process，會拒絕操作。

### Windows 內建工具

```text
記事本       / Notepad
計算機       / Calculator
工作管理員   / Task Manager
檔案總管     / File Explorer
設定         / Settings
控制台       / Control Panel
終端機       / Windows Terminal
命令提示字元 / Command Prompt
PowerShell
剪取工具     / Snipping Tool
小畫家       / Paint
裝置管理員   / Device Manager
服務         / Services
事件檢視器   / Event Viewer
磁碟管理     / Disk Management
```

### 音量與系統

```text
音量大一點 / volume up
音量小一點 / volume down
靜音 / mute
取消靜音 / unmute
鎖定電腦 / lock PC
重新掃描程式 / refresh apps
關機
```

播放控制固定走 Spotify Web API；Windows 系統 media key 只保留給音量 fallback，避免遠端請求繞過 Spotify 選擇其他播放器。音量有 `pycaw` 時使用 Windows master volume，否則使用系統按鍵 fallback，因此 `unmute` 在 fallback 模式會標成 best-effort。

## 7. Spotify 指定歌曲播放

目前 V1 的音樂控制固定使用 Spotify Web API，不再由 Windows 系統 media key 猜測目前是哪個播放器。需要：

- Spotify Premium 帳戶。
- Spotify Developer Dashboard 的 Client ID。
- 將 `http://127.0.0.1:8000/spotify/callback` 加入 Spotify App 的 Redirect URI。
- 在 `.env` 設定 `SPOTIFY_CLIENT_ID`；可選填 `SPOTIFY_DEVICE_NAME` 指定 Spotify Connect 裝置名稱。

啟動 Agent 後，用本機 PowerShell 取得授權網址：

```powershell
$key = (Get-Content .env | Where-Object { $_ -match '^SIRI_AGENT_API_KEY=' }) -replace '^SIRI_AGENT_API_KEY=', ''
$auth = Invoke-RestMethod http://127.0.0.1:8000/spotify/auth/start -Headers @{ 'X-API-Key' = $key }
Start-Process $auth.authorization_url
```

完成 Spotify 授權後，Token 只會保存在 Windows 的 `runtime\spotify_token.json`，不會傳給 iPhone、Siri Shortcut、API 回應或 log。可用下列指令查看不含 Token 的狀態：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/spotify/status -Headers @{ 'X-API-Key' = $key }
```

可說：

```text
播放
播放晴天
播放周杰倫的晴天
播放周杰倫的晴天 (葉惠美)
Play Blinding Lights by The Weeknd
暫停
下一首
上一首
```

歌曲名稱、歌手與括號中的專輯/版本提示只會作為 Spotify Search API 的查詢文字；只有經 Spotify 回應驗證過的曲目才會進入播放。搜尋結果不明確時 Agent 會要求補充歌手或專輯，不會隨機播放，也不接受客戶端直接傳入 Spotify URI。

## 8. Application Catalog

Agent 啟動時會建立本機 catalog，並快取到 `runtime\apps.json`；每次 Siri 指令不會掃整顆硬碟。它不會遞迴掃 `C:\`，也不會把 Downloads、Temp、Cache 或瀏覽器下載的 EXE 自動信任。

主要來源：

- Current User / All Users Start Menu `.lnk`
- Registry App Paths
- Windows AppsFolder / packaged app AUMID
- 固定的 Windows system app mapping
- 受本機 `manual_apps.yaml` 明確設定的 portable `.exe/.com`
- 少量已知名稱的 PATH 應用程式
- Installed Programs / Uninstall Registry 僅作 metadata，不可直接啟動

查看 catalog（需要 API key）：

```powershell
$key = (Get-Content .env | Where-Object { $_ -match '^SIRI_AGENT_API_KEY=' }) -replace '^SIRI_AGENT_API_KEY=', ''
Invoke-RestMethod http://127.0.0.1:8000/apps -Headers @{ 'X-API-Key' = $key }
```

重新掃描：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/apps/refresh -Headers @{ 'X-API-Key' = $key }
```

或直接說「重新掃描程式」。完整 path、AUMID 和 shortcut path 只留在 Windows 本機，不回傳給 iPhone。

### 自訂 alias

已安裝應用程式的 aliases 可在 `config\app_aliases.yaml` 設定；portable app 則在 `manual_apps.yaml` 的 aliases 設定。例：

```yaml
application_aliases:
  google chrome:
    - 瀏覽器
  discord:
    - 語音
  adobe photoshop 2026:
    - PS
```

也可以把 portable app 明確列入：

```yaml
manual_apps:
  - name: OBS Studio
    path: C:\Tools\obs-studio\bin\64bit\obs64.exe
    aliases:
      - 錄影
      - OBS
```

只接受存在的 `.exe` 或 `.com` 檔案。這個檔案只能在 Windows 本機修改；遠端 API 沒有新增、修改、刪除 executable path 的能力。修改後請說「重新掃描程式」。

### 自訂網站

在 `config\websites.yaml` 本機加入固定的 `id`、顯示名稱、aliases 和 `https://` URL。遠端只可選擇 allowlist 中的網站，不可傳入任意 URL。

## 9. API 摘要

除 `/health` 外，控制 API 都需要 `X-API-Key`。統一回應包含 `success`、`status`、`action`、`message`、`candidates`、`confirmation_required`、`error_code`、`data`。

```text
GET  /health       不需 API key，極簡狀態
GET  /info         需要 API key，版本、session、network/firewall diagnostics
GET  /apps         需要 API key，安全的 app public view
POST /apps/search  {"query":"photoshop"}
POST /apps/refresh
POST /action       需要封閉 Action enum
POST /command      {"text":"開啟 Discord"}
```

`/action` 只接受已知 action 和 app name / app ID；不接受 `path`、`executable`、`command`、`arguments`、`shell`、`powershell`、`url` 或 Python code。所有啟動都遵守：

```text
Siri text -> safe parser -> closed action -> catalog match -> verified LaunchSpec -> Windows adapter
```

## 10. 安全邊界

- 只綁定 LAN server 的 `0.0.0.0:8000`，實際進入仍受 private-network middleware 和 Windows Private Firewall 限制。
- API key 使用常數時間比較，不寫入 log。
- Rate limit 以 client IP 計算，避免 LAN 裝置瘋狂呼叫。
- Shutdown token 只存 hash，不記錄完整 token；使用一次即失效。
- 自然語言 parser 只能產生預先定義的 Action enum。
- 不使用 `shell=True`；使用者文字不直接進 subprocess、PowerShell 或 CMD。
- PowerShell 僅用於開發者固定的本機 discovery / diagnostics command。
- 不提供 remote shell、remote PowerShell、任意檔案操作或 arbitrary URL。

## 11. 測試與維護

安裝依賴後：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit -q
.\.venv\Scripts\python.exe -m pytest tests\integration_windows -q
.\.venv\Scripts\python.exe -m pytest -q
```

`tests\unit` 全部 mock Windows calls，不能關機、鎖定、開 Photoshop、調音量或殺 process。`tests\integration_windows` 只做真實 Windows 的唯讀探測：built-in app、Start Menu / Registry / AppsFolder discovery、interactive session 和 network profile；不會真的 shutdown、lock 或 force kill 使用者程式。

本機 diagnostics / cache / logs：

```text
runtime\apps.json
logs\agent.log
```

這些內容已排除在 Git 外。不要提交 `.env`。

## 12. 卸載

預設保留程式碼、設定、`.env` 和使用者資料：

```powershell
.\scripts\uninstall.ps1
```

若要同時清除 cache/logs，明確使用：

```powershell
.\scripts\uninstall.ps1 -RemoveRuntimeData
```

Firewall、Task Scheduler、runtime、logs 可恢復或重新建立；不要在不確認的情況下刪除 `D:\ai`，因為該資料夾可能還有其他專案。
