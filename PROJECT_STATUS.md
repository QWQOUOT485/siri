# Project Status

這份文件是給新對話／新 coding agent 的「目前狀態摘要」。只記錄現在仍然有效的事實、驗收邊界與下一步；歷史 benchmark、bug 修復與 review 細節請看專門文件與 Git history。

## Current Phase

### 2026-09-24 Stage B final v1 pre-seal split pending independent PR review

Issue #53 is CLOSED. Frozen v6 remains the 3,600-row / 600-group source and
the independently accepted decision package remains separate audit evidence
under `artifacts/local_ai/stage_b/v6/`. Its 12 raw submissions cover all 3,600
candidates once: 3,600 accepted, zero rejected, needs_correction, conflict, or
pending. PR #56 merged reviewed head
`d3b71f9f02871f64191c924621f35f9bc4b2f9a4`; PR #57 merged the exact
decision package. V4 and v5 remain historical audit evidence.

Starting at exact main `7619baa4145b7525fad32a1bc62ec35afedd59aa`, the
new `artifacts/local_ai/stage_b/final_v1/` pool deterministically selects 500
whole groups / 3,000 rows and excludes 100 whole groups / 600 rows. Train is
300 groups / 1,800 rows, validation is 100 / 600, and held-out Stage B test is
100 / 600. The authoritative `validate_protocol_corpus()` passed the exact
class quotas, held-out language/slot gates, Stage A leakage check, and frozen
near-duplicate policy. Canonical final corpus SHA-256:
`a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13`.
Selection manifest SHA-256:
`973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a`;
split assignment SHA-256:
`84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37`;
authoritative corpus manifest SHA-256:
`297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c`;
provenance manifest SHA-256:
`d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d`.

`final_split_assigned=true` and `held_out_sealed=false`. The held-out split
has not been copied into a seal/evaluation location. Training, fine-tuning,
calibration, model compute, or Stage B finalist promotion remain unauthorized.
`LOCAL_SEMANTIC_MEMORY_ENABLED=false` and `LOCAL_AI_FALLBACK_APPROVED=false`
remain mandatory. This PR does not change runtime/Spotify work; Issue #59 is
separate and OPEN, as is Issue #52. The next gate is independent review of the
final-v1 pre-seal selection and split before any held-out sealing decision.
Focused Stage B selection/protocol/v6 review tests passed (128), the full unit
suite passed (597; two existing dependency deprecation warnings), and
`compileall -q app scripts tests` plus `git diff --check` passed.

### 2026-09-23 Issue #52 first four high-risk fixes — independent source review passed; live acceptance pending

The branch `codex/issue-52-first-four-fixes` starts from exact `main`
`bdd3468457ee2a2caa434d4c41091cafd8f45594` and changes only the first
four high-risk findings tracked in issue #52. Discovered/manual process-close
mapping now carries canonical executable paths; fixed system entries mark
name-only hints explicitly, and the existing service still refuses to close
system apps. Graceful close rechecks identity on its retained wait handle;
force close rechecks identity on the termination handle. Spotify clarification
uses closed positive selection forms. Fixed `.msc` tools resolve through the
Windows system-directory API and the launcher rechecks the trusted path.
Blocking `/action` and `/command` orchestration runs as sync FastAPI endpoints.

The four code fixes passed independent source review at implementation commit
`8b2ab5cef21e14d6bd87ca68c597bb3a05e8649e`; the reviewed code is unchanged.
Subsequent PR commits updated `PROJECT_STATUS.md` only. PR #54 is merged in
the required main baseline `68a71ed420467f1eebdf686f9268905af37e8146`.
Source/mock independent review passed. Live acceptance and installed-Agent
state must be read from the separate runtime acceptance report; this Stage B
task does not make a new Windows/Spotify/Siri runtime claim. Issue #52 and its
other findings remain open, with its checkboxes untouched.
`LOCAL_SEMANTIC_MEMORY_ENABLED=false` and `LOCAL_AI_FALLBACK_APPROVED=false`
remain unchanged.

### 2026-09-23 Stage B v4 historical workflow and audit evidence

PR #48's reviewed candidate-corpus head was exactly
`c5481a7d7d4b08f29b77e3ed65afaacd68a2ea85`; it is merged into `main` with
merge commit `04dadb6ef086534ab42f84b43fc40296e2cd7df4`. PR #50 was reviewed
at exact head `c59ae2b0aba1f0ddec42d02e28f01e40d02512f1` and is now merged into
`main` with merge commit `84c778b702d8ca469882aa5e06a6f3602ceffdcd`. The
independent-review workflow is now in `main`; its 12 deterministic review
packets of 300 rows each remain frozen. Review decisions remain zero at
workflow creation; that initial manifest count does not mean all 3,600 rows
have been semantically reviewed. Conflict-aware candidate aggregation exists,
but automatic conflict adjudication does not exist. The final 3,000 rows are
not selected, no final split exists, held-out data is not sealed, and training
is not authorized.
The implementation commit is `8d135e37d6a196bd2d1f630e51e8095d8c797613`.

Stage B v4 remains frozen as audit evidence, but is no longer eligible to
progress to final selection. It is an offline, deterministic, **unsplit** pool
of 3,600 provisional rows across 600 source groups and 32 template families.
Scope counts are 1,800 supported play, 1,260 supported semantic-unknown, 300
deterministic-only, and 240 safety-only. The source is synthetic, local,
provider-ID free, and Spotify/network independent. Packet 01 independent
semantic review and a follow-up corpus scan found corpus and generator defects,
tracked in issue #53. The scan found 6 zh-Hans rows containing Traditional
`著`. The earlier HANS contamination check was incomplete because detection
coverage depended on the known conversion mapping. Additional affected
generator families are English slash-delimited punctuation-loss surfaces;
Chinese deterministic-volume rows that became compound playback intent;
Chinese `unknown_missing_track` bare direct-play surfaces; and artificial
mixed-language surfaces combining `執行 run cmd`. These defects caused v4 to
be blocked; v5 was regenerated separately and later superseded by v6 after
the carrier-naturalness audit.
V4 review decisions are audit evidence only and must not be blindly reused
after regeneration because record text or hashes changed.
The offline production-alignment audit reports supported play/unknown as
1,800/1,260 eligible, deterministic-only/safety-only as 300/240 blocked, and
zero scope-contract mismatches. Leakage, exact duplicates, same-group near
duplicates, cross-group near duplicates, and cross-group exact duplicates are
zero.

The new
[`scripts/local_ai_stage_b_independent_review.py`](scripts/local_ai_stage_b_independent_review.py)
binds review to the literal reviewed source identities: candidate corpus
`c7e0a44b69d4033c960a8a1af20b0f4c71ad5674ece4b9a44953a1bea40e68d2`, entity
catalog `5deb5bd5a5c7d02b0f2eb864d0bfc4063161c62697d19fc2363f9d3e458b502a`,
generator config
`d263bd9ec97a897134e9fc5bf1121f16b86a84ff9a361d7046c68f10670d4435`, and
candidate manifest `a2ceef6205a3bf1a92c31a6ad12d34ac5a1d9aee467ace101532ba9ddfae074f`.
It fail-closes on self-hash, row schema, queue coverage, pending/unsplit flags,
and the 3,600-row/600-group source shape.

Review artifacts under
[`artifacts/local_ai/stage_b/review/`](artifacts/local_ai/stage_b/review/)
contain a self-hashed review manifest
`b59f493a25b34f5e1926321712229c94ea466dccc1bfaa53c4851107e63ed3c6` and 12
deterministic packets of 300 rows each. Every candidate ID appears exactly
once; packets are review allocations, not train/validation/held-out splits.
The packet hashes are unchanged:

```text
packet-01 9247d3fa2981fb896c38a8a9d61c8f76638a82e1309d605f39eb9afc88c8e902
packet-02 f6495bab08c86ece8effa565384ed208be0fb233e5a6a15afe26e15a324a5ca6
packet-03 f41b40ba64b83bfad1620ce0c071fbb8a15eefb90a5b3efa81419597177a72bc
packet-04 87f60aec287ca4b9d3071d240670a2081b1486d0003a57a04ed6e9d949d50202
packet-05 710785f922e529ea4467999a5825de57f8e2c18fef367ae3b33ef492abf2a8ed
packet-06 cd4b636a0d6f650555f22d7fe5dd42f5ff541e4717fc9a5cf2ae5b289ddf5b57
packet-07 a04c0358b68c75b470701bed6f3892498eabb3c69c557181ee1b662fc0f600a1
packet-08 280f5d14be348d9c430d9a766b10b974d4de2e6a831e219c0ca0ccef0ca1325f
packet-09 d63a10fbfbf579155e0f9fa5669ad2389598604c9f955cec1167e39fb3c20829
packet-10 cf6a68319a2172e7423aa77255da3f8e78b4b5a5c793d3c697c3293fa14044bf
packet-11 fe315f9592195bb81691e260a8f3a4fa6bcc6577367f0e5afcdce34c2e09650d
packet-12 2e46a81f007d5287e5d9c1653684f8c547159d55d12bf657e1a9b8ebf449783a
```

The review manifest now documents candidate aggregate states
`pending`/`accepted`/`rejected`/`needs_correction`/`conflict` and
`conflict_resolution.automatic=false`. Raw reviewer submissions remain
separate (`decision_count` and `raw_decision_counts`); candidate progress and
packet/language/scope/template-family/slot-mode dimensions count each
candidate once. The initial state is decision_count=0, reviewed=0, accepted=0,
rejected=0, needs_correction=0, conflict=0, pending=3,600. A same-reviewer
duplicate is still rejected; multi-reviewer disagreement becomes `conflict`.
Source-group health is aggregate-based: conflict wins, then
needs_correction, partial rejection, full acceptance only when all six rows
are accepted, otherwise partial review or unreviewed. No decision is
fabricated, propagated, adjudicated, or automatically resolved.

[`docs/LOCAL_AI_STAGE_B_INDEPENDENT_REVIEW_GUIDE.md`](docs/LOCAL_AI_STAGE_B_INDEPENDENT_REVIEW_GUIDE.md)
now targets the frozen v6 source identities while preserving the same review
workflow. The historical v4 and v5 manifests remain in their original
directories. This is **not** the final Stage B corpus: v4 and v5 cannot
progress to final selection. V6 reviewer decisions are now in `main` after
PR #57 merged; independent semantic review is complete with 3,600 accepted
decisions. No final 3,000-row selection exists, no split is assigned, held-out
data is not sealed, and no correction,
training, fine-tuning, inference, model compute, RX 9070 XT qualification,
deployment, production-parser authority, RAG, vector storage, embeddings,
Semantic Memory, Local AI fallback, or live Windows/Spotify/Siri/network
operation is authorized.

At the v4 workflow merge, the focused independent-review suite passed
(**24 tests**), the full unit suite passed (**496 tests**, 2 dependency
deprecation warnings), and `compileall -q app scripts tests` plus
`git diff --check` passed. These are historical results, not v6 validation.
`LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false` remain unchanged.

### 2026-09-21 Stage B pre-corpus gate / Memory RAG roadmap-only / compute not authorized

PR #44, which recorded the Stage B adaptation design, is merged into `main`
with merge commit `1ba8c335fd082acf891ea288483db543c1bd8b15`. The new
benchmark-only corpus infrastructure defines the closed Stage B record schema,
immutable span and optional-slot partition validation, split/leakage checks,
deterministic normalization, and manifest/hash reporting in
[`scripts/local_ai_stage_b_corpus.py`](scripts/local_ai_stage_b_corpus.py), with
focused coverage in
[`tests/unit/test_local_ai_stage_b_corpus.py`](tests/unit/test_local_ai_stage_b_corpus.py).
PR #45's reviewed correction was subsequently merged into `main` with merge
commit `cd53d9f1e5961a8a6246e00a73deea64c13fa452`. No real 3,000-row corpus has
been generated or committed.

The new pre-corpus gate freezes the separate authority/review/split/sealing
protocol, a standard-library character n-gram near-duplicate policy with its
synthetic calibration fixture and deterministic config hash, and a sanitized
separate provenance-manifest helper. Authoritative cross-split validation now
compares every relevant pair with exact Jaccard; retained SimHash metadata is
advisory only, and final protocol validation compares against the explicit
literal reviewed config hash rather than deriving the identity from the
mutable default.
It remains offline and benchmark-only; the real corpus-build protocol is recorded in
[`docs/LOCAL_AI_STAGE_B_CORPUS_BUILD_PROTOCOL.md`](docs/LOCAL_AI_STAGE_B_CORPUS_BUILD_PROTOCOL.md).
The new-branch source evidence is **57 focused tests** and **422 unit tests**
passed, with compileall and git diff checks passing; this remains source/unit
evidence only, not real corpus, compute, production, Windows, Spotify, Siri, or
model acceptance.

Memory RAG / Personal RAG is documented as future research in
[`docs/FUTURE_ROADMAP.md`](docs/FUTURE_ROADMAP.md) and `TASKS.md`. It is not
implemented; current structured Semantic Memory remains the high-trust layer,
retrieval remains untrusted evidence, and no vector storage, embeddings, or RAG
runtime exists.

Stage A is complete as an evidence inventory. The control plus all eight fixed
candidates have a reviewed run, a reviewed historical result, or an explicit
blocker. The final comparison and gate are recorded in
[`docs/LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md`](docs/LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md).

The formal result is **NO STAGE B FINALIST FROM RELEASED STAGE A MODELS**.
The control remains the only row with complete slot/full-semantic evidence
(95.24% full semantic, 100% play recall, 100% unknown recall, 0% conditional
expected-unknown false acceptance). Typed candidates are not equivalent to
that control. `laya` and `decider` remain architecture-only research
candidates; neither is a Stage B finalist. The separate design/corpus/training
plan is recorded in
[`docs/LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md`](docs/LOCAL_AI_STAGE_B_ADAPTATION_PLAN.md).
No adaptation, training, fine-tuning, or new model download has begun.

All typed routes expose no track/artist/album slots. `systemone-lite`,
`eve-rlcd`, `decider`, `Verdict-open-jev`, and
`open-jev-deberta-v3-large` accepted all 6 supported expected-unknown rows
(100% conditional false acceptance). `kev` failed supported-play quality.
`laya` retained 100% unknown recall and 0% conditional false acceptance but
failed play/Chinese quality and slot evidence. `system-one-open` remains
explicitly blocked because no released trained checkpoint was available.

Runnable non-control timing is CPU exploratory evidence because the RX 9070
XT backend is blocked. PR #42 is merged; this synthesis was prepared from the
reviewed base `ebdc257d2884649285418018c3d8c7493517bb91` for lineage context,
not as a current-main assertion. This infrastructure task does not change
production `app/`, deploy, run inference, train, download, run
Windows/Spotify/Siri, enable Semantic Memory, or enable Local AI fallback.
No compute authorization is granted; `LOCAL_AI_FALLBACK_APPROVED=false` remains
mandatory. laya and decider remain architecture-only research candidates, and
no Stage B finalist exists.

External Stage A weights remain under `D:\ai\ai`; migration SHA verification
passed; the recoverable backup `D:\ai\ai\_migration-backup-20260921` is kept;
the LM Studio control remains under its `D:\ai\ai\alphaduriendur\...` path.

## 2026-09-21 Independent Audit Hardening

This source hardening slice serializes the process-local Spotify token
lifecycle. Concurrent expired-token callers share one provider refresh;
explicit refresh remains forced unless an overlapping refresh has already
completed, in which case the waiter reuses it. Refresh failure clears only the
token used by that failed request, preserving a newer token saved by another
lifecycle.

Windows launcher, media, shutdown, and volume adapters no longer expose raw OS
exception details in remote operation results. Unit coverage also keeps
system-app close operations away from the process controller. Local AI tests
cover rejection of `localhost` and IPv6 loopback endpoints, and the command
route proves a successful deterministic action is executed exactly once even
when the fallback gate is enabled.

Source evidence recorded for this slice is **358 passed**; compileall, pip
check, and git diff check passed. No live Spotify calls or Siri voice E2E were
run. No Candidate Recovery semantics were changed, Semantic Memory was not
enabled, Local AI was not promoted, and no installed deployment was performed.

## v1.1 Candidate Recovery Phase 1B

This phase was explicitly scheduled after the v1.0 release handoff. The source
implementation now has a bounded, title-first Spotify recovery path and a
server-owned clarification continuation for `都不是` / `不是這些` / `換一批` /
`none of these`.

PR #35 final review passed and the reviewed source was merged to `main` with
merge commit `dde5e07130517dcaa67d9136ad222f748930545f`. No live Spotify,
Siri voice, or installed deployment acceptance was run as part of the merge;
Semantic Memory production enablement and Local AI promotion remain disabled.

- Public clarification remains at most three candidates; the internal recovery
  pool is capped at 20 candidates, each Spotify fetch is capped at 10 results,
  and the clarification store allows at most two successful user-visible
  recovery rounds shared by local and provider pages.
- Every successful recovery page atomically rotates the opaque clarification
  token and retires the old token as USED. Provider recovery has one in-flight
  authority branch per token; provider/auth failure leaves the usable context
  retryable without creating a second client-visible state. Recovery phrases
  are reviewed exact matches after normalization, not broad prefixes.
- The initial title-first provider fetch uses offset 0 and creates the initial
  clarification page without consuming continuation budget; only successful
  user-visible local/provider pages count, with provider continuation offsets
  progressing 10 then 20 before exhaustion.
- Recovery excludes Live/Concert variants, removes already-shown provider
  identities, preserves explicit album/version constraints, and never accepts a
  client URI, track ID, paging offset, or recovery cursor.
- Recovered candidates remain clarification-only evidence. No recovery result
  auto-plays and recovery alone never confirms Semantic Memory. Alias learning
  still requires server-owned candidate selection followed by successful
  playback.
- Current source/unit verification is complete: full pytest **336 passed**,
  compileall, pip check, and git diff check passed. The installed target was
  deployed with a reversible backup and 158/158 source-controlled non-protected
  files matched by SHA-256. Installed focused regressions (49 + 125 + 3 + 16)
  and full pytest **336 passed**; `/health` and OpenAPI both reported version
  `1.0.0`. The initial trusted candidate clarification and explicit playback
  passed, but the bounded `都不是` continuation returned
  `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a new token rotation, so
  live continuation acceptance remains blocked/unproven. Siri voice acceptance
  was not performed; Semantic Memory remains disabled and Local AI promotion
  remains unapproved. Evidence is recorded in
  [`docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md).

## Source of Truth

依序閱讀：

1. `docs/SECURITY.md` — 最高優先
2. `docs/SPEC.md`
3. `docs/ARCHITECTURE.md`
4. 任務相關文件：`docs/SPOTIFY.md`、`docs/API.md`、`docs/WINDOWS.md`、`docs/NETWORKING.md`、`docs/SIRI_SHORTCUT.md`
5. `TASKS.md`
6. `docs/TESTING.md`

`PROJECT_STATUS.md` 只描述目前 implementation / acceptance 狀態，不能覆蓋安全規格。

`docs/SOURCE_SPEC.md` 是唯讀歷史快照，不再是現行規格的 final arbiter。這個 authority blocker 已於 2026-09-19 由 `AGENTS.md` 與現行規格順序明確解決。

## v1.0 Scope Freeze

PR #29 的 docs-only scope-freeze merge 已由 GitHub 完成，merge commit 是
`c31a0ac0f59fa45a31a06991116845bebfb5b734`；這次合併代表 v1.0
implementation scope freeze accepted。PR #28 的 evidence-only merge commit
`f9f36695dfe092bca0cfeb21e8b15ea1044fd7c7` 是建立本次 freeze 時的
historical base，不是目前的 `main`。本次 scope freeze **只整理文件，不修改
implementation，也不新增 `spotify_continue` live retry 或 provider workaround**。

v1.0 retained scope、known limitation、proposed blockers 與 v1.1 deferred
items 的唯一整理見 [`docs/V1_SCOPE_FREEZE_2026-09-20.md`](docs/V1_SCOPE_FREEZE_2026-09-20.md)。
`spotify_continue` 仍是 **NOT ACCEPTED**；`LOCAL_SEMANTIC_MEMORY_ENABLED`
與 `LOCAL_AI_FALLBACK_APPROVED` 必須維持 `false`。

## Release-cut Verification (2026-09-20)

- Current source `main` full pytest: **306 passed**; `compileall` and `pip check` passed.
- Installed `D:\ai\windows-siri-agent` full pytest: **306 passed**; `compileall` and `pip check` passed. The checked non-sensitive source/version files have the same SHA-256 hashes as the current tree.
- The installed Agent was not running on `127.0.0.1:8000` during this inspection, so the current result is connection refused. PR #26's earlier installed-host `/health` HTTP 200 remains historical evidence and is not relabeled as a current live check.
- No live Spotify request or Siri voice E2E was run during this release-cut inspection; `spotify_continue`, semantic memory, and Local AI promotion boundaries remain unchanged.

## Final Release-cut Runtime Gate (2026-09-20)

The final installed runtime gate passed against reviewed `main`
`fbea4ba753fab6b672a6e4d24488381128df69bb` after PR #30 merged. The sanitized
evidence is recorded in [`docs/V1_RELEASE_CUT_RUNTIME_GATE_2026-09-20.md`](docs/V1_RELEASE_CUT_RUNTIME_GATE_2026-09-20.md).

- Installed Agent startup completed without a startup traceback.
- Current loopback `GET /health` returned HTTP 200 with only `ok`, `status`,
  `version`, and `uptime_seconds` fields.
- Effective installed settings were `semantic_memory_enabled=false`, Local AI
  `shadow`, and `local_ai_fallback_approved=false`.
- Release-relevant runtime/source parity was confirmed for `app/`, `scripts/`,
  `tests/`, `VERSION`, `requirements.txt`, and `.env.example`. Local `.env`,
  config, Spotify token, runtime data, logs, outputs/work, and `.venv` were
  preserved; no copy, delete, or overwrite was performed on them.
- No live Spotify request, Siri voice E2E, or `spotify_continue` retry was run.
  `spotify_continue` remains **NOT ACCEPTED**; Semantic Memory remains
  disabled; Local AI executable fallback remains unapproved; hosted CI remains
  absent.
- The pre-identity-cut source and installed runtime reported `0.1.0`; this is
  historical evidence for the gate above and does not prove installed `1.0.0`
  deployment, parity, or health.

## v1.0.0 Release Identity Cut (2026-09-20)

- Runtime release-cut gate: **PASSED** for the reviewed deterministic scope.
- Source product identity is now `1.0.0` in `VERSION`, `app.__version__`, the
  FastAPI metadata, and the runtime fallback.
- The annotated `v1.0.0` tag and GitHub Release are published at the reviewed
  merge commit `f1c201ddc2e9866ae46befd279c04c61921ad586`.
- Installed `1.0.0` deployment, source/runtime parity, `/health`, and OpenAPI
  identity acceptance **PASSED**.
- `spotify_continue` remains **NOT ACCEPTED**.
- `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false` remain unchanged.
- Hosted CI remains absent and is not being added in this PR.

## Final v1.0.0 Installed Identity Acceptance (2026-09-20)

- Reviewed source `main` is merge commit
  `71eb1bb74365cf69a88ae84239b4fa7d14f06f33`; PR #32 reviewed head was
  `7e25596980552bdfd81549ed58772304694a380c`.
- Source and installed full pytest both passed **307 tests**; focused identity
  tests passed **1** in each environment. `compileall` and `pip check` passed
  in both environments.
- Release-controlled source/installed parity compared **161 files** with zero
  missing files and zero SHA-256 mismatches.
- Installed loopback `/health` returned HTTP 200, version `1.0.0`, and only the
  bounded fields `ok`, `status`, `version`, and `uptime_seconds`. OpenAPI
  metadata version is `1.0.0`.
- Installed startup produced no traceback. Semantic memory is disabled; Local
  AI remains in `shadow` mode with `LOCAL_AI_FALLBACK_APPROVED=false` and no
  execution-authority promotion.
- No live Spotify calls, `spotify_continue` retry, Siri voice E2E, Candidate
  Recovery, Semantic Memory enablement, or Local AI promotion was performed.
- No implementation source or additional commit was created as part of the
  tag/release step.

## Security Invariants

下列界線不可因功能或 AI 擴充而放寬：

```text
Siri Text
→ Parser / guarded semantic interpretation
→ ValidatedAction
→ Trusted service / Catalog object
→ Adapter
```

- 不提供 remote shell / arbitrary PowerShell / CMD / Python execution。
- 使用者文字不得直接進 shell、subprocess、executable path 或 arbitrary URL。
- App launch 只能走 Trusted `AppEntry` / `LaunchSpec`。
- Windows Agent 只供 LAN 使用，不公開到 Internet。
- Shutdown 必須兩階段 confirmation token。
- Spotify token 只保存在 Windows 本機，不進 Shortcut、API response、log 或 Git。
- Local AI 永遠不是 execution engine。

## Completed and Accepted

### Core Windows Agent

- API key authentication、closed action schema、rate limiting 與 LAN/private-network boundary 已建立。
- Windows Agent 必須跑在目前登入使用者的 interactive session。
- 自動啟動採 Task Scheduler `At log on`。
- Application discovery / catalog / matcher / trusted launch flow 已建立。
- Graceful close 與 explicit force-close 為不同權限路徑。
- Shutdown two-step confirmation 已實作。
- `scripts/start.bat`、setup / firewall 流程與 diagnostics 已建立。

### Siri / Shortcut

- iPhone Shortcut → Windows Agent → Spotify 的基本控制路徑已實機通過。
- 指定歌曲播放已實機通過。
- Spotify clarification 已完成全語音 E2E：
  - Agent 回傳最多 3 個 trusted candidates + opaque token
  - Shortcut 保存 token
  - 第二輪語音選擇回送 token
  - server-side trusted candidate selection
  - 真實 Spotify 播放成功
- clarification 穩定流程已記錄在 `docs/SIRI_SHORTCUT.md`。
- 換 API key 後的 iPhone → Agent → Spotify playback regression 已通過。

### Spotify deterministic path

已支援：

- `spotify_resume`
- `spotify_play_track`
- `spotify_pause`
- `spotify_next`
- `spotify_previous`

目前 Siri acceptance scope 聚焦指定歌曲、播放、暫停與 clarification；下一首／上一首 closed actions 保留，但不列入目前 Siri acceptance scope。

Catalog / resolution 已有：

- Traditional / Simplified Chinese normalization
- Live / Concert / Tour / 演唱會 / 現場版本排除
- album / version hint
- trusted `SpotifyTrackRef`
- ISRC / duration 輔助 identity evidence
- confidence-based ambiguity handling
- 最多 3 個 clarification candidates
- popularity 僅作同分候選 tie-breaker
- saved/liked membership signal 僅用於 genuine ambiguity candidate ordering
- Top Tracks / Top Artists 目前已有固定 read-only adapter 與 server-side ambiguity ranking source slice
- Recently Played 目前已有固定 read-only adapter 與 server-side ambiguity ranking source slice；排序位於 Top Signals 之後、Search relevance 之前

Spotify OAuth 使用 Authorization Code with PKCE。真實帳號 token refresh 已驗證。

### Spotify saved/liked personalization slice

- `user-library-read` 已重新授權成功。
- 真實帳號已對三首使用者收藏歌曲讀回 `saved=true`。
- Library membership path 與 server-owned candidate boundary 已驗證。
- Library timeout / 401 / 403 / 429 / malformed response 會安全退回原 deterministic 順序。
- saved status 不進 AI、Shortcut 或一般 API response。

2026-09-20 current-source read-only acceptance probe 使用固定 20 個 bare-title queries，加上最多 50 個只在記憶體中使用的 Recently Played title seed；得到 20 個 genuine ambiguity、1 個 saved membership、0 個 library error、0 個 API error。Accepted case 中 saved candidate 從原始 Search position 1 提升到 final position 0，ambiguity 保留，沒有 playback 或 Library write。Recently Played seed 只用來擴大搜尋語料，saved probe 的 ranking client 只暴露 Search 與 Library membership，因此這是 saved-only reorder evidence。Slice A 已取得 bounded real-account acceptance，但不代表所有未來搜尋語料都一定有 saved reorder。可重跑方法位於 `scripts/spotify_saved_ranking_acceptance.py --from-recent`；詳細精確結果見 [`docs/SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_SAVED_RANKING_ACCEPTANCE_2026-09-20.md)。

### Spotify Top Tracks / Top Artists source slice

- 固定使用 `GET /me/top/tracks` 與 `GET /me/top/artists`，不接受 client endpoint、權重、Spotify ID 或 URI。
- Top track / artist 只在既有最多三個 trusted genuine-ambiguity candidates 內作排序 evidence。
- saved → top track → top artist → deterministic relevance → popularity 的順序只影響 candidate ordering；explicit artist / album / version 仍優先，ambiguity 不會變成自動播放。
- malformed 或失敗的 top lookup 只忽略該訊號；Library lookup 失敗時整體回到原 deterministic order。
- source/unit regression 已完成。2026-09-20 token 已重新授權並包含 `user-top-read`、`user-read-recently-played` 與 `user-library-read`；current-source read-only probe 使用固定 20 個 bare-title 加上 bounded in-memory 的 50 個 Top Track title seed，得到 34 個 genuine ambiguity、34 個可比對 raw candidate set、0 個 API/library error，並觀察到 1 個 `top_track` candidate 從原始位置 1 提升到 final position 0，ambiguity 保留，沒有 playback 或 Library write。Top Artist data 在 19 個 candidates 命中，但本次沒有獨立的 Top-Artist-only reorder，因此目前是 **partial acceptance**，不可宣稱 Top Artist standalone real-account acceptance。詳細結果見 [`docs/SPOTIFY_TOP_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_TOP_RANKING_ACCEPTANCE_2026-09-20.md)。

### Spotify Recently Played source slice

- 固定呼叫 `GET /me/player/recently-played`，只使用 server-owned track ID / artist name 作為既有最多三個 genuine-ambiguity candidates 的 ranking evidence。
- 排序順序維持 saved → top track → top artist → recent track → recent artist → deterministic relevance → popularity；explicit artist / album / version 仍優先，ambiguity 不會變成自動播放。
- response limit 固定 bounded；empty/malformed history、timeout、401、403、429、缺少 scope 或 optional method 都安全忽略並退回既有 deterministic ranking。
- source/unit regression 已完成；bounded probe 的 candidate/membership boundary 已修正為比對 server-owned URI set，不受個人化排序改變順序影響。2026-09-20 重新授權 token 的真實只讀 run 完成了 20 個 genuine ambiguity / 20 個 raw candidate set，Recently Played 命中 6 個 candidates，但沒有 saved/top signal 缺席且 recent-only 重排的 qualifying case；Search、Library、Top、Recently Played error 均為 0。Recently Played real-account acceptance 仍未通過，沒有播放或 Library write。精確證據見 [`docs/SPOTIFY_RECENT_RANKING_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_RECENT_RANKING_ACCEPTANCE_2026-09-20.md)。

### Spotify quota hardening and personalization read reduction

- source 已加入 bounded `SpotifyApiError.reason` parsing：只保留有限長度、固定字元形狀的 provider reason，不保存任意 provider message，也不把 token 放入 exception text、cache key 或 log。
- `SpotifyApiClient` 對明確 `QUOTA_EXCEEDED` 建立 provider-wide Web API cooldown；普通 429 只進入 bounded operation scope（Search、personalization、playback 分開），遵循 capped `Retry-After`（最多 3600 秒），missing / malformed / negative header 使用短 fallback cooldown，不 sleep、不 busy-loop、不自動重試。OAuth Accounts token endpoint 不受 Web API cooldown 阻擋，避免 401 refresh path 誤清除有效 refresh token。
- Top Tracks、Top Artists、Recently Played 使用 process-local bounded cache：fresh TTL 60 秒、stale refresh grace 30 秒、最多 12 個 signal entries；authorization context 以 process-local HMAC scope 隔離，raw token 不持久化，saved membership 不進這個 cache。cache 或 refresh 失敗時維持 deterministic ranking。
- 本次 source/unit targeted regression 為 84 passed；未呼叫真實 Spotify。Development Mode `429 / QUOTA_EXCEEDED / Retry-After=3600` blocker 與其他 provider conditions 仍限制 real-provider evidence，因此本次不宣稱 provider quota 或 real-account acceptance 已解決；mock/cache evidence 不等於 real Spotify acceptance，installed Agent alignment 仍是獨立 gate。
- 2026-09-20 PR #26 (`fix/spotify-403-provider-reason-20260920`) merged to `main` as `874a944`; bounded 403 observability exposes only the already-validated provider reason as `OperationResult.data.provider_reason`, omitting missing, malformed, or overlong values. User-visible 403 code/message, 429 retry data, and 401 refresh behavior remain unchanged. The reviewed non-secret source was staged to the installed Agent with a reversible backup; installed targeted Spotify/security tests passed (169), full pytest passed (306), compileall and pip check passed, and loopback `/health` returned 200. The first post-deployment read-only preflight found 1 usable non-restricted device but 0 active devices, so no command was sent; that earlier precondition gap is now superseded by the active-device acceptance recorded below.

### Deterministic Spotify shuffle / repeat / continue

- current source 已加入 closed actions：`spotify_shuffle_on/off`、`spotify_repeat_off/track/context`、`spotify_continue`；parser、`SpotifyService`、`SpotifyPlayer` 與 fixed Spotify endpoints `/me/player/shuffle`、`/me/player/repeat` 已接通。
- `spotify_continue` 僅執行 repeat off → resume，保留既有 shuffle，不讀取或重建 queue/context；401/403/429、無裝置與 repeat 失敗都維持 bounded fail-closed behavior。
- source/unit regression、security schema coverage、compileall、pip check 與 diff check 已完成；current-source full suite 是 **306 passed**。PR #26 post-deployment installed-host verification 另有 targeted Spotify/security **169 passed**、installed full pytest **306 passed**、compileall passed、pip check passed 與 loopback `/health` HTTP 200。先前 installed-host full suite 的 **303 passed** 僅為 earlier installed regression，不是 latest installed full suite；各 run 的既有 dependency deprecation warnings 仍分開看待。Installed source parity 已核對 157 個非敏感文件，disabled loopback `/health` smoke 通過。
- 2026-09-20 installed runtime bounded real Spotify acceptance：shuffle on/off、repeat track/context/off 均成功；`spotify_continue` 的 repeat-off 後 readback 保留 `shuffle=true` 且仍播放，但整體回應為 `SPOTIFY_FORBIDDEN`，因此 continue 仍是 **NOT ACCEPTED / partial evidence**，未重試。測試後已恢復起始的 shuffle=false、repeat=track 狀態。沒有遇到 429/`QUOTA_EXCEEDED`，也未做 Siri voice E2E；精確 evidence 見 [`docs/SPOTIFY_STATE_CONTROLS_RUNTIME_ACCEPTANCE_2026-09-20.md`](docs/SPOTIFY_STATE_CONTROLS_RUNTIME_ACCEPTANCE_2026-09-20.md)。
- 2026-09-20 bounded diagnosis：targeted source/mock differential 顯示 active device、無 transfer/queue/readback 時，empty-body `PUT /me/player/play` 已足以重現 fail-closed 403；同 endpoint 的 trusted named-track body 在 mock 與 installed historical log 均成功。官方契約允許 empty body，因此目前沒有足夠證據宣稱 source request bug。PR #26 的 safe/bounded observability 已 review、merge、部署；其後在使用者手動開啟 Spotify Desktop 後，installed Agent 的一次 read-only preflight 確認 1 個 usable non-restricted、1 個 active、selected active，且 repeat=off、shuffle=false、正在播放並有 item。唯一一次 `就一直播下去` command 仍回傳 `SPOTIFY_FORBIDDEN`，sanitized `provider_reason=UNKNOWN`；因 403 沒有 post-command readback、retry 或 transfer，沒有 429/`QUOTA_EXCEEDED`。這排除了「本次沒有 active device」作為充分解釋，但仍未證明 source bug 或 provider root cause；精確診斷見 [`docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`](docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md)。
- Installed alignment 保留 `.env`、local config、runtime data、Spotify token、logs、work/outputs；live token lifecycle 的正常 refresh 可能更新 token JSON，但沒有將 token 值寫入報告。Local AI controls requests 維持 `unsupported_domain`、未進 executable AI path。
- `spotify_seek`、`spotify_set_volume`、`spotify_like_current`、`spotify_unlike_current` 尚未在本批實作；Local AI allowlist 維持不擴張。

### Windows exact volume

`set_volume(volume_percent=0..100)` 已完成：

- closed action
- deterministic Chinese / English parser
- strict schema
- pycaw exact scalar setter
- exact setter 失敗時明確報錯，不用 media key 假裝精確百分比

已部署 Windows runtime 並以 `/action` 與 `/command` 驗證 exact scalar path。尚未做 Siri 語音 E2E 與獨立實體喇叭聽感驗收。

### Non-AI repair batch

已完成並有 regression coverage：

- Windows `SendInput` ctypes native layout
- shutdown expired-token error accuracy
- bounded relative-volume steps
- force-close duplicate PID deduplication
- Chinese normalization duplicate mapping cleanup
- configured-port `start.bat` diagnostics

其中安全的 Windows runtime / Spotify playback 路徑已有部署驗證；沒有為驗收而執行真實 shutdown 或 force-close。

## Local AI Status

### Current authority

Local AI 在 V1 **允許研究與 guarded integration，但 production fallback 尚未批准**。

現行 initial AI scope 只允許：

```text
spotify_play_track
unknown
```

以下維持 deterministic-only：

- playback controls
- clarification selection
- app control
- volume
- shutdown / force-close
- firewall
- system administration

### Implemented guarded path

```text
original Siri utterance
→ deterministic parser/resolver
→ deterministic eligibility gate
→ Local AI semantic retry
→ RawAIIntent
→ strict schema
→ deterministic grounding
→ GroundedAIIntent
→ AIPolicyGate
→ ValidatedAction
→ deterministic Spotify resolver
```

AI 不得選 Spotify URI / track ID、不得排序候選、不得直接播放，也不得接觸 clarification token authority。

Production LM Studio endpoint 必須是同機 loopback `127.0.0.1`；LAN endpoint 只可作隔離 benchmark / development。

### Evidence

最初 Phase 0.5 benchmark 未達門檻，因此不能當 production authorization。

後續 guarded fixed-corpus benchmark 與 resolver-seam hardening 已記錄：

- semantic accuracy 約 95.24%
- semantic-retry 100%
- deterministic-only / safety-only safe-unknown 100%
- observed false execution 0%
- observed post-grounding false acceptance 0%
- P95 約 200 ms
- source resolver / route regressions 已補齊

目前完整 source test run為 **306 passed**，另有 2 個既有 dependency deprecation warnings；本次 compileall、pip check、git diff check 也都通過。GitHub 目前沒有對 HEAD 提供 Actions workflow / commit status，因此這些是 repo 記錄的本機 source evidence，不等於 hosted CI。

新增的 `docs/LOCAL_AI_FAIL_CLOSED_MATRIX_2026-09-20.md` 與 `tests/unit/test_local_ai_promotion_matrix.py` 固定記錄 malformed output、connection/timeout、busy、oversized response、ungrounded track、invented optional slots 與 policy rejection 的 source/unit fail-closed 結果；targeted Local AI suite 為 **38 passed**。這補齊可重跑的本機矩陣，但不等於 live transport fault injection。

2026-09-20 的 loopback benchmark 三個模型、兩種模式的固定 corpus rows 已完成；完整 sanitized evidence 位於 `docs/LOCAL_AI_BENCHMARK_2026-09-20.md`，中斷過程仍保留在 `docs/LOCAL_AI_BENCHMARK_2026-09-20_PARTIAL.md`。本次未改變 production AI 設定，也沒有模型推薦：`qwen3.5-0.8b` 兩種模式均無法產生可解析 JSON；`qwen2.5-coder-1.5b-instruct` 兩種模式為 95.24% supported semantic、100% semantic-retry；`qwen3-4b` strict-schema row 已完成但為 28.57% supported semantic、16.67% semantic-retry。所有已完成 rows 的 observed false execution 與 post-grounding false acceptance 都是 0%，但這仍不是 Windows/Spotify/Siri acceptance。`LOCAL_AI_FALLBACK_APPROVED` 仍必須維持 `false`。

2026-09-20 real Windows Agent 已完成 loopback/shadow safe、hostile、resolver-retry、server-owned clarification probes；結果與 evidence boundary 記錄在 `docs/LOCAL_AI_SHADOW_ACCEPTANCE_2026-09-20.md`。live probe 沒有讓 AI 結果形成 executable action；malformed/timeout/busy/oversized/grounding edge cases目前以 source/unit evidence 為主，仍不是完整 promotion acceptance。該 shadow report 記錄的是 installed alignment 之前的 deployment snapshot；在後續 alignment 後，Installed Agent 的 Local AI / runtime source hash 已與 current tree 相同。read-only runtime 設定仍為 `shadow`、loopback、`qwen2.5-coder-1.5b-instruct`、2 秒、32 KiB、`LOCAL_AI_FALLBACK_APPROVED=false`，但 live transport fault matrix、Siri/real-account acceptance 與 exact executable-fallback promotion boundary 仍未完成，不能視為 exact promotion acceptance。`LOCAL_AI_FALLBACK_APPROVED` 仍必須維持 `false`。

新的 exact-evidence independent review 位於 `docs/LOCAL_AI_PROMOTION_REVIEW_2026-09-20.md`，結論為 **NO-GO**：live transport fault matrix、Siri/real-account acceptance 與 exact executable-fallback promotion boundary 尚未全部完成。新的 source/unit matrix 只補強 B1 的本機證據，沒有清除上述 live blocker。這不是模型推薦，也不改變 `LOCAL_AI_FALLBACK_APPROVED=false`。

2026-09-21 Stage A final synthesis is recorded in [`docs/LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md`](docs/LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md)。固定八個候選均有 reviewed result 或 explicit blocker，正式 gate 為 **NO STAGE B FINALIST FROM RELEASED STAGE A MODELS**。`laya` 與 `decider` 僅列為 architecture-only future research candidates，不是 finalist，沒有開始 adaptation/training。全部 typed routes 沒有 track/artist/album slots；非 control 的 RX 9070 XT backend 仍 blocked，CPU timing 不是 GPU qualification。Summary 使用既有 pilot、Batch 2A、Batch 2B evidence，沒有重跑 inference；`LOCAL_AI_FALLBACK_APPROVED=false`、production app 與 runtime authority 均未改變。

### Promotion gate

Production fallback 仍是 **NO-GO**。Stage A synthesis is now durable, but it
does not clear the separate production promotion gates:

1. current exact commit/model/config production-loopback shadow acceptance;
2. complete source/security regression and production-aligned fail-closed
   evidence;
3. real Windows Agent + Spotify safe/fail-closed cases and Siri voice
   acceptance where required;
4. separate independent promotion review with every live blocker cleared.

The Stage B gate is also closed for released candidates. A benchmark score,
architecture-only research recommendation, or source/unit result must never
set `LOCAL_AI_FALLBACK_APPROVED=true`.

## Local Semantic Recovery / Alias Memory

Phase 1 source implementation 已完成一個可 review 的 Slice 1–10 vertical implementation；2026-09-20 的 current-source Windows lifecycle harness 也已通過。current Phase 1 source 已以不覆蓋 secrets / local config / runtime data 的方式 staged 到 installed Agent，並完成 installed-host regression 與 disabled loopback smoke；這仍不是 real-world acceptance complete。詳細 evidence 與界線見 [`docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_RUNTIME_ACCEPTANCE_2026-09-20.md) 與 [`docs/SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md`](docs/SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md)。

Phase 1 原則：

- 只有 **exact confirmed non-conflicted alias** 可自動 canonicalize。
- confirmed learning 必須來自：
  ```text
  server-owned clarification candidate
  → explicit user selection
  → successful playback
  ```
- RapidFuzz / track-first / vector / AI 只可作 candidate/evidence，不能直接升為 execution authority。
- observation logging 預設關閉。
- DB corruption/unavailability 必須退回既有 deterministic behavior。
- 已建立 bounded domain models、schema-versioned SQLite persistence、RAM exact index、candidate-only RapidFuzz evidence、MemoryLearner、EntityRecoveryService、optional runtime config 與 aggregate-only metrics。
- `Sad overlxrd` 首次 trusted clarification + successful mocked playback 會建立 alias；第二次相同 artist text 走 exact RAM canonicalization；mocked playback failure 不會學習。
- source/security/concurrency regression 已納入完整 pytest suite；memory 預設仍 disabled，`LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY` 以 code-level false gate fail closed。
- current-source Windows harness 已驗證 disabled startup、fresh SQLite schema v1/FK、controlled enabled startup、restart persistence/RAM rebuild、corrupt/unavailable fallback、fuzzy candidate-only、conflict 與 8-way concurrent confirmation；exact lookup 1,000 次的 P50/P95 為 0.0174/0.0231 ms（temporary fixture，非 installed-host benchmark）。
- current-source staged runtime 已用真實 Spotify 帳號完成 token refresh、trusted canonical search、server-owned clarification selection、實際 playback、MemoryLearner confirmation、restart persistence 與第二次 exact hit（exact=1、fuzzy=0）；但 candidate 是由 canonical trusted search 控制性 seed，不能代替 ASR alias 的 first-occurrence candidate recovery。
- 真實 `Sad overlxrd` first-occurrence path（使用帳號實際存在的 `死亡不是生命的終點`）仍回傳 `SPOTIFY_TRACK_NOT_FOUND`、沒有 clarification candidates；installed Windows Agent 現已包含 current Phase 1 Semantic Memory modules/config，disabled runtime smoke 也確認未建立 SQLite artifact，但 iPhone Siri voice E2E 與 installed-host real Spotify acceptance 尚未執行，因此仍不可設定 `LOCAL_SEMANTIC_MEMORY_ENABLED=true`。詳細 follow-up 見 [`docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md`](docs/SEMANTIC_MEMORY_REAL_ACCEPTANCE_2026-09-20.md) 與 [`docs/SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md`](docs/SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md)。

規格位於 `docs/semantic_recovery/`。

## Not Yet Proven / Remaining Work

### v1.0 known limitation

1. **`spotify_continue` remains NOT ACCEPTED.**
   - The deterministic source path and source/unit coverage exist.
   - The one permitted active-device real run had a usable, non-restricted,
     selected active device but still failed closed with
     `SPOTIFY_FORBIDDEN` and sanitized `provider_reason=UNKNOWN`.
   - No retry, transfer, post-403 readback, 429, or `QUOTA_EXCEEDED` occurred.
     No source bug or safe workaround is proven; do not retry for scope freeze.
   - See [`docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`](docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md).

### Optional evidence gaps, not v1.0 blockers

2. **Spotify personalization acceptance**
   - Top Track has one real-account partial acceptance; Top-Artist-only
     reordering is not independently proven.
   - Recently Played source/unit evidence exists, but the bounded real-account
     run found no recent-only qualifying reorder case.
   - Keep explicit metadata priority and genuine ambiguity safety. Do not turn
     these optional ranking gaps into a v1.0 blocker.

3. **Exact Windows volume presentation**
   - Installed exact scalar behavior is verified; Siri voice E2E and an
     independent physical-speaker check remain unproven.

### Non-blocking known evidence / UX gaps

These remain valid evidence boundaries but are **not v1.0 release blockers**:

- Spotify OAuth callback behavior once showed a generic browser failure even
  though status and token storage succeeded; functionality works, but the UI
  and root cause remain unclarified.
- Clarification-store bounded-attempt and concurrency hardening is covered by
  source/unit tests, but a full Siri E2E was not rerun specifically because of
  that hardening.
- Spotify quota hardening and personalization cache have source/unit evidence,
  while real-provider evidence remains constrained by Development Mode quota
  and provider conditions. Mock/cache evidence is not real Spotify acceptance.

### Deferred / guarded work

4. **v1.1 Spotify features**
   - `spotify_seek`, Spotify device volume, and like/unlike current track are
     explicitly deferred; they are not missing v1.0 release blockers.

5. **Semantic memory and Local AI**
   - Phase 1 source and harness evidence remain guarded, but real runtime
     acceptance is incomplete. Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false`.
   - Preference memory remains deferred. Candidate Recovery Phase 1B is tracked
     above as the active, separately scoped source slice.
   - Local AI remains off/shadow; the independent promotion review is NO-GO and
     `LOCAL_AI_FALLBACK_APPROVED=false` must remain unchanged.

6. **Project infrastructure**
   - Hosted CI is not established; current source evidence remains local and
     must not be presented as hosted CI evidence.

### Current release-gate order

```text
1. Preserve docs/SECURITY.md invariants and closed deterministic authority.
2. Keep the accepted core Windows/Siri/Spotify flows and installed regression
   evidence intact at the release cut.
3. Keep spotify_continue as a documented fail-closed known limitation.
4. Keep semantic memory and Local AI fallback disabled.
5. Revisit only the explicit v1.1/deferred items through a separately scoped
   decision; do not add a live Spotify retry to this freeze.
```

## Installed Runtime

目前記錄的 Windows Agent 路徑：

```text
D:\ai\windows-siri-agent
```

Spotify redirect URI：

```text
http://127.0.0.1:8000/spotify/callback
```

不要把 API key、OAuth token、authorization code、PKCE verifier/state 或其他 secret 寫入本檔。

## Updating This File

任何改變真實專案狀態的工作，在結束前都要更新這份文件。

只保留：

- 現在的 phase
- 現在有效的 accepted facts
- 真實 acceptance boundary
- current blockers / not-yet-proven
- 下一步

歷史 debug 過程、舊 test count、已解決 blocker 與被取代的 next step，應留在專門報告或 Git history，不要再次累積到這份 handoff。
