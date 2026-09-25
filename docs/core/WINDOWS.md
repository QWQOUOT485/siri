# Windows Platform Constraints

This document outlines the Windows platform constraints and specifications for the Agent.

### Interactive Desktop Session (#101, #109)
- Agent MUST run in current logged-in user's interactive desktop session
- Cannot use regular Windows Service as primary deployment
- GUI applications, media control, user profile must target current interactive user session
- If Agent detects it's NOT in interactive session: log warning, mark in `/info` diagnostics that GUI launch may not work normally. Don't pretend everything is fine.
- All Windows Adapter operations (app discovery, app launch, process resolve, media control, reading user profile/AppData/Start Menu/UWP Apps) must target current interactive user session
- Avoid using SYSTEM account or other session's processes

### Task Scheduler (#102)
- First version auto-start: Task Scheduler ONLY
- Trigger: At log on
- Target: current logged-in user
- Mode: Run only when user is logged on (interactive user, NOT SYSTEM)
- Do NOT use Startup Folder (`shell:startup`) in v1 — confirmed to only do Task Scheduler, avoid installation flow confusion
- `setup.ps1` creates Task Scheduler item, asks user whether to enable
- `uninstall.ps1` removes the scheduled task
- If detected running as SYSTEM or inappropriate service context: log and README clearly state GUI application launch may not work normally
- Future: Windows Service only as auxiliary component (e.g. background monitoring), never for direct GUI application launch

### Setup Script — setup.ps1 (#57)
1. Check OS is Windows
2. Check Python installed
3. Check required Python version
4. Create `.venv`
5. Install dependencies
6. Create config
7. Generate API key
8. Create runtime folders
9. Build application catalog
10. Run basic self-test
11. Ask whether to create Windows Firewall Private rule
12. Display Windows LAN IP
13. Display health URL
14. Tell user next steps

If no Python: give understandable installation instructions. Optionally auto-install via winget (but don't silently make major system changes).

### Start Script — start.bat (#59)
- Double-click to start Agent
- Activate `.venv`
- Start Server
- Display simple status

### Stop (#60)
- System tray: right-click Stop Agent (if available)
- `start.bat` window: Ctrl+C for normal stop

### Auto-Start Installation (#61)
- `install-startup.ps1`: let user choose whether to auto-start Agent on Windows login
- Don't force auto-start during setup
- Provide `uninstall-startup.ps1`

### Uninstall
- `uninstall.ps1`: remove firewall rules, Task Scheduler items

### Firewall Handling (#25, #26, #58, #107)
- `setup.ps1` asks: create Windows Firewall rule?
- If user agrees: create rule
- Rule name: e.g. 'Siri Windows Agent'
- TCP port (e.g. 8000) only
- Private profile ONLY, never Public
- If current profile is Public: warn, don't silently change
- Consider RFC1918 private ranges for multi-subnet (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- `allowed_networks` in config file
- Runtime Agent: only inspect, never modify firewall
- See [Security Model](SECURITY.md#firewall-security)

### Application Discovery Sources (#5, #103, #106)
**A. Trusted Launch Sources:**
- Current User Start Menu shortcuts (`.lnk`)
- All Users Start Menu shortcuts (`.lnk`)
- Registry App Paths
- Windows AppsFolder
- UWP / AUMID
- `system_apps` mapping (Windows built-in tools)
- `manual_apps` from local config

**B. Metadata-only Sources:**
- Installed Programs Registry / Uninstall Registry
- Publisher / Version / Install Location
- Other sources without clear launch contract

Metadata-only sources CANNOT become launch targets.

Can use Windows API, winreg, COM, or other reasonable methods.
Internal fixed PowerShell commands OK for discovery. NEVER put iPhone text into PowerShell.

### Don't Scan Entire Hard Drive (#6)
- No recursive `C:\` scan
- Downloads, Temp, Cache, Browser downloads exe NOT auto-trusted

### system_apps Mapping (#106)
Maintain well-known system targets: Task Manager (taskmgr), File Explorer (explorer), Settings (ms-settings:), Control Panel, Calculator, Notepad, Windows Terminal, Command Prompt, PowerShell, Snipping Tool, Paint, Device Manager, Services, Event Viewer, Disk Management.
Trusted Launch Source. Not dependent on general Discovery.

### Manual Apps (#87, #88)
- `manual_apps` config for portable applications
- Local-only configuration (name, path, aliases)
- On startup validate: path exists, is file, reasonable extension, user explicitly configured
- Remote API cannot add/modify/delete
- See [Security Model](SECURITY.md#manual-apps-security)

### Process Resolver (#105, #15)
- app → process executable mapping in Catalog
- Don't kill wrong processes based on name similarity
- Use current interactive session + process hints + executable identity + top-level window
- Graceful close (`WM_CLOSE`) → timeout → check result
- If can't reliably identify: don't force close, report to user
- Force close is separate explicit operation
- See [Architecture](ARCHITECTURE.md#running-application-resolver)

### Media Control (#19)
- Windows media key / multimedia controls
- Best-effort across Spotify, YouTube Music, Chrome, Edge, VLC
- Acts on current active media session
- Cannot guarantee single-app control
- Research Windows Global System Media Transport Controls

### Volume Control (#20)
- Windows system master volume
- Steps limited 1-10
- No very large values

### Lock (#21)
- `LockWorkStation`, immediate execution

### Shutdown (#22)
- Two-step confirmation with crypto token
- See [Security Model](SECURITY.md#shutdown-two-step-confirmation)

### Local Logs (#72)
- Detailed logs on Windows local machine
- Stack traces local only, never sent to iPhone

### Runtime Cache (#55)
- Application catalog cached as local JSON

### Interactive Session Diagnostics (#101)
- Agent startup: detect interactive session
- If not interactive: warning log + `/info` diagnostic flag

### App Discovery Diagnostics (#89)
- Local log/diagnostics file showing: sources scanned, apps found, apps ignored, reasons
- Not sent to iPhone
