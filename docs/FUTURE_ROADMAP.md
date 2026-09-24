# Future Roadmap

> Status: **Vision / Aspirational**
>
> 這份文件描述 Windows Siri Agent 未來可能發展的方向。它不是目前實作狀態、不是 release commitment，也不能覆蓋 docs/SECURITY.md、docs/SPEC.md 或 docs/ARCHITECTURE.md。
>
> 真正目前做到哪裡，請看 PROJECT_STATUS.md。真正要先做什麼，請看 TASKS.md。

## 1. Long-term vision

這個專案最初的核心是：

~~~text
Siri
→ Windows Agent
→ deterministic action
~~~

長期可以逐步發展成：

~~~text
Voice / Text / Phone / Desktop
        ↓
Intent understanding
        ↓
Personal semantic memory
        ↓
Context / policy / trust evaluation
        ↓
ValidatedAction
        ↓
Trusted capability
        ↓
Windows / Spotify / local services / future devices
~~~

最終方向不是「讓 AI 可以任意操作電腦」，而是建立一個：

**local-first、個人化、可學習、可驗證、權限封閉的 Personal Agent。**

核心原則：

~~~text
AI may interpret.
Memory may personalize.
Policy decides.
ValidatedAction authorizes.
Trusted adapters execute.
~~~

## 2. Three core development tracks

### Track A — Deterministic foundation

負責真正執行動作、Windows / Spotify integration、device/state control、strict validation、security boundary 與 reliability。

它是整個 Agent 的 authority layer。

### Track B — Local semantic memory

負責記住使用者已確認的 ASR 誤認、常用名稱、alias 與個人偏好，降低重複 clarification。

Memory 可以改善理解，但不是 execution authority。

### Track C — Local AI

負責 free-form language interpretation、parser failure recovery、entity-boundary recovery，以及未來可能的 summarization / query rewriting / planning assistance。

AI 可以提出語意，但不是 execution authority。

---

# Horizon 1 — Finish the Agent foundation

## 1. Spotify candidate personalization

讓 ambiguity candidate ordering 更符合使用者實際習慣：

~~~text
explicit artist / album / version
→ deterministic identity / Live filtering
→ saved / liked
→ Top Tracks / Top Artists
→ Recently Played
→ Spotify Search relevance
→ popularity-like tie-breaker
~~~

目標不是降低 clarification safety，而是讓真正可能的候選更常排在前面。

## 2. Full deterministic Spotify controls

補齊：

- shuffle on/off
- repeat track/context/off
- continue normally
- seek
- Spotify Connect volume
- like current track
- unlike current track

全部維持 closed actions。

## 3. Windows audio-device switching

例如：

~~~text
切到耳機
切到喇叭
把輸出換成 DAC
~~~

應使用 trusted device inventory，不接受 client 傳任意 device path。

## 4. Microphone controls

未來可加入 microphone mute/unmute、trusted input-device selection、meeting mode。

## 5. Display controls

例如 brightness、night light、display mode、monitor selection。

## 6. Better window management

例如：

~~~text
把 Spotify 放右邊
把 Chrome 最大化
把 Discord 移到第二螢幕
~~~

應由 server-side trusted window resolution 處理，不接受 client 提供 HWND/PID。

## 7. App focus instead of duplicate launch

當程式已經執行時，「開 Spotify」可以優先 focus trusted existing window，而不是再開第二份。

## 8. Better Windows state awareness

建立唯讀狀態：

- foreground app
- current audio device
- current volume
- display state
- Spotify playback state
- active trusted applications

這些 state 可幫助 deterministic command 做更合理的決策。

---

# Horizon 2 — Personal semantic memory

## 9. Confirmed alias memory

例如：

~~~text
Sad overlxrd
→ SASIOVERLXRD
~~~

只有經過 trusted clarification + successful action 才確認。

## 10. App nickname memory

例如：

~~~text
小綠
→ Spotify

工作瀏覽器
→ Edge
~~~

alias 最後仍要綁定 trusted AppEntry。

## 11. Device nickname memory

例如：

~~~text
桌面喇叭
→ trusted audio device A

耳機
→ trusted audio device B
~~~

alias 不能直接變成任意 Windows device identifier。

## 12. Personal vocabulary

建立 local dictionary，支援人名、歌手、遊戲、專案名稱、公司縮寫、品牌與使用者自己的暱稱。

## 13. Conflict-aware learning

如果同一 alias 被可信流程確認到不同 entity，系統應標示 conflict 並重新 clarification，而不是 last-write-wins。

## 14. Memory inspection UI

未來提供：

- 查看 learned aliases
- 查看 trust state
- 手動停用 alias
- 刪除 alias
- 查看 conflict

讓「系統學了什麼」對使用者透明。

## 15. Memory confidence aging

部分記憶可因久未使用、provider item 消失、app 被卸載、device 不存在而失效或降級。

## 16. Context-scoped aliases

不同 capability 的 alias 可以隔離，避免 Spotify、App、Device 等 entity namespace 互相污染。

## Memory RAG / Personal RAG — future research

目前的 Semantic Memory 是高信任、結構化的 alias/entity retrieval；它不是
conventional RAG，也不是向量資料庫或可執行的記憶代理。未來若研究 Personal
RAG，分層邊界應固定為：

~~~text
User utterance
    ↓
Deterministic parser / eligibility
    ↓
High-trust structured Semantic Memory
    ↓
Optional low-trust semantic/vector retrieval
    ↓
Bounded retrieved evidence
    ↓
Local AI semantic interpretation
    ↓
Grounding
    ↓
Policy
    ↓
ValidatedAction
    ↓
Trusted adapter
~~~

現有高信任 memory layer 專責：

- confirmed aliases；
- trusted entity mappings；
- conflict-aware mappings；
- provider-validated identity；
- deterministic exact lookup；
- bounded fuzzy candidate evidence。

未來低信任 retrieval layer 可以研究：

- embedding/vector retrieval 與 remembered vocabulary 的 semantic recall；
- 過去確認過的 phrasing、bounded user preferences、context/history summaries；
- project/entity vocabulary 與 query-rewrite evidence。

Retrieved memory 永遠只是 untrusted evidence。它不能：

- 變成 shell、PowerShell、CMD、executable path 或 arbitrary URL；
- 以 provider ID 直接授權 execution；
- bypass deterministic grounding 或 policy；
- 建立 `ValidatedAction`；
- enable Local AI fallback；
- 只靠 vector similarity 自動確認 memory。

Poisoned 或互相衝突的 memory 必須 fail toward clarification。敏感／私人記憶
預設留在本機；未來仍需要 memory inspection、deletion、disable 等使用者控制。

### Candidate implementation research — TencentDB Agent Memory

TencentCloud/TencentDB-Agent-Memory 可作為這個低信任 long-term-memory
layer 的候選實作，但不是目前已採用的 production dependency，也不得取代既有
Semantic Memory。

建議邊界：

~~~text
Current high-trust Semantic Memory
    confirmed alias / trusted entity / conflict handling
                    │
                    │ remains authoritative
                    ▼
Project-owned MemoryProvider interface
                    │
                    ├── NullMemoryProvider
                    └── TencentMemoryProvider
                             │
                             ▼
                     Tencent MemoryCore
                  conversation / facts /
                    scenes / profile
                             │
                             ▼
                    bounded recall evidence
                             │
                             ▼
                         Local AI
                             ↓
                        Grounding
                             ↓
                         Policy
                             ↓
                     ValidatedAction
~~~

研究時優先採 direct MemoryCore SDK / localhost HTTP integration，而不是先把
MemoryProxy 放進 Siri Agent 的主路徑。原因是 Python Agent 應由本專案自己控制
何時 recall、哪些欄位可進 prompt、最大 evidence 數量、timeout 與 fail-closed
行為。

整合必須透過本專案自己的 provider abstraction，避免 application code 直接依賴
Tencent 專用資料模型。第一版研究介面至少應能表達：

- bounded recall；
- conversation/fact capture；
- health / unavailable 狀態；
- explicit delete / disable；
- source/provenance metadata；
- timeout / cancellation；
- no-op fallback。

Tencent memory 的任何輸出都屬低信任 evidence。它不得：

- 取代 confirmed alias / trusted entity mappings；
- 自動提升 alias trust state；
- 直接提供可執行 Spotify URI、provider ID、Windows path、URL 或 command；
- bypass deterministic eligibility、grounding、policy 或 clarification；
- 建立或批准 `ValidatedAction`；
- 自動啟用 Local AI fallback；
- 因 vector/semantic similarity 而取得執行權限。

第一個 feasibility / PoC gate 應只驗證：

1. local standalone MemoryCore 是否能在 Windows 開發環境穩定啟動與停止；
2. Python SDK / localhost HTTP 是否能 bounded recall / capture，且 failure 不影響
   deterministic Agent；
3. local OpenAI-compatible model / embedding backend 相容性與 latency；
4. Traditional Chinese、Simplified Chinese、mixed-language 記憶召回品質；
5. stale memory、contradiction、dedup、provenance 與 deletion 行為；
6. restart persistence、schema/version migration、backup/restore；
7. sensitive-data redaction 與禁止 secrets/provider IDs 進入記憶；
8. memory poisoning / prompt-injection evidence 是否能被限制在低信任層；
9. disabling/removing the provider 是否能完全退回現有 behavior；
10. pinned reviewed version 是否可重現，不依賴 rolling latest/pre-release。

只有 PoC、security review、failure-mode review 和 acceptance evidence 都通過後，
才可以另外開 production-integration scope。即使未來正式採用，TencentDB Agent
Memory 仍只是 Personal RAG / long-term context implementation；本專案自己的
Semantic Memory、grounding、policy 與 ValidatedAction authority 保持不變。

本項目前只屬 FUTURE RESEARCH / ROADMAP：不實作 vector storage、embeddings、
RAG runtime，也不改變 `LOCAL_SEMANTIC_MEMORY_ENABLED=false` 或
`LOCAL_AI_FALLBACK_APPROVED=false`。

### JEV retrieval / selection trace UI — future observability

未來 JEV / Personal Agent 進行 memory、document、entity 或其他 bounded data
retrieval 時，應提供一個可選的本機可視化介面，讓開發者可以直觀看到「資料如何
被找出來、如何被淘汰、如何排序，以及最後哪一筆 evidence 被選中」。

第一版可視化至少應能呈現：

- 原始 query、normalized query 與 bounded extracted fields；
- 各 retrieval source，例如 high-trust Semantic Memory、future Personal RAG、
  local document index 或其他明確 allowlisted data source；
- candidate recall pool 與各階段候選數量；
- filter / dedup / conflict / rerank 等選擇階段；
- 每筆 candidate 的 bounded score breakdown、provenance 與 selected /
  rejected 狀態；
- 被淘汰 candidate 的 machine-readable reason code；
- 最終 selected evidence 的醒目標示；
- 每個 retrieval / filter / rerank stage 的 latency；
- 完整但 bounded 的 decision trace，方便重現 retrieval bug。

概念流程：

~~~text
User query
    ↓
Normalize / extract
    ↓
Retrieve candidates
    ↓
Filter / deduplicate / conflict checks
    ↓
Rerank
    ↓
Bounded evidence selection
    ↓
Local AI interpretation
~~~

UI 應清楚區分：

~~~text
retrieved candidate
≠ trusted fact
≠ selected evidence
≠ ValidatedAction
≠ execution authority
~~~

這個 trace panel 的主要用途是 observability、debugging、evaluation 與 future
dataset/retrieval research，而不是讓使用者從 UI 任意提升 candidate trust 或直接
授權 execution。

安全與隱私邊界：

- 預設只顯示 bounded / sanitized trace，不 dump 整個 process environment、
  secrets、OAuth token、API key、private filesystem path 或 provider credential；
- provider ID / URI 若未來需要顯示，只能視為 server-owned metadata，不能因 UI
  顯示而取得 execution authority；
- sensitive memory / personal history 應支援 redaction，並允許完全停用 trace；
- trace data 不得自動成為 fine-tuning data；
- frozen benchmark / held-out labels 不得因 visualizer 而暴露到 training、
  calibration、prompt construction 或 selection logic；
- visualizer 不得改寫 candidate、score、ranking、memory trust state 或
  `ValidatedAction`；
- UI 關閉、故障或未安裝時，retrieval pipeline 必須維持相同行為。

未來若要實作，可先從 read-only developer panel 開始：

1. query / slot view；
2. candidate table；
3. filter / rerank stage timeline；
4. selected evidence detail；
5. rejection reason / score breakdown；
6. sanitized exportable trace for offline debugging。

之後若 JEV 擴展到更大的 long-term-memory / Personal RAG / local document
retrieval，這個介面可作為統一的「retrieval observability」層，而不是為每一種
memory provider 分別做不可比較的 debug UI。

#### Compact widget / Scriptable-style companion

除了完整 local web dashboard，也可研究一個較小的 **read-only companion widget**，
用卡片方式即時顯示最近一次 JEV retrieval 的摘要，例如：

~~~text
Query
候選 12
   ↓
Filter 5
   ↓
Top 3
   ↓
Selected 1

✓ 最終選中
來源 / score / reason
~~~

手機端可採類似 Scriptable widget 的呈現方式：小卡片、定時刷新、狀態一眼可讀；
完整候選、score breakdown 與 decision trace 則留在 localhost / LAN dashboard。

UI 風格參考，不代表 production dependency，也不直接複製第三方 implementation：

- https://raw.githubusercontent.com/poychang/scriptable-widgets/main/widgets/codex-reset-checker/codex-reset-checker.js
- https://blog.poychang.net/codex-reset-checker-scriptable-widgets/

建議資料流：

~~~text
JEV / retrieval pipeline
        ↓
sanitized read-only trace event
        ↓
bounded local trace store
        ↓
localhost dashboard API
        ├── full visual trace
        └── optional compact phone/widget view
~~~

Widget / trace API 必須保持 read-only：不能用 client input 改寫 candidate、score、
selection、memory trust state 或 `ValidatedAction`；手機端優先顯示 sanitized summary，
而不是把 sensitive/raw memory 全量同步出去。

本項目前只屬 FUTURE RESEARCH / ROADMAP，不代表已實作 JEV retrieval、
Personal RAG runtime、dashboard 或任何新的 execution authority。

---

# Horizon 3 — Safer Local AI

## 17. Production-safe semantic retry

Rule parser / resolver 不確定時：

~~~text
deterministic failure
→ Local AI semantic retry
→ grounding
→ policy
→ existing deterministic resolver
~~~

AI 只負責語意解讀。

## 18. Query rewriting

AI 可以把自然語句轉成 bounded structured search hints，但真正 track selection 仍由 deterministic Spotify resolver 決定。

## 19. Multi-model routing

未來可能採：

~~~text
small fast model
→ if uncertain
larger local model
~~~

整條 chain 仍要通過 deterministic grounding / policy boundary。

## 20. AI health monitor

Agent 可檢查：

- LM Studio 是否正常
- expected model 是否載入
- latency 是否異常
- malformed-output rate
- timeout rate

異常時退回 deterministic path。

## 21. Continuous shadow evaluation

Production 中 AI 可以在符合資格的 request 上產生 shadow interpretation，和最後 trusted result 比較並記錄 sanitized metric，但不執行。

## 22. Personal semantic correction corpus

將 ASR text → clarification → confirmed entity 轉成 local evaluation corpus，先用於 benchmark，而不是直接 fine-tune。

## 23. Optional local fine-tuning / LoRA

只有在資料量、品質、安全評估都足夠後，才考慮 LoRA / instruction tuning / entity-extraction tuning。

Fine-tuned model 仍必須通過與 base model 相同或更嚴格的 policy gate。

### 23.1 Model-size strategy

這個專案不應以「參數越大越好」作為模型選型原則。Local AI 的第一個 production-oriented role 很窄：

~~~text
eligible Siri utterance
→ semantic interpretation / entity-boundary recovery
→ strict JSON/schema
→ deterministic grounding
→ policy gate
→ existing deterministic resolver
~~~

因此模型大小應由 **固定 corpus 的實測品質、structured-output 穩定性、延遲與安全結果** 決定，而不是單看 parameter count。

目前已有的 benchmark evidence 顯示：

- `qwen2.5-coder-1.5b-instruct` Q4 在既有 fixed corpus 上達到 100% JSON/schema、95.24% supported semantic、100% semantic-retry，P95 約 200 ms。
- 較大的 `qwen3-4b` 在同一類任務上反而明顯退化。
- 因此「更大的模型」目前沒有自動取得 promotion priority。
- 上述結果只是 benchmark evidence，不代表 production fallback 已批准；現行 promotion gate 仍適用。

建議的 model-size progression：

~~~text
Stage A — 1.5B class
current baseline / fast semantic parser
↓
Stage B — 1.5B–4B class
first LoRA / instruction-tuning experiments
↓
Stage C — 7B/8B class
only when the Agent scope expands into genuinely broader
multi-domain interpretation, richer context, or bounded planning
↓
Stage D — 14B+ class
only if measured evidence shows smaller tiers cannot meet
quality requirements and latency / memory cost remains acceptable
~~~

換句話說，未來模型升級應該由「任務變難」或「benchmark 證明現有 tier 不夠」觸發，而不是因為有更大的模型可用。

### 23.2 First fine-tuning target

第一個 fine-tuning project 應保持單一、可驗證的目標：

**改善 Spotify named-track semantic parsing / entity extraction / semantic retry，不擴張 execution authority。**

訓練樣本可包含：

- `spotify_play_track` 的自然語句變體
- track / artist / album entity-boundary ambiguity
- Traditional / Simplified Chinese variants
- ASR-like noise 與常見誤分詞
- colloquial artist / song phrasing
- 必須輸出 `unknown` 的 negative samples
- malformed / unsupported / deterministic-only requests 的拒絕樣本

第一個 fine-tuned model 不應加入 app control、shutdown、force-close、firewall、arbitrary Windows operations 或 client-supplied execution target。

### 23.3 Data discipline

Personal semantic correction data 可以逐步累積成 tuning candidate corpus，但不能把「記憶」直接等同於「訓練資料」。

進入 fine-tuning 前至少要區分：

~~~text
raw local observations
→ reviewed / sanitized candidate examples
→ training split
→ held-out validation split
→ frozen benchmark / acceptance split
~~~

要求：

- 不把 API key、OAuth token、private path、Spotify URI/ID、logs 中的秘密放入 dataset。
- 不把固定 benchmark 的答案直接洩漏進 training split。
- confirmed alias / clarification evidence 必須先轉成 bounded semantic example。
- negative examples 應占有足夠比例，避免 fine-tune 後過度猜測。
- training corpus version、hash、base model、adapter config 與 prompt/schema 都應可追溯。

### 23.4 Base vs fine-tuned evaluation

任何 fine-tuned candidate 都必須和未微調 baseline 在**完全相同**的 evaluation harness 下比較。

至少比較：

- transport success
- JSON parse / strict-schema success
- supported semantic accuracy
- semantic-retry accuracy
- deterministic-only safe-unknown
- safety-only safe-unknown
- false execution
- post-grounding false acceptance
- P50 / P95 latency
- malformed-output rate
- timeout / failure behavior

第一個 LoRA 的成功標準不是「感覺比較懂我」，而是：

~~~text
same frozen corpus
+ same schema / grounding / policy
+ measurable semantic improvement
+ no safety regression
+ acceptable latency
~~~

如果 fine-tuned model 只提升少量 wording coverage，卻增加 malformed output、false acceptance 或 latency，應保留 base model。

### 23.5 Hardware / training scope

第一階段 tuning 應刻意設計成可在單張約 12–16 GB VRAM 的 consumer GPU 上完成，例如 QLoRA / parameter-efficient tuning。

不應為了第一個 personal model：

- 假設不同電腦的 VRAM 可以直接相加
- 依賴 mixed-vendor cross-host distributed training
- 引入複雜 multi-node training stack
- 先追求 14B / 32B full fine-tune

如果未來真的需要更大模型，應先由 benchmark 證明能力缺口，再決定升級硬體或使用更大的 local model。

### 23.6 Long-term model role

長期模型可以逐步從：

~~~text
semantic parser
→ semantic recovery model
→ contextual interpreter
→ bounded planner
~~~

但每提升一層能力，都必須維持：

~~~text
model proposes meaning / plan
→ deterministic grounding
→ policy
→ closed ValidatedAction(s)
→ trusted adapters
~~~

即使未來使用 7B、14B 或更大的 personal model，也不應因模型更強而繞過既有 security architecture。

---

# Horizon 4 — Contextual Agent

## 24. Short-term conversational context

例如：

~~~text
播放晴天
→ clarification / playback

換原版
~~~

第二句可以理解為針對目前 Spotify context。

Context 必須短效、bounded、可失效。

## 25. Current-object references

支援安全代詞：

~~~text
這首
這個程式
剛剛那個
目前這個
~~~

只能解析到 server-owned current object。

## 26. Scene / mode system

例如 Work mode、Gaming mode、Movie mode。

Scene 可以包含 trusted apps、preferred audio、volume、display settings 等，但必須是 server-owned configuration，不接受 client arbitrary scripts。

## 27. Conditional automation

例如：

~~~text
如果我開 Steam
→ 切到耳機
→ 開 Discord
~~~

這需要 closed triggers + closed actions 的 automation policy layer，而不是 AI 生成 script。

## 28. Time-aware routines

例如睡前模式、工作開始模式、固定時間的 local routine。

需要 explicit opt-in、local scheduler、bounded actions 與 visible configuration。

---

# Horizon 5 — Local Personal Agent platform

## 29. Local web dashboard

LAN / localhost dashboard 可查看：

- Agent health
- trusted apps
- Spotify state
- Local AI status
- semantic memory
- recent bounded command results
- latency metrics
- clarification statistics
- security status
- integration health

高風險設定仍應需要本機操作或 explicit confirmation。

## 30. Capability platform

長期可以把功能抽象為 capability：

~~~text
Windows Apps
Windows Audio
Windows Display
Spotify
Semantic Memory
Local AI
Automation
Notifications
Documents
Future smart-home/device adapters
~~~

所有 capability 必須遵守：

~~~text
Untrusted Input
→ Interpretation
→ Policy
→ ValidatedAction
→ Trusted Capability
→ Adapter
~~~

未來增加功能時，不需要讓 AI 或 client 取得底層 unrestricted authority。

---

# Beyond the first 30

## Cross-device agent

未來 iPhone 不只送指令，也可以安全讀取 current track、PC status、current app、Agent health、pending clarification。

## Local document assistant

對明確 allowlisted folder 提供 local search、document summary、question answering、project knowledge retrieval。

AI 只能讀被授權資料來源，不能因此取得任意 filesystem access。

## Notification intelligence

建立 Windows notification adapter，讓系統可以在明確授權下分類、摘要與語音讀出通知。

## Local knowledge graph

將 apps、aliases、devices、Spotify entities、scenes、trusted local resources 形成受控 entity graph，成為未來 Personal Agent 的 semantic layer。

## Plugin / capability SDK

未來 capability 可以宣告：

- closed actions
- input schema
- permissions
- confirmation requirements
- adapter
- tests

而不是 plugin 任意取得 Python / shell execution。

## Multi-user profiles

如果同一台 Windows 有多人使用，memory、Spotify auth、aliases、scenes、runtime state 應依使用者隔離。

## Offline-first privacy mode

長期理想：

- core command execution fully local
- memory local
- AI local
- no cloud LLM requirement
- external traffic only to explicit providers such as Spotify

這可以成為整個專案的重要產品特色。

---

# Possible version themes

這不是正式 release commitment，只是方便思考。

## V1 — Reliable Siri-to-Windows Agent

- trusted Windows actions
- Spotify
- Siri Shortcut
- clarification
- security boundary

## V1.5 — Personalized Agent

- candidate personalization
- semantic alias memory
- richer deterministic controls
- better Windows state awareness

## V2 — Local Intelligent Agent

- approved Local AI semantic retry
- short-term context
- query rewriting
- memory + AI cooperation
- dashboard

## V3 — Personal Automation Platform

- scenes
- routines
- conditional automation
- capability framework
- cross-device state

## V4 — Local Personal Agent

- richer context
- local knowledge graph
- documents / notifications
- multi-device orchestration
- optional fine-tuned personal model

---

# Architectural north star

~~~text
                  ┌──────────────────┐
Voice / Text ────▶│ Interpretation   │
                  │ Rules / Memory   │
                  │ Local AI         │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Policy & Trust   │
                  │ Grounding        │
                  │ Confirmation     │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ ValidatedAction  │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Trusted          │
                  │ Capabilities     │
                  └────────┬─────────┘
                           │
                           ▼
              Windows / Spotify / Future
~~~

長期設計原則：

1. **Understanding is not authority.**
2. **Memory is not authority.**
3. **AI confidence is not authority.**
4. **External IDs are not trusted because the client supplied them.**
5. **Every executable behavior converges to a closed validated action.**
6. **High-risk operations remain deterministic and confirmation-gated.**
7. **The system should degrade safely when AI, memory, provider APIs, or optional components fail.**
8. **Personalization should improve ranking and understanding before it increases autonomy.**
9. **Real-world acceptance must remain distinct from source/tests/spec completion.**
10. **The Agent should become more useful without becoming a remote shell.**

---

# What success could look like

理想中的使用體驗：

~~~text
使用者：
「幫我開工作模式，然後放點我最近常聽的輕鬆音樂。」

Agent：
- resolves 工作模式 from trusted local scene
- focuses/opens trusted work apps
- applies bounded audio/display settings
- uses personal Spotify signals to prepare trusted candidates
- asks clarification only when genuinely ambiguous
- executes only validated actions
~~~

下一次：

~~~text
使用者：
「播放 Sad overlxrd 那首。」

Agent：
- recognizes a previously confirmed local alias
- resolves it without calling AI
- uses the normal deterministic Spotify resolver
- plays the trusted result
~~~

再遇到真正的新語意：

~~~text
使用者：
「放那個歌名裡有死亡是生命什麼的。」

Agent：
- deterministic parser cannot confidently resolve it
- memory has no exact trusted alias
- guarded Local AI proposes bounded semantic slots
- deterministic grounding verifies them
- Spotify resolver finds trusted candidates
- ambiguity still asks the user
~~~

長期目標是：

**更懂使用者，但不因為更聰明而失去控制。**

---

# Roadmap governance

這份文件可以自由「畫大餅」，但真正進 implementation 前，每一項仍必須：

1. 有明確 user value。
2. 有 closed action / trusted-data design。
3. 通過 security review。
4. 寫 active spec。
5. 有 unit/security tests。
6. 必要時有 Windows / Spotify / Siri real acceptance。
7. 更新 PROJECT_STATUS.md。
8. 只有驗收完成後才算 implemented。

未進入 active spec 的內容，一律視為 **future idea**，不得因為存在於本文件就自動視為授權實作。
