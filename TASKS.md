# Current Tasks

## Current Milestone

**v1.1 Candidate Recovery Phase 1B — source merged; continuation runtime gate not accepted**

The v1.0.0 runtime release-cut gate and installed identity acceptance passed for
the reviewed deterministic scope. The v1.0.0 release commit and annotated tag
target is `f1c201ddc2e9866ae46befd279c04c61921ad586`, after evidence-only PR
#33 merged.
The annotated `v1.0.0` tag targets that commit, and the GitHub Release
`Windows Siri Agent v1.0.0` is published. Source and installed identity report
`1.0.0`; the release evidence records source/installed full pytest at 307
passed, 161 release-controlled files with zero missing or SHA-256 mismatches,
and installed `/health` plus OpenAPI version `1.0.0`.

Core Siri → Windows → Spotify playback and clarification are functional. The
v1.0 scope freeze was accepted when PR #29 merged into `main`; its retained
scope, `spotify_continue` known limitation, proposed blockers, and v1.1
deferrals remain recorded in `docs/releases/v1/V1_SCOPE_FREEZE_2026-09-20.md`. Candidate
Recovery Phase 1B source implementation was merged to `main` by PR #35
(`dde5e07130517dcaa67d9136ad222f748930545f`). The tested current `main` is
`fcb955a43b0590636f776ffc31e7ca71897114f2`.

Installed alignment and regression passed, and the initial real trusted
clarification plus explicit playback passed. The bounded continuation runtime
gate remains **BLOCKED / NOT ACCEPTED**: live `都不是` returned
`SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a next page or token
rotation. This does not prove a source bug. Siri voice acceptance was not
performed; Semantic Memory remains disabled; Local AI fallback remains
unapproved. The detailed evidence boundary is recorded in
`docs/features/spotify/evidence/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.

## v1.0.0 Release Identity Cut

- Runtime release-cut gate: **PASSED** for the reviewed deterministic scope.
- Source product version is now `1.0.0`.
- Installed `1.0.0` deployment, source/runtime parity, `/health`, and OpenAPI
  identity acceptance **PASSED**.
- The annotated `v1.0.0` tag targets
  `f1c201ddc2e9866ae46befd279c04c61921ad586`, and the formal GitHub Release
  `Windows Siri Agent v1.0.0` is published.
- Evidence-only PR #33 is merged as
  `f1c201ddc2e9866ae46befd279c04c61921ad586`.
- `spotify_continue` remains **NOT ACCEPTED**.
- `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false` remain unchanged.
- Hosted CI remains absent and is not being added in this docs-only change.

## v1.0 Scope Freeze Decision

- Retain the Windows security boundary, API key/LAN-only operation, trusted app
  control, shutdown confirmation, Windows volume, Spotify basic/named-track
  playback, clarification, shuffle/repeat, and installed regression evidence.
- Keep `spotify_continue` deterministic and fail-closed, but mark it
  **NOT ACCEPTED** because the active-device real run returned
  `SPOTIFY_FORBIDDEN` with sanitized `provider_reason=UNKNOWN`.
- Treat Top-Artist-only and Recently-Played-only acceptance gaps as optional
  evidence, not v1.0 blockers.
- Defer seek, Spotify device volume, like/unlike, preference memory, and broader
  Local AI authority to a separately approved scope. Candidate Recovery Phase
  1B source is merged via PR #35; its installed/runtime continuation gate is a
  separate acceptance boundary and remains not accepted.
- Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
  `LOCAL_AI_FALLBACK_APPROVED=false`.

## Before Coding

1. Read `AGENTS.md`.
2. Read `PROJECT_STATUS.md`.
3. Read `docs/core/SECURITY.md`.
4. Read `docs/core/SPEC.md` and `docs/core/ARCHITECTURE.md`.
5. Read task-specific docs:
   - Spotify → `docs/features/spotify/SPOTIFY.md`
   - playback controls → `docs/features/spotify/PLAYBACK_CONTROLS.md`
   - Local AI → `docs/local_ai/architecture/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` plus current SECURITY / ARCHITECTURE rules
   - semantic recovery → `docs/features/semantic_memory/recovery/`
   - Windows adapters → `docs/core/WINDOWS.md`
   - API → `docs/core/API.md`
   - Siri → `docs/features/siri_shortcut/SIRI_SHORTCUT.md`
6. Before finishing, run relevant tests per `docs/core/TESTING.md`.
7. If real project state changed, update `PROJECT_STATUS.md`.

## Post-freeze Queue

### P0 — Preserve safety and release evidence

- No user text may become shell/subprocess/PowerShell/CMD/executable
  path/arbitrary URL.
- Local AI remains off/shadow and semantic memory remains disabled.
- Clarification tokens and trusted Spotify IDs remain server-owned.
- Do not turn candidate-quality signals into automatic execution authority.
- Do not delete security regressions to make tests pass.
- Keep source/unit, installed, and real-device evidence explicitly separate.

### P1 — v1.1 candidates and current Phase 1B slice

- `spotify_seek`
- Spotify device volume
- `spotify_like_current` / `spotify_unlike_current`
- Candidate Recovery Phase 1B — **source merged via PR #35; continuation runtime
  acceptance BLOCKED / NOT ACCEPTED**
- preference memory
- broader Local AI authority or executable fallback

The other listed items require a separately scoped v1.1 decision and branch.
Phase 1B source/unit work is merged to `main`. Installed alignment/regression
and the initial trusted clarification plus explicit playback passed, but the
bounded continuation returned `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED`
without a next page or token rotation, so continuation remains
**BLOCKED / NOT ACCEPTED**. Installed/runtime evidence is not Siri voice
acceptance; Siri voice acceptance was not performed.

### P2 — Optional evidence, not a v1.0 blocker

- Top-Artist-only genuine-ambiguity reordering
- Recently-Played-only genuine-ambiguity reordering
- Siri voice / independent speaker acceptance for exact Windows volume

Keep Spotify relevance/popularity and personalization signals as bounded
candidate evidence only.

### P2.5 — Local decision-model / Jev-style benchmark research

Evaluation-only comparison of small local typed-decision / System-One-style
models against the existing `qwen2.5-coder-1.5b-instruct` strict-schema
control. Production Local AI authority remains unchanged, and
`LOCAL_AI_FALLBACK_APPROVED=false`.

- Common target hardware: RX 9070 XT 16 GB where supported.
- Stage A evaluates released models and inference methods as-is.
- Stage B may adapt at most 2–3 evidence-backed finalists.
- Compare semantic quality, false acceptance/safety, calibration, latency,
  memory use, and Chinese/mixed-language behavior.
- Keep MiniMind as a pinned **training-method reference only** for future SFT,
  distillation, checkpoint/resume, and later Agentic-RL research. It is not a
  ninth candidate, finalist, training authorization, or production dependency.
  See [MiniMind training-method reference](docs/local_ai/training/LOCAL_AI_MINIMIND_TRAINING_REFERENCE.md).
- Full candidate set, hardware protocol, metrics, fairness rules, and
  promotion boundary: [dedicated benchmark plan](docs/local_ai/benchmark/LOCAL_AI_DECISION_MODEL_BENCHMARK_PLAN.md)

### P2.6 — Memory RAG / Personal RAG (future research)

- Keep current structured Semantic Memory as the high-trust exact/entity layer;
  it is not conventional RAG.
- Future vector/semantic retrieval may provide only bounded, local,
  low-trust evidence for vocabulary, preferences, context summaries, or query
  rewriting. It must remain downstream of deterministic eligibility and
  upstream of grounding and policy.
- Retrieved text/IDs can never become shell, executable paths, arbitrary URLs,
  execution authority, or `ValidatedAction`; vector similarity cannot confirm a
  memory or enable Local AI fallback. Conflicts and poisoning fail toward
  clarification.
- Roadmap only; do not implement vector storage/embeddings/RAG runtime or
  enable `LOCAL_SEMANTIC_MEMORY_ENABLED` / `LOCAL_AI_FALLBACK_APPROVED`.
- Evaluate TencentCloud/TencentDB-Agent-Memory MemoryCore as a candidate
  implementation for the low-trust long-term-memory layer. It must not replace
  the current high-trust Semantic Memory or become execution authority.
- First deliverable is a docs/PoC feasibility gate, not production integration:
  define a project-owned `MemoryProvider` interface, a
  `TencentMemoryProvider` adapter, local/standalone deployment assumptions,
  version pinning, failure isolation, privacy/deletion controls, provenance and
  stale-memory handling, backup/restore expectations, and bounded recall
  contracts.
- Prefer direct MemoryCore SDK/HTTP integration for the Python Agent during the
  feasibility phase. MemoryProxy is not required for the first Siri-Agent PoC.
- Retrieved Tencent memory remains untrusted evidence only. It cannot provide
  trusted provider IDs, confirm aliases, bypass grounding/policy, create a
  `ValidatedAction`, or authorize Local AI fallback. Memory unavailability
  must degrade to the existing deterministic/high-trust path.
- No production dependency, daemon, embedding model, migration, or runtime
  enablement is authorized until the separate feasibility/security/acceptance
  gate passes.
- Design notes: [Memory RAG / Personal RAG](docs/roadmap/FUTURE_ROADMAP.md#memory-rag--personal-rag--future-research).

### P3 — Project infrastructure

- Add hosted CI for unit/security tests if separately scheduled.
- Keep Windows/Spotify/Siri real acceptance separate from hosted CI claims.
- Keep `PROJECT_STATUS.md` concise; do not re-add chronological debug history.

## Current Acceptance Gaps

- `spotify_continue` is source-tested and implemented, but its only permitted active-device real run failed closed with `SPOTIFY_FORBIDDEN` / sanitized `provider_reason=UNKNOWN`; it remains a v1.0 known limitation and **NOT ACCEPTED**. See `docs/features/spotify/evidence/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`.
- Candidate Recovery Phase 1B initial trusted clarification and explicit
  playback passed after installed alignment, but the bounded live continuation
  returned `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a next page or
  token rotation. It remains **BLOCKED / NOT ACCEPTED**; this does not prove a
  source bug. See `docs/features/spotify/evidence/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.
- Exact Windows volume has installed runtime acceptance but not Siri voice / physical-speaker acceptance.
- Top-Artist-only and Recently-Played-only real-account ordering cases remain partial/unproven and are not v1.0 blockers.
- Semantic-memory runtime acceptance is incomplete; keep it disabled.
- Local AI production fallback remains unapproved; keep shadow/off.
- Hosted CI is not established; local source evidence must not be presented as hosted CI evidence.

## Definition of Done for v1

- all mandatory `docs/core/SECURITY.md` invariants remain enforced
- core Windows app control and Spotify named-track playback work
- Siri clarification E2E remains passing
- OAuth tokens and secrets remain local
- shutdown remains two-step
- no remote arbitrary execution path exists
- relevant unit/security tests pass
- Windows integration tests pass where required
- setup/start flow works on real Windows
- remaining v1-scoped Spotify controls are implemented or explicitly deferred by the scope-freeze decision
- Local AI is safely kept off/shadow; executable fallback is not part of this freeze
- semantic memory remains disabled until its separate runtime acceptance gate passes
- `PROJECT_STATUS.md` accurately distinguishes source completion from real acceptance
