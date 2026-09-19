# Windows Siri Agent 產品規格書 (Product Specification)

本文件定義 Windows Siri Agent 的產品規格與功能需求。技術實作與架構細節請參見 [Architecture](ARCHITECTURE.md)。

## 1. 產品目標與使用場景 (Goal & Scenario)
- **目標**：透過 iPhone 的 Siri 來語音控制 Windows 電腦，主要用於開啟程式、控制媒體、系統操作等。
- **使用場景**：僅限家庭或單一建築物內的區域網路 (LAN) 使用（例如 1F 到 4F 的 Wi-Fi 環境）。不支援透過網際網路遠端控制。
- **最終使用體驗**：
  1. 使用者在任何樓層對 iPhone 說：「嘿 Siri，控制電腦」。
  2. Siri 回應：「請說。」
  3. 使用者說出指令，例如：「開 Discord」或「音量大一點」。
  4. Windows 電腦執行對應操作，Siri 語音回報結果：「已開啟 Discord」或「音量已提高」。
  5. 針對危險操作（如關機），Siri 會進行二次確認，確保安全。

## 2. 核心功能與指令 (Core Features & Commands)

本產品保留基於規則的指令解析器 (Rule-based Command Parser) 作為第一層，並允許在 Windows 本機加入小型 Local LLM 作為 **fallback 語意解析器**。Local LLM 僅可將自然語言收斂成封閉 schema，不得直接控制 Windows、Spotify、shell、URL、executable path 或其他執行目標。V1 不使用雲端付費 LLM API；高風險操作（shutdown / force-close / firewall / system administration）永久維持 deterministic-only。詳細設計見 `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md`。

### 2.1 應用程式操作 (Application Control)
- **開啟程式 (open_app)**：安全啟動應用程式。
- **關閉程式 (close_app)**：優先嘗試正常關閉視窗 (graceful close)，若無法關閉則回報，不會一開始就強制結束 (taskkill /f)。
- **強制關閉 (force_close_app)**：必須使用明確的強制關鍵字才會觸發，詳見 [Security Model](SECURITY.md#force-close-safety)。
  - 中文觸發詞：強制關閉、強制結束、強制退出、強制終止、直接砍掉 + 程式名稱。
  - 英文觸發詞：force close, force quit, force kill, forcefully close + 程式名稱。
- **重新掃描程式**：手動更新應用程式清單 `/apps/refresh`，無須重啟 Agent。

### 2.2 內建系統工具支援 (Built-in Tools)
僅支援「開啟」下列工具，絕對不會將使用者輸入當作 Shell 指令執行：
工作管理員 (Task Manager)、檔案總管 (File Explorer)、設定 (Settings)、控制台 (Control Panel)、計算機 (Calculator)、記事本 (Notepad)、Windows Terminal、命令提示字元 (Command Prompt)、PowerShell、剪取工具 (Snipping Tool)、小畫家 (Paint)、裝置管理員 (Device Manager)、服務 (Services)、事件檢視器 (Event Viewer)、磁碟管理 (Disk Management)。

### 2.3 Spotify 音樂與音量控制 (Spotify Music & Volume)

第一版指定歌曲播放只整合 **Spotify**；不再詢問 YouTube Music / Apple Music / Spotify 三選一。

- **Spotify 基本播放控制**：
  - 「播放」/「播放音樂」/ `Play`：恢復 Spotify 目前播放。
  - 「暫停」/「暫停音樂」/ `Pause`：暫停 Spotify。
  - 「下一首歌」/ `Next track`：Spotify 下一首歌曲。
  - 「上一首歌」/ `Previous track`：Spotify 上一首歌曲。
- **指定歌曲播放 (`spotify_play_track`)**：
  - 「播放晴天」
  - 「播放周杰倫的晴天」
  - 「播放周杰倫的晴天 (葉惠美)」：可用專輯/版本提示消除同名歌曲歧義
  - 「Spotify 播放周杰倫的晴天」
  - `Play Blinding Lights by The Weeknd`
- Parser 將自然語言收斂成結構化資料，例如：`action = spotify_play_track`、`track = 晴天`、`artist = 周杰倫`、`album = 葉惠美`（artist/album 可選）。
- Agent 使用 Spotify Web API 搜尋 Catalog，取得可信的 Spotify track URI/ID 後再要求 Spotify 播放。
- 使用者輸入的歌名/歌手/專輯提示只可作為 Spotify 搜尋文字，不可變成 shell、CMD、PowerShell、exe path、command-line arguments 或 arbitrary URL。
- 如果搜尋結果明顯歧義或信心不足，不得隨機播放；回傳可朗讀訊息，要求使用者補充歌手或更完整歌名。
- Spotify 播放目標優先使用本機設定的 Windows Spotify Connect 裝置；若目前沒有可用裝置，回傳清楚錯誤，或安全地透過 Trusted AppEntry 開啟 Spotify Desktop 後再重試。
- Spotify OAuth / token / scopes / device selection 詳見 [Spotify Integration](SPOTIFY.md)。
- **音量控制**：Windows 主音量仍由既有 volume adapter 控制，單次調整限制步數 (steps 1-10)。支援 `volume_up`, `volume_down`, `mute`, `unmute`, `toggle_mute`。
  - 常用語句：音量大一點、音量增加、聲音大一點、調大音量、音量小一點、音量降低、聲音小一點、調小音量、靜音、取消靜音、解除靜音 / volume up, volume down, mute, unmute。

### 2.4 系統控制 (System Control)
- **鎖定電腦 (LockWorkStation)**：立即執行鎖定。
  - 常用語句：鎖定、鎖定電腦、鎖電腦 / lock PC。
- **關機 (Shutdown)**：嚴格的兩階段確認機制。
  - 常用語句：關機、關閉電腦 / shutdown。
  - 流程：Agent 產生一次性加密確認 Token -> Siri 提示確認 -> 使用者確認後才執行。詳見 [Security Model](SECURITY.md#shutdown-two-step-confirmation)。

### 2.5 網站開啟 (Website Control)
- **開啟網站 (open_website)**：透過 Windows 系統預設瀏覽器（非寫死 Chrome）開啟預先設定的網站。
- **預設支援清單**：YouTube, YouTube Music, Spotify Web, Netflix, Google, ChatGPT, GitHub。
- **安全限制**：不接受遠端傳入任意 URL，僅能透過設定檔擴充。

## 3. 應用程式自動發現機制 (Application Discovery)

Agent 會自動找出 Windows 電腦上已安裝的應用程式，建立「應用程式目錄 (Application Catalog)」，免除手動設定的麻煩。

- **資料來源**：採用多種可靠來源，詳見 [Architecture](ARCHITECTURE.md)。
- **安全限制**：絕對不會掃描整顆硬碟，也不會將 Downloads / Temp / Cache 目錄下的執行檔視為信任程式。
- **可攜式程式 (Portable Apps)**：支援透過本機設定檔 `manual_apps` 手動加入，詳見 [Security Model](SECURITY.md#manual-apps-security)。
- **App 快取 (Cache)**：目錄會快取於本機 JSON，啟動時載入，避免每次呼叫 Siri 都重新掃描。支援啟動時自動更新、定時更新及手動更新。

### 3.1 應用程式目錄資料結構 (Catalog Data Structure)
每筆應用程式資料包含：`display_name`, `normalized_name`, `aliases`, `launch_method`, `launch_target`, `executable path` (僅限信任來源), `process information`, `source`, `app type`, `confidence`，及選用的 `AUMID` 與 `shortcut path`。
> **注意**：`launch_target` 等內部啟動資訊，絕不允許由遠端 API 直接設定。

### 3.2 名稱辨識與模糊搜尋 (Name Recognition & Search)
- **正規化 (Normalization)**：支援大小寫不分、去除空白、標點符號與連字號處理。
- **搜尋優先順序**：精確別名 (Exact alias) -> 精確正規化名稱 -> 強字首/權杖 (Strong prefix/token) -> 模糊搜尋 (Fuzzy match) -> 歧義候選 (Ambiguous candidates)。
- **模糊搜尋防呆**：當信心指數不足，或同時存在多個相似程式（例如 Visual Studio 與 Visual Studio Code）時，Agent 不會隨機挑選，而是回傳所有候選名單，交由 Siri 詢問使用者。

### 3.3 中文與自訂別名 (Aliases)
內建常見 Windows 程式的中文別名，例如：
- 工作管理員 -> Task Manager
- 記事本 -> Notepad
- 計算機 / 小算盤 -> Calculator
- 檔案總管 / 文件總管 -> File Explorer
- 終端機 -> Windows Terminal
- 命令提示字元 -> Command Prompt
- PowerShell -> Windows PowerShell

使用者可透過目前的本機設定來源自訂別名：一般 runtime 設定放在 `.env`，應用程式與網站清單放在 `config/manual_apps.yaml`、`config/websites.yaml` 等專用 YAML；不使用單一 `config.yaml` / `config.toml` 作為目前實作的設定入口。

## 4. 系統配置與部署 (Configuration & Deployment)

- **設定檔 (Configuration)**：runtime 設定使用 `.env`；清單型設定使用 `config/*.yaml`（例如 `allowed_networks.yaml`、`websites.yaml`、`manual_apps.yaml`）。可設定 Port、Bind address、Allowed networks、Volume step、Shutdown confirmation timeout、Website/App aliases 等，無須更動 Python 原始碼。
- **相依性 (Dependencies)**：最小化依賴，優先使用 Python 內建函式庫與 Windows API。核心依賴僅限 FastAPI, uvicorn, pydantic, python-dotenv。
- **安裝與啟動**：提供自動化腳本（`setup.ps1` 處理 venv 與依賴安裝、`start.bat` 啟動、自動建立 `requirements.txt` / `pyproject.toml` 等）。
- **版本資訊**：內含 `VERSION` 檔案，可透過 API `GET /info` 查詢。
- **.gitignore 規範**：嚴格排除 `.env`、API keys、logs、runtime cache、venv、`__pycache__` 等敏感與暫存檔案。

## 5. 使用者介面與回饋 (UI & Feedback)

- **系統匣圖示 (System Tray)** (選用)：提供 Agent Running、Copy Address、Show IP、Refresh Apps、List Apps、Open Config、Open Logs、Open README、Restart Agent、Stop Agent 等功能。
- **狀態網頁 (Status UI)** (選用)：提供簡易的 Web 介面顯示系統狀態 (Agent Online, PC Name, IP, App count, API status 等)。
- **Siri 回應訊息**：
  - **成功**：「已開啟 Discord」、「音量已提高」。
  - **錯誤**：「找不到 Discord」。
  - **歧義**：「找到兩個可能的程式：Visual Studio 和 Visual Studio Code，請說完整名稱。」
- **錯誤處理**：定義清楚的錯誤代碼與處理機制。絕對不允許將 Stack Trace 傳送至 iPhone，詳見 [Security Model](SECURITY.md#stack-trace-security)。
- **日誌記錄 (Logging)**：詳見 [Security Model](SECURITY.md#logging-security)。
- **診斷功能 (Diagnostics)**：提供應用程式探索的本機診斷日誌，方便排查未找到特定程式的原因。

## 6. 產品演進與架構擴充 (Future Extensibility)
第一版架構仍以安全與核心體驗為優先，但 Local LLM 語意 fallback 已允許納入 V1，前提是先通過獨立模型 PoC、schema/grounding/security 測試與實機驗收。AI 不是執行引擎，現有 deterministic resolver 與 trusted-object execution boundary 不得被取代。未來仍可擴充智慧家庭 (Smart Home) 及更進階的自動化控制，但任何高風險 AI 執行能力都需要另行安全審查。

## 7. 開發原則
- 優先順序：安全 > 能正常使用 > Siri Shortcut 簡單 > 自動辨識已安裝程式 > LAN 跨 Wi-Fi/subnet > 穩定 > 容易安裝 > 容易維護 > UI 漂亮。
- 善用成熟且安全的 GitHub OSS 專案，避免重複造輪子。
