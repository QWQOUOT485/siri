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
deferrals remain recorded in `docs/V1_SCOPE_FREEZE_2026-09-20.md`. Candidate
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
`docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.

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
3. Read `docs/SECURITY.md`.
4. Read `docs/SPEC.md` and `docs/ARCHITECTURE.md`.
5. Read task-specific docs:
   - Spotify → `docs/SPOTIFY.md`
   - playback controls → `docs/PLAYBACK_CONTROLS.md`
   - Local AI → `docs/LOCAL_AI_ARCHITECTURE_PROPOSAL.md` plus current SECURITY / ARCHITECTURE rules
   - semantic recovery → `docs/semantic_recovery/`
   - Windows adapters → `docs/WINDOWS.md`
   - API → `docs/API.md`
   - Siri → `docs/SIRI_SHORTCUT.md`
6. Before finishing, run relevant tests per `docs/TESTING.md`.
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

### P2.5 — Open System One / Jev-like local model benchmark

Build a reproducible local benchmark for open Jev-like / System-One-style
decision models. This is an evaluation task only. It must not expand Local AI
authority, enable executable fallback, or set
`LOCAL_AI_FALLBACK_APPROVED=true`.

The goal is not to find the largest model. The goal is to determine which
architecture best fits this Agent's narrow Chinese Siri semantic-recovery task
under the existing deterministic grounding and policy boundary.

#### Control baseline

Keep the current generative baseline as the control row:

- `qwen2.5-coder-1.5b-instruct` in the existing prompt / strict-schema path.
- Preserve the current frozen 109-case results as historical evidence; rerun
  only when the benchmark harness, prompt/schema, model build, or comparison
  protocol requires an exact aligned run.

#### Fixed eight-candidate set

Benchmark these eight open candidates before adding more. Do not silently
replace a candidate; if one cannot run, record the exact blocker and continue.

| # | Candidate | Backbone / scale | Route being tested | Why it is in the set |
|---|---|---|---|---|
| 1 | [systemone-lite](https://github.com/fritzprix/systemone-lite) | Qwen2.5-0.5B-Instruct | frozen/SFT option-restricted next-token scoring + prefix KV | simplest Qwen System-One baseline; published RTX 3060 12 GB path |
| 2 | [kev](https://github.com/jaredpalmer/kev) | Qwen2.5-0.5B | LoRA + trained pointer/readout decision head | small trained decoder decision-head design |
| 3 | [eve-rlcd](https://github.com/anthony-maio/eve-rlcd) | Qwen3-0.6B-Base | supervised warmup + RLCD-style calibrated decision training | tests explicit probability/calibration training rather than plain SFT |
| 4 | [decider](https://github.com/Mapika/decider) | Qwen3.5-2B-Base | one-pass typed decisions with trained label projection | stronger small decoder model and richer decision-model implementation |
| 5 | [system-one-open](https://github.com/mithalouni/system-one-open) | Gemma 3 270M first; Gemma 4 E2B only if hardware fit is proven | trained Gemma Jev-style model | non-Qwen decoder family and very small-model comparison |
| 6 | [laya](https://github.com/NandhaKishorM/laya) | prefer multilingual mmBERT checkpoint (~322M class) | non-autoregressive multilingual encoder + decision head | especially relevant to Traditional-Chinese / mixed-language Siri input |
| 7 | [Verdict-open-jev](https://github.com/Heman10x-NGU/Verdict-open-jev) | ModernBERT ~151M | very small non-autoregressive encoder decision engine | latency / size floor and encoder-vs-decoder comparison |
| 8 | [open-jev-deberta-v3-large](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large) | DeBERTa-v3-large | encoder + typed option scoring + calibrated probabilities | independent encoder architecture and calibration reference |

Optional methodology reference, not a ninth required model:

- [LitJev](https://github.com/zhengxuyu/litjev) may be used to test
  logits-only inference on an existing Qwen checkpoint. If used, prefer the
  current Qwen baseline backbone so the experiment isolates **decision
  inference vs autoregressive JSON generation** rather than changing both model
  and inference method at once.

#### Stage A — Run released models / inference methods as-is

Before training anything locally:

1. Pin repository commit / package version / model revision.
2. Record license, exact model ID, parameter count, quantization/precision,
   framework/backend, and model file size.
3. Adapt each candidate behind a benchmark-only interface; do not wire it into
   executable production fallback.
4. Run the same frozen Agent evaluation cases without training on their answers.
5. Keep raw model outputs and machine-specific traces under ignored runtime
   paths; commit only sanitized aggregate evidence.

A candidate may be English-oriented or poorly matched to Chinese. Do not remove
it merely for performing badly; that result is useful architecture evidence.

#### Stage B — Agent-specific adaptation of finalists

After Stage A, select at most the strongest 2–3 candidates for local adaptation.

- Build a reviewed/sanitized Siri decision corpus separate from the frozen
  evaluation set.
- Use explicit train / validation / frozen-evaluation splits.
- Prefer LoRA / QLoRA / small decision-head tuning where supported.
- For encoder candidates, use the project's intended classification/decision
  head training path rather than forcing an autoregressive JSON objective.
- Include Traditional Chinese, mixed Chinese/English artist names, colloquial
  Siri phrasing, ASR-like errors, entity-boundary mistakes, and strong
  `unknown` negative examples.
- Do not include secrets, OAuth tokens, private paths, Spotify IDs/URIs, raw
  sensitive logs, or frozen benchmark answers in training data.

The initial adapted authority remains narrow:

~~~text
spotify_play_track
unknown
+ bounded track / artist / album semantic recovery
~~~

Do not add app control, shutdown, force-close, firewall, arbitrary Windows
operations, shell text, executable paths, URLs, or client-owned Spotify IDs.

#### Benchmark protocol

Use the existing Local AI frozen corpus as the common starting point and extend
the harness only when needed to represent non-generative typed decisions.
Preserve old cases and hashes when changing the harness.

Measure at least:

- transport / model-load success
- typed-output or strict-schema success
- supported semantic accuracy
- semantic-retry accuracy
- deterministic-only safe-unknown
- safety-only safe-unknown
- false execution
- post-grounding false acceptance
- P50 / P95 end-to-end model latency
- throughput where the model supports batched questions
- peak VRAM and system RAM
- model/load time
- malformed-output rate
- timeout / backend failure behavior
- probability calibration: Brier score and ECE where probabilities exist
- option-order sensitivity / flip rate where the architecture scores options
- Chinese-only, English-only, and mixed-language slice accuracy

For entity extraction models, also record track / artist / album slot accuracy
and entity-boundary recovery separately from top-level action accuracy.

#### Hardware protocol

Use a single benchmark machine / GPU for the entire comparison:

- **RX 9070 XT 16 GB only**

All eight candidates, the control baseline, and any optional LitJev-style
methodology run should use the same RX 9070 XT system whenever technically
possible. This keeps latency, throughput, VRAM use, load time, and backend
behavior comparable without mixing NVIDIA/CUDA and AMD results.

Backend rules:

- Prefer a stable backend that actually supports the candidate on RX 9070 XT,
  such as ROCm, Vulkan, or another project-supported local path.
- Record the exact driver/runtime, backend, precision/quantization, context
  length, batch shape, and model revision with every performance result.
- Do not silently move a failing candidate to the RTX 3060 or another machine.
- If a candidate cannot run correctly on RX 9070 XT because its released code
  path is CUDA-only, unsupported, broken, or otherwise incompatible, record an
  explicit **RX 9070 XT backend blocker** and continue with the remaining
  candidates.
- A backend blocker is a valid benchmark result; do not patch away architectural
  differences merely to make every candidate produce a score.
- If an officially supported AMD-compatible path exists but requires a small,
  reviewable compatibility change, document the exact change and keep it
  separate from model-quality results.

If a released candidate requires more than the available 16 GB VRAM, try an
officially supported smaller checkpoint / precision / quantization only when
that variant belongs to the same project and preserves the intended method.
Otherwise record it as a VRAM blocker instead of inventing an unreviewed
substitute.

Do not combine the RX 9070 XT with the RTX 3060 as pooled VRAM or distributed
training for this benchmark.

#### Fairness rules

- Same frozen cases for every candidate.
- Same semantic target and safety expectations.
- No benchmark-answer leakage into tuning data.
- No candidate-specific hand-written answer overrides.
- Do not lower grounding/policy requirements to improve a model's score.
- Confidence is evidence, not execution authority.
- A candidate with higher semantic accuracy but worse false acceptance is not
  considered an improvement.
- Parameter count alone is never a success criterion.
- Do not compare latency without recording hardware/backend/precision.
- Keep source/unit benchmark results separate from Windows / Spotify / Siri
  real-world acceptance.

#### Output artifact

Produce a sanitized report such as:

`docs/LOCAL_AI_DECISION_MODEL_BENCHMARK_<YYYY-MM-DD>.md`

Include:

- exact candidate/model revisions
- exact benchmark/harness commit
- frozen corpus hash and case count
- hardware/backend identity
- one comparison table for all eight candidates + control
- per-language slices
- calibration results where supported
- failure/blocker notes
- shortlist rationale based on measured results, without changing production
  approval state

Raw JSON/CSV can remain under ignored `runtime/ai_poc/` or another existing
ignored benchmark directory.

#### Research success criteria

~~~text
same frozen evaluation corpus
+ reproducible candidate identity
+ measurable semantic and/or latency gain
+ calibrated confidence where applicable
+ no safety regression
+ fits realistic local hardware
~~~

Only after a finalist passes the existing grounding, policy, fail-closed,
production-aligned shadow, real Windows/Spotify/Siri acceptance where required,
and independent promotion review may executable fallback be considered.

### P3 — Project infrastructure

- Add hosted CI for unit/security tests if separately scheduled.
- Keep Windows/Spotify/Siri real acceptance separate from hosted CI claims.
- Keep `PROJECT_STATUS.md` concise; do not re-add chronological debug history.

## Current Acceptance Gaps

- `spotify_continue` is source-tested and implemented, but its only permitted active-device real run failed closed with `SPOTIFY_FORBIDDEN` / sanitized `provider_reason=UNKNOWN`; it remains a v1.0 known limitation and **NOT ACCEPTED**. See `docs/SPOTIFY_CONTINUE_RESUME_403_DIAGNOSIS_2026-09-20.md`.
- Candidate Recovery Phase 1B initial trusted clarification and explicit
  playback passed after installed alignment, but the bounded live continuation
  returned `SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED` without a next page or
  token rotation. It remains **BLOCKED / NOT ACCEPTED**; this does not prove a
  source bug. See `docs/SPOTIFY_CANDIDATE_RECOVERY_RUNTIME_ACCEPTANCE_2026-09-20.md`.
- Exact Windows volume has installed runtime acceptance but not Siri voice / physical-speaker acceptance.
- Top-Artist-only and Recently-Played-only real-account ordering cases remain partial/unproven and are not v1.0 blockers.
- Semantic-memory runtime acceptance is incomplete; keep it disabled.
- Local AI production fallback remains unapproved; keep shadow/off.
- Hosted CI is not established; local source evidence must not be presented as hosted CI evidence.

## Definition of Done for v1

- all mandatory `docs/SECURITY.md` invariants remain enforced
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
