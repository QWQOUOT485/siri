# Windows Siri Agent Architecture

How should this system be designed? Preserve the v2 architecture completely.

## Layer Architecture

```text
API Layer (FastAPI routes)
  → validation, serialization, call services; no direct Windows operations
    ↓
Infrastructure (auth / rate_limit / config / logging)
  → cross-cutting concerns, not domain core logic
    ↓
Service Layer (orchestration)
  → CommandService → Parser → Matcher → AppService → Adapter
    ↓
Domain Layer (pure data models and rules, no Windows dependency)
  → actions.py / app_models.py / matching.py
  → This layer can be fully unit tested without real Windows
    ↓
Windows Adapter Layer (only place touching Windows API)
  → discovery / launcher / process / media / volume / system / firewall
  → Only operates in current logged-in user's interactive session
  → Only this layer (and some integration tests) needs real Windows verification
    ↓
Current logged-in Interactive User Session
    ↓
Windows System
```

**Key modification:** Agent itself must run in current user's interactive desktop session (Task Scheduler At log on, not SYSTEM / not regular Windows Service).

## Layer Responsibilities

- **API Layer**: validation, serialization, call services. No direct Windows operations.
- **Infrastructure**: auth (constant-time compare, no log key), rate_limit (middleware, not domain), config (.env, allowed_networks, websites, manual_apps), logging (no secrets).
- **Service Layer**: orchestration. CommandService → Parser → Matcher → AppService → Adapter. ShutdownService for token lifecycle. AppService for catalog queries, refresh, AppEntry→LaunchSpec.
- **Domain Layer**: Pure data models, no Windows import. Actions enum, AppEntry/LaunchSpec/ProcessSpec models, matching logic (normalize + alias + token/prefix + fuzzy + confidence).
- **Windows Adapter Layer**: Only place touching Windows API. All operate targeting current interactive user session. Abstract interfaces for test injection.

## Dependency Inversion

Domain has no Windows dependency. Windows Adapters implement abstract interfaces defined in `base.py`. Services orchestrate between Domain and Adapters.

## Key Data Models

- **AppEntry**: display_name, normalized_name, aliases, launch_method, launch_target, executable path (from trusted sources), process info, source, app type, AUMID, shortcut path, confidence, launch_source (Trusted/Metadata-only), launch_confidence, metadata_confidence.
- **LaunchSpec**: Built by Catalog from AppEntry. Windows Adapter only accepts this, not arbitrary strings.
- **ProcessSpec**: Process hints for Running Application Resolver.
- **stable app_id**: Matcher uses app_id after finding app, avoids repeated name matching.

## Application Discovery Source Classification

**A. Trusted Launch Sources** (can be used as launch targets):
- Start Menu .lnk (Current User / All Users)
- Registry App Paths
- Windows AppsFolder
- UWP / packaged app AUMID
- Windows system_apps mapping (well-known system targets)
- User's local manual_apps config

**B. Metadata-only Sources** (supplementary info only, NOT launch targets):
- Installed Programs Registry / Uninstall Registry
- Publisher / Version / Install Location metadata
- Other sources without clear launch contract

## Catalog

In-memory catalog using stable app_id. Bridges services and adapters.

## Matcher

normalize + alias + token/prefix + fuzzy + confidence ranking. Search priority: exact alias → exact normalized → strong prefix/token → fuzzy → ambiguous candidates.

## Running Application Resolver

Not just 'app name → process name → kill'. Flow:
1. Catalog process hints / executable identity
2. Current logged-in user session
3. Top-level windows / associated process tree
4. Graceful Close (WM_CLOSE)
5. Wait reasonable timeout
6. Check result
7. If still exists, report failure (don't force close)

Force Close is separate explicit operation.

## Firewall Responsibility

- Runtime: inspect only (`inspect_network_profile()`, `inspect_firewall_rule()`)
- `setup.ps1`: create/remove rules only with explicit user consent
- Private Profile only
- Never auto-modify network profile, Router, NAT, Port Forwarding, UPnP

## Rate Limiter Placement

Belongs in API/infrastructure layer (middleware), not domain/service logic.

## system_apps Mapping

Windows built-in tools (Task Manager, Settings, Calculator, etc.) maintained as well-known system targets. Trusted Launch Source. Not dependent on general Discovery. Not 'hardcoding all apps'.

## Media Control

Best-effort. Acts on current active media session. Cannot guarantee single-app control. V1 has no specific app selection logic. README must explain.

## Directory Structure (v2)

```text
windows-siri-agent/
├── app/
│   ├── main.py                    # FastAPI entrypoint；啟動時檢查 interactive session
│   ├── infrastructure/
│   │   ├── auth.py                # API key 驗證，常數時間比對，不 log key
│   │   ├── rate_limit.py          # 移出 domain，改放 infrastructure（middleware）
│   │   ├── config.py              # .env、allowed_networks、websites、manual_apps 讀取
│   │   └── logging.py             # 不記錄 secret / 完整 shutdown token
│   │
│   ├── api/
│   │   ├── routes_health.py       # /health：不需 API Key，內容極簡（ok/version/uptime）
│   │   ├── routes_apps.py         # /apps, /apps/search, /apps/refresh：需要 auth
│   │   ├── routes_action.py       # /action：需要 auth
│   │   └── routes_command.py      # /command：需要 auth
│   │
│   ├── domain/                    # 純資料模型與規則，無 Windows import
│   │   ├── actions.py             # 封閉 Action enum + ValidatedAction model（安全收斂點）
│   │   ├── app_models.py          # AppEntry / LaunchSpec / ProcessSpec 資料模型
│   │   └── matching.py            # normalize + alias + token/prefix + fuzzy + confidence 排序
│   │
│   ├── services/                  # orchestration，串 domain 與 adapters
│   │   ├── command_service.py     # Parser → Matcher → AppService → Adapter
│   │   ├── app_service.py         # catalog 查詢、refresh、AppEntry → LaunchSpec 建立
│   │   └── shutdown_service.py    # shutdown token 產生 / 驗證 / 過期 / 一次性
│   │
│   ├── adapters/
│   │   └── windows/               # 唯一碰 Windows API 的地方，皆以 interactive session 為目標
│   │       ├── base.py            # abstract interface，方便注入 Fake 實作做測試
│   │       ├── discovery.py       # 區分 Trusted Launch Source / Metadata-only Source
│   │       ├── launcher.py        # 只接受 Catalog 建立的 LaunchSpec，不接受任意字串
│   │       ├── process.py         # Running Application Resolver：top-level window→graceful close
│   │       ├── media.py           # media key 模擬，best-effort
│   │       ├── volume.py          # pycaw wrapper，操作 master volume
│   │       ├── system.py          # lock / shutdown（session-aware）
│   │       └── firewall.py        # inspect_* 唯讀；create/remove 規則僅供 setup.ps1 經同意呼叫
│   │
│   └── catalog.py                 # in-memory catalog，內部使用穩定 app_id，串 service 與 adapters
│
├── tests/
│   ├── unit/                      # 全部 mock 化，可在任何環境（含本容器）執行
│   │   ├── test_command_parser.py
│   │   ├── test_matching.py
│   │   ├── test_shutdown_service.py
│   │   ├── test_action_schema_security.py   # 注入攻擊測試
│   │   ├── test_api_auth.py
│   │   ├── test_process_resolver_mocked.py
│   │   └── test_adapters_mocked.py
│   └── integration_windows/       # 只能在真實 Windows 執行，禁止破壞性操作
│       ├── test_discovery_real.py           # 找 Windows built-in app、.lnk 解析
│       ├── test_app_paths_real.py
│       ├── test_session_detection_real.py   # interactive session 偵測
│       └── test_network_profile_real.py
│
├── scripts/
│   ├── setup.ps1                  # venv、dependency、.env、詢問是否建立 firewall 規則、
│   │                               # 詢問是否啟用 Task Scheduler「At log on」自動啟動（唯一方案）
│   ├── start.bat                  # 以目前使用者手動啟動（測試 / 除錯用）
│   └── uninstall.ps1              # 移除 firewall 規則、Task Scheduler 項目
│
├── config/
│   ├── websites.yaml
│   ├── manual_apps.yaml           # 僅本機可改，遠端 API 不可新增/修改/刪除
│   └── allowed_networks.yaml
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Key Design Decisions (v2)

1. **Interactive User Session 是架構的第一優先前提**：`main.py` 啟動時即偵測目前是否執行在 interactive user session，若否，log warning 並在 `/info` 標示 GUI launch 可能不正常。自動啟動一律採 Task Scheduler `At log on`（interactive user 模式），不採一般 Windows Service。
2. **Discovery 輸出區分 `launch_source`（Trusted / Metadata-only）**：`AppEntry` 除了 display_name、aliases、confidence 之外，明確標記資料是否來自可信啟動來源（Start Menu `.lnk`、App Paths、AppsFolder/AUMID、system_apps mapping、manual_apps）或僅為補充 metadata（Uninstall Registry 等）。只有 Trusted Launch Source 可以進一步生成 `LaunchSpec`。
3. **啟動資料流逐層收斂，Adapter 不信任任何遠端字串**：`Command Parser → ValidatedAction → Matcher → Trusted AppEntry → LaunchSpec → Windows Launcher Adapter`。`launcher.py` 只接受 `app_service.py` 建立好的 `LaunchSpec`，即使上層已驗證，Adapter 內部仍再次確認 path 存在、來源合法。
4. **Process 關閉改為 Running Application Resolver**：`process.py` 先用 Catalog 的 process hints 在目前 session 內找出相關 process/top-level window，發送 graceful close，等待 timeout 後再確認；找不到可靠對應時回報「無法安全判斷應關閉哪個程序」，不亂殺。`force_close_app` 是獨立、明確、higher-risk 的操作，不會被自然語言「關閉 X」自動觸發。
5. **Firewall 職責明確分離**：`firewall.py` 執行期只提供 `inspect_network_profile()` / `inspect_firewall_rule()`（唯讀）；`create_private_rule()` / `remove_agent_rule()` 只能由 `setup.ps1` 在使用者明確同意後呼叫，且規則只開放 Agent port、只在 Private Profile。
6. **Rate limiter 放在 infrastructure，不放 domain**：`rate_limit.py` 作為 middleware，處理 client IP / request frequency，與 domain 的商業規則（parser、matcher、shutdown flow）分離。
7. **Catalog 使用穩定 `app_id`**：Matcher 找到程式後，後續流程（`/apps/search` 回傳、`/action` 執行）盡量透過 `app_id` 傳遞，避免重複用 display name 比對造成同名程式、大小寫、fuzzy match 不一致的問題。
8. **Windows 內建工具走 `system_apps` mapping**：Task Manager、Settings、Calculator 等視為 Trusted Launch Source 的固定入口，不依賴一般 Discovery，也不算「把所有應用程式寫死」。
9. **測試分兩類**：`tests/unit/`（mock 化，可在任何環境含本容器完整執行）與 `tests/integration_windows/`（只能在真實 Windows 執行，且明確禁止 shutdown / lock / force kill 等破壞性操作，只做唯讀或安全的探測）。
10. **Media control 維持 best-effort 標記**：沿用 v1 設計，README 明確說明系統層 media control 作用於目前 active media session，無法保證只控制單一 app；第一版不做特定 app 選擇邏輯。

See also [SECURITY.md](SECURITY.md) and [WINDOWS.md](WINDOWS.md).
