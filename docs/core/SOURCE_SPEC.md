請直接幫我建立一個完整、可執行、可安裝、適合一般使用者使用的 Windows 專案。

不要只回答我「怎麼做」。

不要只給範例程式碼。

如果你目前是在可以直接修改 repository / workspace 的 Codex 環境，請直接：

* 建立所有需要的檔案
* 寫完整程式
* 安裝需要的 dependencies
* 執行測試
* 修正錯誤
* 驗證 Server 可以正常啟動
* 寫好 README
* 做好安裝腳本
* 做好啟動腳本

我不是工程師，所以最後要讓我可以按照很簡單的步驟使用。

\---

\# 0. 可以先查 GitHub / 官方文件，不要浪費 token 重造輪子

在開始自己實作之前：

可以先搜尋 GitHub 上成熟的開源專案、Python libraries、Windows automation libraries、FastAPI 範例、Windows application discovery 方法、Windows media key 控制方案等。

優先尋找：

* 成熟
* 有維護
* license 清楚
* 安全
* 容易整合
* Windows 支援良好

的現成開源方案。

如果 GitHub 已經有成熟、安全、簡單的實作方式，可以直接參考或使用 dependency，不需要浪費大量 token 從零重新發明。

也可以查：

* Microsoft 官方文件
* Python 官方文件
* FastAPI 官方文件
* Windows API 文件
* Apple Shortcuts 相關可靠文件

但是：

不要直接整份複製來源不明的程式碼。

不要引入奇怪或低信任度 dependency。

不要使用多年沒維護又有更好替代方案的 package。

不要使用 license 不相容的程式碼。

不要因為 GitHub 某段程式碼可以跑，就直接認為它安全。

如果有多種方案，優先選：

安全

穩定

程式碼少

dependency 少

Windows 原生能力優先

容易維護

\---

\# 1. 我的最終目標

我要用 iPhone Siri 控制我的 Windows 電腦。

使用場景只在家裡 / 同一棟建築物內。

大約是：

1. 樓到 4 樓都有 Wi-Fi。

不同樓層可能：

* Wi-Fi 名稱不同
* Access Point 不同
* Mesh 節點不同
* IP subnet 不同

但是全部都是我自己的內部網路。

只要不同 subnet 之間有 routing，可以互相存取即可。

我不需要從外面的 Internet 控制電腦。

\---

\# 2. 不使用任何公網方案

不要使用：

* Tailscale
* Tailscale Funnel
* Cloudflare Tunnel
* ngrok
* 公網 VPS
* Router Port Forwarding
* UPnP Port Mapping
* DDNS
* 公開 API
* 任何需要把 Windows Agent 暴露到 Internet 的方式

整套系統只在 LAN / Local Network 裡運作。

架構：

iPhone

↓

Siri

↓

Apple Shortcuts

↓

家裡 LAN / Wi-Fi

↓

Windows Agent

↓

Windows 系統操作

\---

\# 3. 我要可以直接對 Siri 說

例如：

「嘿 Siri，控制電腦」

然後 Siri 問我指令。

我說：

「開啟 Discord」

Windows 就開 Discord。

其他例子：

「開 Steam」

「開 Photoshop」

「開 Chrome」

「開 Spotify」

「開記事本」

「開工作管理員」

「開設定」

「開檔案總管」

「關閉 Discord」

「關掉 Chrome」

「打開 YouTube Music」

「播放音樂」

「暫停音樂」

「下一首」

「上一首」

「音量大一點」

「音量小一點」

「靜音」

「取消靜音」

「鎖定電腦」

「關機」

\---

\# 4. 最重要功能：自動找到我電腦上的程式

我不希望每安裝一個程式，就要自己修改 Python 程式碼。

Agent 要自己建立：

Installed Application Catalog

自動找出 Windows 電腦上可以啟動的程式。

目標是支援「絕大多數正常安裝的 Windows 程式」。

不要宣稱能 100% 找到世界上所有特殊 portable app，但要盡量提高覆蓋率。

例如應該盡量可以找到：

Discord

Steam

Google Chrome

Microsoft Edge

Firefox

Spotify

LINE

Telegram

WhatsApp

Visual Studio Code

Visual Studio

Photoshop

Illustrator

Premiere Pro

After Effects

OBS Studio

VLC

Notepad++

7-Zip

Windows Terminal

PowerShell

Notepad

Calculator

Task Manager

File Explorer

Settings

Control Panel

以及其他正常安裝到 Windows 的程式。

\---

\# 5. Application Discovery

請建立完整的 application discovery 模組。

可以使用多種可信來源綜合建立 application catalog。

優先研究並使用 Windows 正常的應用程式來源，例如：

* Current User Start Menu shortcuts
* All Users Start Menu shortcuts
* Desktop shortcuts，如果合理
* Registry App Paths
* Registry installed application information
* Windows Start Apps
* Microsoft Store / UWP / packaged applications
* Shell AppsFolder
* Windows built-in system applications
* PATH 中已知的桌面應用程式，如果安全且合理
* 其他 Windows 官方或穩定 API

可以使用 Windows API、winreg、COM 或其他合理方法。

如果需要使用 PowerShell 取得 Windows 的應用程式資訊：

可以由程式內部執行「固定、寫死、由開發者控制」的 PowerShell command。

但是絕對不能：

把 iPhone 傳來的文字直接加入 PowerShell。

也不能提供 remote PowerShell execution API。

\---

\# 6. 不要掃描整顆硬碟

不要：

遞迴掃 C:\ 找所有 exe。

不要把：

Downloads

Temp

Cache

Browser downloads

裡面的 exe 自動視為可信任 application。

Application Catalog 應以正常 Windows 安裝資訊為主。

\---

\# 7. Application Catalog

請為每個程式建立結構化資料。

至少包含：

* display\_name
* normalized\_name
* aliases
* launch\_method
* launch\_target
* executable path（只限 discovery 自己找到的可信來源）
* process information（如果可靠）
* source
* app type
* optional AUMID
* optional shortcut path
* confidence

launch\_target 等內部資訊不能直接由遠端 API 任意傳入。

\---

\# 8. 程式名稱辨識

我要可以傳：

Discord

discord

DISCORD

都找到同一個。

需要 normalization，例如：

* lowercase
* trim spaces
* normalize punctuation
* normalize hyphen
* collapse duplicate whitespace

另外建立 alias。

例如：

Google Chrome

aliases：

chrome

google chrome

Microsoft Visual Studio Code

aliases：

vscode

vs code

visual studio code

code

Adobe Photoshop 2026

aliases：

photoshop

adobe photoshop

\---

\# 9. 中文 alias

請內建常見 Windows 程式中文 alias。

例如：

工作管理員

→ Task Manager

記事本

→ Notepad

計算機

→ Calculator

小算盤

→ Calculator

檔案總管

→ File Explorer

文件總管

→ File Explorer

設定

→ Settings

Windows 設定

→ Settings

終端機

→ Windows Terminal

命令提示字元

→ Command Prompt

控制台

→ Control Panel

瀏覽器

→ 系統預設瀏覽器

PowerShell

→ Windows PowerShell / PowerShell

\---

\# 10. Fuzzy Search

支援 fuzzy matching。

例如實際程式：

Adobe Photoshop 2026

我說：

photoshop

應該可以找到。

但不能過度猜測。

例如電腦上同時有：

Visual Studio 2026

Visual Studio Code

如果我只說：

Visual Studio

不要偷偷選其中一個。

應回傳：

找到多個可能的程式：

* Visual Studio 2026
* Visual Studio Code

讓 iPhone / Siri 再問我。

\---

\# 11. 搜尋優先順序

建議匹配優先順序：

1. Exact alias match
1. Exact normalized name match
1. Strong prefix / token match
1. Fuzzy match
1. Ambiguous candidates

不要因為低 confidence fuzzy match 就直接啟動錯誤程式。

設計合理 confidence threshold。

\---

\# 12. 開啟程式

支援：

open\_app

例如：

我說：

「開啟 Discord」

Agent：

解析 command

搜尋 Application Catalog

找到 Discord

安全啟動 Discord。

\---

\# 13. 開程式時的安全要求

API 不接受：

exe path

command line

arguments

shell command

PowerShell command

CMD command

Python code

batch file path

script path

也不要接受：

C:\xxx\xxx.exe

然後直接執行。

遠端只能提供：

application name

真正的 launch information 必須由 Agent 自己的 application catalog 決定。

\---

\# 14. 關閉程式

支援：

close\_app

例如：

「關閉 Discord」

Agent 要找到：

Discord 對應的 currently running process。

優先正常關閉視窗。

不要一開始就 taskkill /f。

流程可以是：

1. 找 application
1. 找相關 process
1. 嘗試 graceful close
1. 等待合理時間
1. 如果仍存在，回報使用者

可以另外設計：

force\_close\_app

但是 force close 不要透過自然語言默認觸發。

如果提供 force close，必須是明確的額外操作。

\---

\# 15. Process mapping

Application Catalog 要盡可能保存：

app → process executable

但是不要因為名稱相似就亂殺 process。

例如：

Visual Studio Code

→ Code.exe

Discord

→ Discord.exe

Chrome

→ chrome.exe

如果無法可靠識別 process：

不要強制關閉。

回傳：

「可以找到這個程式，但無法安全判斷應關閉哪個 process。」

\---

\# 16. Windows 內建程式

盡量支援：

Task Manager

File Explorer

Settings

Control Panel

Calculator

Notepad

Windows Terminal

Command Prompt

PowerShell

Snipping Tool

Paint

Device Manager

Services

Event Viewer

Disk Management

以及其他常用 Windows 系統工具。

仍然遵守：

只能「開啟工具」。

不能把遠端文字當成 shell command 執行。

\---

\# 17. 網站

支援：

open\_website

建立 website configuration。

預設包含：

YouTube

YouTube Music

Spotify Web

Netflix

Google

ChatGPT

GitHub

可以在設定檔容易新增。

第一版不要允許 remote arbitrary URL。

例如：

我說：

「打開 YouTube Music」

Agent 從 website catalog 取得 URL。

不是直接使用 user input 當 URL。

\---

\# 18. 系統預設瀏覽器

開網站時優先使用 Windows 系統預設瀏覽器。

不要把 Chrome 路徑寫死。

\---

\# 19. 音樂控制

支援：

play\_pause

play

pause

next\_track

previous\_track

第一版可以使用 Windows media key / multimedia controls。

希望能控制：

Spotify

YouTube Music

Chrome

Edge

VLC

其他支援 Windows media session 的程式。

優先研究 Windows Global System Media Transport Controls 或可靠 Windows multimedia key 實作。

如果成熟 GitHub library 已經安全處理這件事，可以考慮使用。

\---

\# 20. 音量控制

支援：

volume\_up

volume\_down

mute

unmute

toggle\_mute

可以有：

steps

但限制範圍，例如：

1. 到 10。

不要允許非常大的值。

希望可以正常控制 Windows 系統 master volume。

\---

\# 21. 鎖定 Windows

支援：

lock

使用 Windows 正規方法，例如：

LockWorkStation

這個操作可以立即執行。

\---

\# 22. 關機

關機一定要有二次確認。

如果我說：

「關機」

不能直接 shutdown。

第一階段：

request\_shutdown

Server 建立：

cryptographically secure random confirmation token

有效時間例如：

60 秒。

token：

* 一次性
* 過期失效
* 使用後失效

Server 回覆：

「確定要關閉電腦嗎？」

以及內部 confirmation token。

iPhone Shortcut 顯示確認視窗。

如果我按：

確定

才送：

confirm\_shutdown

Windows 驗證 token 成功才關機。

\---

\# 23. 不要讓 shutdown confirmation token 被重放

測試：

* token 過期
* token 錯誤
* token 已使用
* token 缺失
* token 重複使用

都不能關機。

\---

\# 24. Local Network Only

FastAPI Server 是 LAN server。

因為 iPhone 必須從區域網路連進來，所以不能只監聽：

127\.0.0.1

需要提供 LAN mode。

例如：

0\.0.0.0:8000

但是必須配合 Windows Firewall 做限制。

\---

\# 25. Windows Firewall

setup 程式需要協助建立 Windows Firewall rule。

只允許：

TCP 8000

Windows Firewall：

Private Profile

不要允許 Public Profile。

不要建立 Internet exposure。

如果 Windows network profile 目前是 Public：

不要偷偷改。

顯示提示：

請將可信任的家用網路設定為 Private Network。

\---

\# 26. Firewall Source Scope

如果合理且不會破壞多 subnet 使用：

可以限制 RFC1918 private ranges 或使用者設定的 LAN subnet。

但是我的 1～4 樓可能不是同一 subnet。

所以不要只限制：

LocalSubnet

導致其他內部 VLAN / subnet 無法存取。

設計 firewall 設定時要考慮：

192\.168.x.x

10\.x.x.x

172\.16.x.x ～ 172.31.x.x

等 private networks。

最好把 allowed\_networks 做成設定檔。

\---

\# 27. LAN 網路情況

請在 README 解釋：

不同 Wi-Fi 不代表一定不能用。

只要：

iPhone 所在 subnet

可以 route 到

Windows 所在 subnet

就可以。

例如：

iPhone：

192\.168.20.30

Windows：

192\.168.10.50

只要 Router / Layer 3 switch 允許：

192\.168.20.0/24

→

192\.168.10.0/24

即可。

\---

\# 28. 可能導致不能連線的情況

README 請列出：

Guest Wi-Fi

AP Isolation

Client Isolation

VLAN Isolation

Inter-VLAN Firewall

Windows Firewall

Windows Network Profile = Public

錯誤 IP

Server 沒啟動

Port 不正確

Wi-Fi Router 阻擋 LAN to LAN

這些情況可能讓 iPhone 找不到 Windows。

\---

\# 29. Windows IP

iPhone Shortcut 需要知道 Windows 位址。

優先提供兩種方式：

方案 A：

使用 Windows hostname。

例如：

http://MY-PC:8000

如果家中的 DNS / mDNS / local hostname resolution 正常，就可以使用。

方案 B：

固定 IP。

推薦使用 Router 的：

DHCP Reservation

讓 Windows 每次都取得同一個 IP。

例如：

192\.168.10.50

不要優先叫我直接在 Windows 裡手動設定 Static IP。

Router DHCP Reservation 比較適合一般使用者。

\---

\# 30. 可選：LAN Discovery

如果容易做到，可以研究：

Bonjour

mDNS

zeroconf

讓 iPhone 比較容易找到 Windows Agent。

例如：

windows-agent.local

但是：

這只是 optional feature。

不要讓 mDNS 成為必要條件。

因為 mDNS 不一定能跨 VLAN / subnet。

固定 IP / DNS hostname 必須仍然可用。

\---

\# 31. Authentication

即使只在 LAN，也一定要有 authentication。

不要因為是內網就做成：

任何裝置都可以關機。

第一次 setup 自動產生強度足夠的 random API secret。

例如至少：

256-bit random

或等價安全強度。

\---

\# 32. API Key 儲存

不要 hardcode 在 source code。

可以存放在：

.env

或安全的 local config。

.gitignore 一定排除：

.env

secrets

runtime data

logs

提供：

.env.example

但是裡面不能有真正 secret。

\---

\# 33. iPhone Shortcut Authentication

Apple Shortcut 呼叫 Agent 時：

帶：

X-API-Key

或其他合理 authorization header。

如果你認為有簡單可靠的方法可以增加：

timestamp

nonce

HMAC request signing

以防止 LAN replay attack，

可以實作。

但是不要讓 Shortcut 複雜到一般人無法建立。

安全與易用性之間請做合理平衡。

\---

\# 34. HTTP / HTTPS

這套系統只在可信任 LAN 裡使用。

第一版可以使用 HTTP：

http://WINDOWS-IP:8000

但 README 必須清楚說明：

HTTP 在 LAN 上沒有傳輸加密。

安全主要依賴：

* 家中可信任網路
* Windows Firewall
* API authentication
* 不暴露 Internet
* 不使用 Guest Wi-Fi
* 不允許任意 shell

如果可以提供容易安裝、不會讓 iPhone 憑證管理變得非常麻煩的 HTTPS optional mode，也可以增加。

但是：

不要為了 HTTPS 把整個安裝流程搞得非常複雜。

\---

\# 35. API

建立 FastAPI。

至少提供：

GET /health

GET /info

GET /apps

POST /apps/search

POST /apps/refresh

POST /action

POST /command

\---

\# 36. /health

回傳簡單狀態，例如：

Agent running

版本

uptime

不要回傳：

API secret

敏感路徑

完整系統資訊。

\---

\# 37. /apps

列出 Agent discovery 找到的應用程式。

不要預設回傳敏感的完整 filesystem path 給 iPhone。

可以回傳：

display name

aliases

type

source category

必要時 ID。

內部 path 留在 server。

\---

\# 38. /apps/search

傳入搜尋文字。

例如：

photoshop

回傳：

best match

confidence

candidates

是否 ambiguous。

\---

\# 39. /apps/refresh

重新建立 application catalog。

我安裝新程式之後，可以不用重開整個 Agent。

例如：

「重新掃描程式」

可以觸發 refresh。

\---

\# 40. /action

接受結構化安全操作。

例如：

open\_app

close\_app

open\_website

media\_play\_pause

media\_next

media\_previous

volume\_up

volume\_down

mute

unmute

toggle\_mute

lock

request\_shutdown

confirm\_shutdown

refresh\_apps

\---

\# 41. /command

這是 Siri 主要使用的 API。

傳入：

text

例如：

「開啟 Discord」

Agent 自己解析。

不要讓 Apple Shortcut 寫一堆 if/else。

所有 command parsing 儘量在 Windows Agent。

\---

\# 42. Natural Language Parser

第一版不要接付費 LLM API。

先建立 rule-based parser。

支援繁體中文和基本英文。

例如：

開啟 Discord

打開 Discord

啟動 Discord

開 Discord

→ open\_app Discord

關閉 Discord

關掉 Discord

退出 Discord

→ close\_app Discord

\---

\# 43. 媒體語句

支援：

播放音樂

繼續播放

播放

暫停

播放暫停

下一首

下一曲

上一首

上一曲

\---

\# 44. 音量語句

支援：

音量大一點

音量增加

聲音大一點

調大音量

音量小一點

音量降低

聲音小一點

調小音量

靜音

取消靜音

解除靜音

\---

\# 45. 系統語句

支援：

鎖定

鎖定電腦

鎖電腦

關機

關閉電腦

重新掃描程式

更新程式清單

\---

\# 46. 英文 command

至少支援：

open Discord

launch Discord

close Discord

play

pause

next track

previous track

volume up

volume down

mute

unmute

lock PC

shutdown

refresh apps

\---

\# 47. Parser 安全性

Parser 永遠只能產生：

預先定義好的 action。

Parser 不可以產生：

shell command

PowerShell command

Python expression

filesystem command

raw executable command。

\---

\# 48. 惡意或奇怪輸入

例如使用者說：

「開 PowerShell 然後刪除 C 槽」

只能辨識：

open\_app = PowerShell

或者更安全：

判定這個 request 含有 unsupported command，拒絕執行後半部。

絕對不能執行：

刪除 C 槽。

\---

\# 49. 絕對禁止 Remote Shell

整個專案最重要的 security invariant：

這不是 Remote Shell。

任何 API 都不能提供：

run\_command

run\_shell

run\_powershell

run\_cmd

execute

eval

python\_exec

script

terminal\_command

之類的能力。

\---

\# 50. subprocess 安全

如果使用 Python subprocess：

避免：

shell=True

任何 user-controlled string 不可以直接進 command line。

所有 executable target 必須來自：

Agent 自己建立並驗證的 application catalog

或者開發者寫死的 system action。

\---

\# 51. Path 安全

不要讓遠端 request 傳：

C:\Program Files\xxx.exe

然後 server 執行。

即使它真的存在也不行。

User 只能說：

Photoshop

Agent 自己 lookup catalog。

\---

\# 52. 網站安全

不要接受：

open\_url = 任意網址。

使用：

website catalog。

可以提供設定檔讓我在 Windows 本機新增網站。

但是遠端 command 不能直接新增惡意 URL。

\---

\# 53. Configuration

建立一般使用者可讀設定檔。

例如：

config.yaml

或：

config.toml

內容可以設定：

port

bind address

allowed networks

volume step

shutdown confirmation timeout

website aliases

application aliases

log level

hostname display name

不要讓我要修改 Python source。

\---

\# 54. Custom Aliases

我要可以很簡單新增自己的名稱。

例如：

Discord

alias：

語音

Chrome

alias：

瀏覽器

OBS Studio

alias：

錄影

Adobe Photoshop

alias：

PS

最好可以直接在 config 檔設定。

\---

\# 55. App Cache

Application Catalog 可以 cache 到本機。

例如 JSON database。

Agent 啟動：

載入 cache

背景 / 啟動時 refresh

或視需要 refresh。

不要每次 Siri command 都重新掃全部 Windows。

\---

\# 56. Auto Refresh

可以設計：

Agent 啟動時 refresh

以及：

手動 refresh

如果成本低，也可以定期 refresh。

但不要頻繁掃描造成效能問題。

\---

\# 57. 安裝

建立：

setup.ps1

我要能在 Windows PowerShell 執行：

setup.ps1

它自動：

1. 檢查作業系統是不是 Windows
1. 檢查 Python
1. 檢查需要的 Python version
1. 建立 .venv
1. 安裝 dependencies
1. 建立 config
1. 產生 API key
1. 建立 runtime folders
1. 建立 application catalog
1. 執行基本 self-test
1. 詢問是否建立 Windows Firewall Private rule
1. 顯示 Windows LAN IP
1. 顯示 health URL
1. 告訴我下一步

如果沒有 Python：

請給一般人看得懂的安裝說明。

如果合理，也可以自動透過 winget 安裝 Python，但不要未經提示偷偷做大量系統修改。

\---

\# 58. Windows Firewall 安裝

setup.ps1 可以詢問：

是否建立 Windows Firewall rule？

如果使用者同意：

建立規則。

規則名稱例如：

Siri Windows Agent

只允許：

TCP 8000

Private profile

不要 Public profile。

\---

\# 59. start.bat

建立：

start.bat

讓我雙擊就可以啟動 Agent。

它應該：

啟動 .venv

啟動 Server

顯示簡單狀態。

\---

\# 60. stop

提供簡單停止方式。

如果有 system tray：

可以右鍵 Stop Agent。

沒有 system tray：

至少 start.bat 視窗 Ctrl+C 可以正常停止。

\---

\# 61. Windows 自動啟動

建立：

install-startup.ps1

功能：

讓我選擇是否登入 Windows 後自動啟動 Agent。

不要在 setup 階段偷偷強制安裝自動啟動。

同時提供：

uninstall-startup.ps1

\---

\# 62. System Tray

如果不會造成太大複雜度，加入 system tray app。

右鍵選單：

Agent Running

Copy Address

Show IP

Refresh Apps

List Apps

Open Config

Open Logs

Open README

Restart Agent

Stop Agent

這是 nice-to-have。

如果會影響核心穩定性：

先完成核心功能。

\---

\# 63. Status UI

如果容易做到，可以建立非常簡單的 local web page：

http://WINDOWS-IP:8000/

顯示：

Agent Online

PC Name

IP

Application count

Last refresh

API status

但不要顯示 API Key。

可以有：

Refresh Apps

但敏感操作仍需要 authentication。

\---

\# 64. iPhone Apple Shortcut

README 必須非常詳細教我做：

Shortcut 名稱：

控制電腦

使用流程：

「嘿 Siri，控制電腦」

↓

Siri / Shortcut 聽寫

↓

取得使用者說的文字

↓

POST 到：

http://WINDOWS-IP:8000/command

↓

帶 Authentication Header

↓

Server 回傳 JSON

↓

Shortcut 取得 message

↓

Siri 念出 message。

\---

\# 65. iOS Shortcut 要盡量簡單

不要讓我建立：

30 個 If

50 個 Menu

大量 Dictionary mapping。

最好只需要：

1. Dictate Text
1. 建立 request
1. Get Contents of URL
1. 取得 message
1. Speak Text

所有邏輯放 Windows Agent。

\---

\# 66. Apple Local Network Permission

README 提醒：

iOS 第一次讓 Shortcuts 存取區域網路時，可能需要允許：

Local Network

如果被拒絕：

教我去哪裡重新開啟。

\---

\# 67. Siri 回覆

成功：

「已開啟 Discord。」

「已關閉 Chrome。」

「音量已提高。」

「已切換播放狀態。」

「已鎖定電腦。」

錯誤：

「找不到 Discord。」

Ambiguous：

「找到兩個可能的程式：Visual Studio 和 Visual Studio Code，請說完整名稱。」

\---

\# 68. 關機 Shortcut

如果 command response 是：

confirmation\_required

Shortcut：

顯示確認視窗。

例如：

「確定要關閉 Windows 電腦嗎？」

如果：

Cancel

不做任何事。

如果：

Confirm

再 POST confirmation token。

\---

\# 69. API Response

統一 response schema。

例如：

success

status

action

message

candidates

confirmation\_required

confirmation\_token

error\_code

不要讓 iPhone 需要解析一堆不同格式。

\---

\# 70. Error Handling

處理：

Invalid API key

Missing API key

Invalid command

Unknown app

Ambiguous app

App launch failure

App close failure

Website not found

Media control failure

Volume failure

Shutdown token expired

Shutdown token reused

Shutdown token invalid

Firewall issue

Network issue

Catalog unavailable

Malformed request

\---

\# 71. 不要把 stack trace 傳給 iPhone

iPhone 只收到：

簡單錯誤。

詳細 stack trace：

只寫 Windows 本機 log。

\---

\# 72. Logging

記錄：

timestamp

client IP

action

target

result

duration

error code

但是不要記錄：

API Key

完整 shutdown token

Secret

authorization header

\---

\# 73. Rate Limiting

因為這是控制電腦的 API：

加入簡單 rate limit。

避免 LAN 上某台裝置瘋狂呼叫。

例如：

合理的每 IP 每分鐘限制。

但是不要限制到 Siri 正常使用會卡住。

\---

\# 74. Replay / brute force

至少：

API Key 比對使用安全方式。

Authentication failure 不要回傳太多資訊。

可以加入：

短暫 rate limit。

不要因為錯誤 key 嘗試就把 Agent crash。

\---

\# 75. Dependencies

優先減少 dependency。

可使用：

FastAPI

uvicorn

pydantic

python-dotenv

其他 Windows dependency 視需要加入。

如果 stdlib + Windows API 就能完成：

優先不用額外 package。

如果 GitHub / PyPI 有成熟 Windows library：

請評估：

maintenance

downloads

license

security

最後再決定是否使用。

\---

\# 76. Architecture

不要全部寫在一個 Python 檔。

建議結構：

app/

main

api

config

models

auth

command\_parser

app\_catalog

app\_discovery

app\_launcher

process\_control

media\_control

volume\_control

system\_control

shutdown\_confirmation

website\_catalog

logging\_config

network

utils

tests/

scripts/

runtime/

logs/

config/

你可以自行改善結構。

\---

\# 77. Tests

使用 pytest 或其他合理 Python 測試框架。

至少測試：

health endpoint

authentication success

authentication failure

missing authentication

application discovery parsing

application normalization

exact match

alias match

Chinese alias

fuzzy match

ambiguous match

unknown application

open app validation

close app validation

website allowlist

media parser

volume parser

volume limit

lock parsing

shutdown request

shutdown confirmation

expired shutdown token

reused shutdown token

invalid shutdown token

command parser Chinese

command parser English

malicious command rejection

arbitrary executable path rejection

arbitrary URL rejection

shell command rejection

PowerShell injection rejection

CMD injection rejection

\---

\# 78. 測試不能真的操作我的電腦

Automated tests 不可以真的：

關機

鎖定

關 Chrome

開 Photoshop

調音量

殺 process

tests 必須 mock Windows system calls。

\---

\# 79. Security Tests

一定要測：

輸入：

open C:\Windows\System32\cmd.exe

不能直接執行 path。

輸入：

powershell -command ...

不能執行。

輸入：

cmd /c ...

不能執行。

輸入：

Discord && shutdown /s

不能執行第二段。

輸入：

Discord; rm ...

不能被 shell interpretation。

\---

\# 80. 不使用 shell=True

除非有非常特殊且充分理由：

整個程式避免 shell=True。

如果真的需要：

必須確認沒有 user-controlled input。

\---

\# 81. README

README 寫給不懂程式的人。

用繁體中文。

不要只寫開發者 README。

我要看到：

第一步做什麼

第二步做什麼

第三步做什麼。

\---

\# 82. README 必須包含

安裝方法

啟動方法

停止方法

第一次 setup

Firewall

如何找 Windows IP

如何設 DHCP Reservation

如何測 /health

如何看找到哪些程式

如何 refresh apps

如何設定 alias

如何設定網站

如何建立 iPhone Shortcut

如何設定 API key

如何使用 Siri

如何處理不同樓層 Wi-Fi

如何處理不同 subnet

如何排查 Guest Wi-Fi

如何排查 AP Isolation

如何排查 Windows Firewall

如何排查 Public Network Profile

如何卸載

\---

\# 83. 網路測試

README 教我：

Windows Agent 啟動後，

先在 Windows：

確認 health。

再從 iPhone Safari：

打開：

http://WINDOWS-IP:8000/health

如果能看到：

Agent online

代表網路正常。

如果 Safari 都連不到：

先不要怪 Siri Shortcut。

先排查 LAN。

\---

\# 84. 跨樓層

README 特別加入：

「1 樓可以用，但 4 樓不能用怎麼辦？」

檢查：

1. 樓 Wi-Fi 是否 Guest Network

AP Isolation

1. 樓是否不同 VLAN

Router 是否允許 Inter-VLAN routing

Windows Firewall allowed subnet

IP 是否正確。

\---

\# 85. 如果不同 subnet

如果：

Windows = 192.168.1.50

iPhone = 192.168.20.25

只要網路設備允許 routing：

仍然可以。

不要寫成：

一定要相同 192.168.1.x 才能使用。

\---

\# 86. 程式重新掃描

我要安裝新程式後可以：

說：

「重新掃描程式」

或者 system tray：

Refresh Apps

或者 API：

/apps/refresh

重新建立 catalog。

\---

\# 87. Portable App

Portable applications 不一定存在正常 installation metadata。

第一版不必掃整個硬碟。

但是可以設計：

manual\_apps

設定。

讓我在 Windows 本機 config 手動加入可信任 portable app。

例如：

name

path

aliases

這個設定只能在 Windows 本機修改。

遠端 API 不可以新增 executable path。

\---

\# 88. Manual Apps

如果 config 有：

manual apps

啟動時驗證：

path 存在

是檔案

extension 合理

使用者明確配置。

不要接受遠端修改。

\---

\# 89. App Discovery Debug

提供：

app discovery diagnostics

讓我如果找不到某程式，可以看到：

Agent 從哪些來源掃描

找到多少程式

哪些被忽略

原因是什麼。

但是不要把敏感完整資料傳給 iPhone。

可以寫到 local log / diagnostics file。

\---

\# 90. Version

Agent 有：

VERSION

GET /info 顯示：

version

方便未來更新。

\---

\# 91. Git

建立：

.gitignore

排除：

.env

API keys

logs

runtime cache

venv

\*\*pycache\*\*

generated secrets。

\---

\# 92. requirements

建立：

requirements.txt

如果更適合：

pyproject.toml

也可以。

但 setup.ps1 必須自動處理。

\---

\# 93. GitHub 開源利用原則

再次強調：

如果某個功能已經有成熟的 GitHub OSS：

例如：

Windows application discovery

Start Menu parsing

.lnk shortcut parsing

Windows media controls

Windows volume control

FastAPI rate limiting

Windows tray icon

可以先研究現有方案。

不需要為了展示能力而重新寫 500 行。

但是引入之前：

檢查 license。

檢查維護狀態。

檢查 security。

檢查是否真的有必要。

如果只需要十幾行 Windows API：

不要引入巨大的 framework。

\---

\# 94. 不需要 AI / LLM

第一版不要：

OpenAI API

Claude API

Gemini API

Local LLM

Ollama

Computer Vision

OCR

Screen recognition

GUI Agent

先把：

Siri → Command Parser → Safe Actions

做好。

\---

\# 95. 未來擴充

架構要方便未來加入：

LLM command understanding

更多 Smart Home 控制

Computer automation

但是現在不要實作。

\---

\# 96. 最重要安全底線

任何遠端文字都不能直接變成：

shell command

PowerShell

CMD

Python

JavaScript

EXE path

arbitrary URL

filesystem instruction。

只能：

Text

↓

Safe parser

↓

Known Action

↓

Validated Target

↓

Windows Control Function

\---

\# 97. 最終使用體驗

完成後，我希望：

我在家裡任何一層拿 iPhone。

說：

「嘿 Siri，控制電腦。」

Siri：

「請說。」

我：

「開 Discord。」

Windows：

Discord 開啟。

Siri：

「已開啟 Discord。」

我：

「嘿 Siri，控制電腦。」

「開 Photoshop。」

Windows 開 Photoshop。

我：

「音量大一點。」

Windows 音量提高。

我：

「播放音樂。」

Windows 播放。

我：

「下一首。」

Windows 下一首。

我：

「鎖定電腦。」

Windows 鎖定。

我：

「關機。」

Siri：

「確定要關閉電腦嗎？」

我確認後：

Windows 才關機。

\---

\# 98. 完成工作後請自行驗證

完成 coding 後：

1. 執行 formatter
1. 執行 static checks，如果專案有
1. 執行 tests
1. 修正所有合理的 failed tests
1. 確認 import 正常
1. 確認 FastAPI 可以 start
1. 確認 /health 正常
1. 確認 authentication 正常
1. 確認 application discovery 不 crash
1. 確認 application search 正常
1. 確認沒有 shell injection
1. 確認 shutdown confirmation 正常
1. 確認 API Key 沒有 commit
1. 確認 setup.ps1 可理解
1. 確認 start.bat 正確

\---

\# 99. 如果有問題，不要停在 TODO

如果你遇到：

某 Windows API 不好用

某 dependency 不穩

某 GitHub 專案不適合

請自行換方案。

不要只留：

TODO

讓我自己解決。

如果某功能在 Windows 技術上無法 100% 保證：

做最合理 fallback。

並在 README 用簡單方式解釋限制。

\---

\# 100. 最後回答我的格式

最後不要貼幾千行 source code 給我。

程式碼直接建立在 repository。

最後只需要簡單告訴我：

1. 已完成哪些功能

1. 我第一次要執行哪個檔案

1. 我要怎麼啟動

1. 我的 Windows IP 在哪裡看

1. iPhone Shortcut 要怎麼設

1. 我要怎麼對 Siri 說

1. 新安裝程式後怎麼重新掃描

1. 如果 1 樓能用但 4 樓不能用，要檢查什麼

1. 哪些功能目前有 Windows 本身限制

\---

\# 101. 【架構審查修正】執行環境：必須在登入使用者的 Interactive Session 執行

修正說明：原規格未明確規定 Agent 的執行 session 類型。因為 Agent 主要工作是開啟 GUI 應用程式（Discord、Chrome、Photoshop 等）與操作目前使用者的媒體播放，若 Agent 以非互動式 session 執行（例如一般 Windows Service 預設的 Session 0），會發生：

* API 回報程式已啟動，但登入使用者桌面上看不到視窗
* GUI process 出現在錯誤的 session
* Media session / 使用者應用程式存取異常
* 使用者 profile、環境變數、AppData 與登入使用者不同

因此明確規定：

> Windows Siri Agent 必須在目前登入使用者的 interactive desktop session 中執行。

不能把「一般 Windows Service」當成主要部署方式。

Agent 啟動時應偵測自己是否執行在 interactive user session：

* 如果不是，記錄 warning log，並在 `/info` 或 diagnostics 中標示「GUI launch 可能不正常」，不要假裝一切正常。

\---

\# 102. 【架構審查修正】自動啟動方式：Task Scheduler「At log on」（第一版唯一方案）

修正說明：取代原本模糊的「開機啟動」構想，明確規定自動啟動機制：

第一版\*\*只採用\*\* Task Scheduler，Trigger 設為 `At log on`，Target 為目前使用者，執行模式為 `Run only when user is logged on`（interactive user，而非 SYSTEM）。

\*\*不在第一版提供 Startup folder（`shell:startup`）選項\*\*——已確認先只做 Task Scheduler 一種，避免安裝流程多一層選擇造成困惑；Startup folder 留待未來若使用者有需求再評估加入。

`setup.ps1` 負責建立 Task Scheduler 項目，並詢問使用者是否要啟用。`uninstall.ps1` 對應移除該工作排程器項目。

若偵測到 Agent 被以 SYSTEM 或不適當的 service context 啟動，應在 log 與 README 中明確提示：GUI application launch 可能不正常。

未來若加入 Windows Service，只能作為輔助元件（例如背景監控），不能負責直接啟動 GUI application。

\---

\# 103. 【架構審查修正】Application Discovery 必須區分 Trusted Launch Source 與 Metadata-only Source

修正說明：原規格第 5 條列出的來源（Start Menu、Registry App Paths、Registry installed application info、AppsFolder、UWP 等）需要進一步分類，因為不是所有「已安裝程式資訊」都能直接拿來啟動程式——例如 Registry 的 Uninstall / Installed Programs 資訊通常只適合取得 Display Name、Publisher、Version、Install Location 等 metadata，不一定包含可靠的啟動方法。

明確分類：

\*\*A. Trusted Launch Sources（可直接作為啟動依據）\*\*

* Start Menu `.lnk`（Current User / All Users）
* Registry `App Paths`
* Windows AppsFolder
* UWP / packaged app AUMID
* Windows 已知 system application（見第 106 條 system_apps mapping）
* 使用者在本機 `manual_apps` 明確設定的 portable application

\*\*B. Metadata-only Sources（僅補充資訊，不可作為 launch target）\*\*

* Installed Programs Registry / Uninstall Registry
* Publisher / Version / Install Location 等 metadata
* 其他沒有明確 launch contract 的資料來源

Application Catalog（對應原規格第 7 條）的每筆資料除了原有欄位外，需再加上：

* `launch_source`（來源屬於 A 或 B）
* `launch_confidence`
* `metadata_confidence`

避免發生「掃描到程式，但 launch target 根本不是可執行的入口」的狀況。

\---

\# 104. 【架構審查修正】啟動資料流必須逐層收斂，不可任意字串直達 subprocess

修正說明：原規格第 13 條「開程式時的安全要求」與第 96 條「最重要安全底線」的精神保留並具體化為明確資料流：

```text
Siri Text
    ↓
Command Parser
    ↓
Validated Action（封閉 action 集合，見第 40 條）
    ↓
Application Matcher
    ↓
Trusted AppEntry（來自 Catalog，具備穩定 app_id）
    ↓
LaunchSpec（由 Catalog 根據 AppEntry 建立，Windows Adapter 不可自行組裝）
    ↓
Windows Launcher Adapter
```

不可以是：

```text
User Text → String Path → subprocess
```

Windows Launcher Adapter 只接受經 Catalog 驗證的 `AppEntry` 或由 Catalog 建立的 `LaunchSpec`，不接受任意 path string、command string、arguments，或使用者提供的 executable。即使上層 API 已驗證過，Adapter 本身也不假設輸入一定可信，需再次檢查（例如 path 是否仍存在、是否屬於已知來源）。

\---

\# 105. 【架構審查修正】關閉程式：強化為 Running Application Resolver，不只用 process name

修正說明：原規格第 14–15 條的 graceful close 精神保留，但需強化，因為很多 Windows application（Chrome、Discord、VS Code、Steam、Adobe 系列）會有多個 process、child process、updater/launcher process，不能只做「app name → xxx.exe → kill」。

建議流程：

```text
Application Catalog
    ↓
Process hints / executable identity
    ↓
目前登入使用者 Session
    ↓
Top-level windows / 關聯 process tree
    ↓
Graceful Close
```

具體步驟：

1. 找到屬於目前登入使用者 session、且符合 Catalog process hints 的 application
2. 找到其 top-level window
3. 發送正常關閉訊息（例如 `WM_CLOSE`）
4. 等待合理 timeout
5. 檢查是否已退出
6. 若仍存在，回報失敗（而非直接強制關閉）

若 process identity 不夠可靠，不強制關閉，回傳：「找得到這個應用程式，但目前無法安全判斷應關閉哪個程序。」

\*\*Force Close 為獨立、明確的高風險操作\*\*：「關閉 Discord」不會自動升級成強制關閉。只有使用者明確說出下列觸發語句，才進入 `force_close_app` 流程，且仍只能操作 Catalog / Process Resolver 已驗證過的 application，不接受任意 process id。

\*\*中文觸發詞範例\*\*：

* 強制關閉 Discord
* 強制結束 Discord
* 強制退出 Discord
* 強制終止 Discord
* 直接砍掉 Discord

\*\*英文觸發詞範例\*\*：

* force close Discord
* force quit Discord
* force kill Discord
* forcefully close Discord

Command Parser 需將上述「force / 強制」類詞彙與 app 名稱組合時，一律解析為 `force_close_app`；未出現這類明確詞彙時（例如單純「關閉 Discord」「close Discord」），一律解析為 `close_app`（graceful close），不得以任何啟發式規則自動升級。此清單可依實際使用情況擴充，但新增詞彙同樣必須包含明確的「強制／force」語意，不可用模糊詞彙（例如單純「不要 Discord」）觸發。

\---

\# 106. 【架構審查修正】Windows 內建工具使用明確 System App Mapping

修正說明：對應原規格第 16 條，Task Manager、Settings、Calculator、Notepad、File Explorer、Control Panel、Windows Terminal、Paint、Snipping Tool 等 Windows 內建工具，由程式維護一份 `system_apps` mapping（well-known system targets），視為 Trusted Launch Source 的一種，不需要依賴一般 Discovery 流程。這不違反「不要把所有應用程式寫死」的原則，因為這些是 Windows 官方已知的固定入口；一般第三方應用程式仍然依賴 Discovery。

\---

\# 107. 【架構審查修正】Firewall Adapter 職責：檢查與（經同意後）建立規則需分離

修正說明：原規格第 25 條「setup 程式需要協助建立 Windows Firewall rule」的精神保留，但需明確劃分職責：

\*\*Agent 正常執行時\*\*：只檢查目前 network profile 與 firewall 規則狀態（`inspect_network_profile()`、`inspect_firewall_rule()`），不自動修改 Firewall。

\*\*`setup.ps1`\*\*：可以詢問使用者「是否建立 Windows Firewall Private Network 規則？」，只有使用者明確同意後才建立規則（`create_private_rule()`）；規則只允許 Agent 的 TCP port，且只在 Private Profile。同時提供 `remove_agent_rule()` 供卸載使用。

不論何時都不自動修改 Windows Network Profile、Router、NAT、Port Forwarding、UPnP。

若偵測目前 network profile 為 Public，不偷偷改，顯示提示（對應原規格第 25 條已有此精神，此處明確化實作責任邊界）。

\---

\# 108. 【架構審查修正】Rate Limiter 的層級歸屬

修正說明：原規格第 73 條「Rate Limiting」的需求保留，但 rate limiter 屬於 HTTP client IP / request frequency / transport 層面的保護，架構上應放在 API / infrastructure 層（middleware），而非核心 domain / service 邏輯。若目前實作已經很簡單，不需要為此過度重構，重點是 responsibility 要清楚。

\---

\# 109. 【架構審查修正】Windows Adapter 一律以目前登入互動使用者為操作目標

修正說明：Windows Adapter 進行任何 application 操作時（app discovery、app launch、process resolve、media control、讀取 user profile / AppData / Start Menu / UWP Apps），都必須以目前登入的 interactive user session 為目標，避免誤用 SYSTEM account 或其他 session 的 process。若 Agent 偵測到自己不在 interactive user session 中執行，依第 101 條處理（log warning + diagnostic 提示，不假裝 GUI launch 正常）。

\---

\# 110. 【架構審查修正】Windows Integration Test 與 Unit Test 分離

修正說明：對應原規格第 77–78 條，Mock unit tests 很重要，但這個專案不能只靠 mock。新增「Windows Integration Tests」類別，只在真實 Windows 上執行，且測試時不可以真的：

* shutdown
* lock
* force kill 使用者程式

可以安全測試的項目包含：

* discovery 是否找到 Windows built-in app
* Start Menu shortcut 是否能正確解析
* catalog refresh 是否正常運作
* Registry App Paths discovery
* AppsFolder / AUMID discovery
* 目前 interactive session 偵測是否正確
* network profile 偵測是否正確
* （若有安全的 test fixture application）test fixture 的實際啟動

Unit Test（mock 化，可在任何環境執行）與 Windows Integration Test（僅在真實 Windows 執行）在測試目錄與 CI/驗證流程中明確分開。

本規格僅定義 Windows Integration Test 的測試範圍與安全邊界（哪些可以測、哪些不可以真的執行），\*\*實際執行指令、pytest 參數、README 操作步驟由實作階段（Codex / 開發 Agent）依專案實際結構補上\*\*，不在本規格中預先寫死。

\---

\# 111. 本次審查修正範圍聲明

本次修正（第 101–110 條）不改變原規格第 1–100 條的核心需求與優先順序，僅：

* 補充第 101、102 條原本缺漏的執行環境與自動啟動規格
* 將第 103–109 條的既有精神（discovery 來源可信度、啟動安全收斂、process 關閉安全性、firewall 職責、rate limiter 定位）具體化，避免實作時走偏
* 新增第 110 條測試類別，作為第 77–78 條的補充，而非取代

原規格中的公網禁止（第 2 條）、LLM 禁止（第 94 條）、shutdown 二次確認（第 22–23 條）、遠端文字不可變成 shell command（第 96 條）等安全底線全數保留，不受本次修正影響。


\---

\# 優先順序

如果需要取捨，優先順序：

1. 安全
1. 能正常使用
1. Siri Shortcut 簡單
1. 自動辨識已安裝程式
1. LAN 跨不同 Wi-Fi / subnet 可用
1. 穩定
1. 容易安裝
1. 容易維護
1. UI 漂亮

不要為了漂亮 UI 犧牲核心功能。

現在請直接開始建立完整專案，不要只提供設計建議。

\---

\# 附錄：架構方案（v2 — 已依 review 修正）

以下是依照架構審查意見（見專案 review 文件）修正後的實作架構規劃。核心分層方向（API → Domain/Service → Windows Adapter → Windows System）維持不變，本版針對 interactive session、launch source 分類、啟動安全邊界、process 關閉、firewall 職責、rate limiter 位置、測試分類等項目做了修正與強化。

\## 分層原則（已加入 Interactive User Session 邊界）

\`\`\`
API Layer (FastAPI routes)
  驗證、序列化、呼叫 service；不直接操作 Windows
      ↓
Infrastructure（auth / rate_limit / config / logging）
  橫切關注點，不屬於 domain 核心邏輯
      ↓
Service Layer（orchestration）
  CommandService → Parser → Matcher → AppService → Adapter
      ↓
Domain Layer（純資料模型與規則，無 Windows 依賴）
  actions.py / app_models.py / matching.py
  → 這層可以完整單元測試，不需要真的 Windows 機器
      ↓
Windows Adapter Layer（唯一碰 Windows API 的地方）
  discovery / launcher / process / media / volume / system / firewall
  → 只在目前登入使用者的 interactive session 中操作
  → 只有這層（及少數 integration test）需要在真實 Windows 上驗證
      ↓
目前登入的 Interactive User Session
      ↓
Windows System
\`\`\`

\*\*關鍵修正\*\*：Agent 本身必須執行在目前登入使用者的 interactive desktop session（Task Scheduler `At log on`，非 SYSTEM / 非一般 Windows Service），這一點在架構圖中明確標出，而不只是部署細節。

\## 目錄結構（v2）

\`\`\`
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
\`\`\`

\## 關鍵設計決策（v2）

1\. \*\*Interactive User Session 是架構的第一優先前提\*\*：`main.py` 啟動時即偵測目前是否執行在 interactive user session，若否，log warning 並在 `/info` 標示 GUI launch 可能不正常。自動啟動一律採 Task Scheduler `At log on`（interactive user 模式），不採一般 Windows Service。

2\. \*\*Discovery 輸出區分 `launch_source`（Trusted / Metadata-only）\*\*：`AppEntry` 除了 display_name、aliases、confidence 之外，明確標記資料是否來自可信啟動來源（Start Menu `.lnk`、App Paths、AppsFolder/AUMID、system_apps mapping、manual_apps）或僅為補充 metadata（Uninstall Registry 等）。只有 Trusted Launch Source 可以進一步生成 `LaunchSpec`。

3\. \*\*啟動資料流逐層收斂，Adapter 不信任任何遠端字串\*\*：`Command Parser → ValidatedAction → Matcher → Trusted AppEntry → LaunchSpec → Windows Launcher Adapter`。`launcher.py` 只接受 `app_service.py` 建立好的 `LaunchSpec`，即使上層已驗證，Adapter 內部仍再次確認 path 存在、來源合法。

4\. \*\*Process 關閉改為 Running Application Resolver\*\*：`process.py` 先用 Catalog 的 process hints 在目前 session 內找出相關 process/top-level window，發送 graceful close，等待 timeout 後再確認；找不到可靠對應時回報「無法安全判斷應關閉哪個程序」，不亂殺。`force_close_app` 是獨立、明確、higher-risk 的操作，不會被自然語言「關閉 X」自動觸發。

5\. \*\*Firewall 職責明確分離\*\*：`firewall.py` 執行期只提供 `inspect_network_profile()` / `inspect_firewall_rule()`（唯讀）；`create_private_rule()` / `remove_agent_rule()` 只能由 `setup.ps1` 在使用者明確同意後呼叫，且規則只開放 Agent port、只在 Private Profile。

6\. \*\*Rate limiter 放在 infrastructure，不放 domain\*\*：`rate_limit.py` 作為 middleware，處理 client IP / request frequency，與 domain 的商業規則（parser、matcher、shutdown flow）分離。

7\. \*\*Catalog 使用穩定 `app_id`\*\*：Matcher 找到程式後，後續流程（`/apps/search` 回傳、`/action` 執行）盡量透過 `app_id` 傳遞，避免重複用 display name 比對造成同名程式、大小寫、fuzzy match 不一致的問題。

8\. \*\*Windows 內建工具走 `system_apps` mapping\*\*：Task Manager、Settings、Calculator 等視為 Trusted Launch Source 的固定入口，不依賴一般 Discovery，也不算「把所有應用程式寫死」。

9\. \*\*測試分兩類\*\*：`tests/unit/`（mock 化，可在任何環境含本容器完整執行）與 `tests/integration_windows/`（只能在真實 Windows 執行，且明確禁止 shutdown / lock / force kill 等破壞性操作，只做唯讀或安全的探測）。

10\. \*\*Media control 維持 best-effort 標記\*\*：沿用 v1 設計，README 明確說明系統層 media control 作用於目前 active media session，無法保證只控制單一 app；第一版不做特定 app 選擇邏輯。

\## 這個架構對使用者的實際好處（更新）

\- 商業邏輯（parser、matcher、shutdown flow、action schema 安全性）與 `tests/unit/` 可以在此容器完整撰寫並執行驗證。
\- `tests/integration_windows/` 明確列出「使用者需要在自己 Windows 機器上驗證」的具體、安全的項目，範圍比 v1 更精確（例如新增了 interactive session 偵測、network profile 偵測）。
\- Interactive session 與 Task Scheduler 自動啟動的要求，直接解決了「API 顯示成功但桌面上看不到視窗」這類 v1 未考慮到的實際部署問題。
\- Firewall、rate limiter、process 關閉的職責邊界更清楚，未來維護或審查安全性時，每個檔案的責任範圍是明確的。
