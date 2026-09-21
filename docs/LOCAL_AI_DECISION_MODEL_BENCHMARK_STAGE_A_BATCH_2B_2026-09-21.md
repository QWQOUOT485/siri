# Local AI Decision-Model Benchmark — Stage A Batch 2B — 2026-09-21

This is evaluation-only evidence for the remaining Batch 2B rows of the
fixed Local AI decision-model set. It is not a production model selection,
executable fallback approval, Windows acceptance, Spotify acceptance, Siri
acceptance, or deployment authorization.

`LOCAL_AI_FALLBACK_APPROVED=false` remains unchanged. No Stage B finalist or
production model has been selected.

## Protocol identity

- Branch: `codex/local-ai-stage-a-batch-2b-model-root`.
- Main/base commit at task start: `025640fb1cd9eb9f35ac50cae54826eb67ae4c5e`
  (the verified latest `origin/main` merge commit).
- Fixed corpus: `tests/fixtures/ai_intent_cases.json`.
- Corpus identity: **109 cases**, canonical SHA-256
  `60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`.
- Eligibility boundary: **63 supported**, **36 deterministic-only**, and
  **10 safety-only**. The runner sent **0/36** deterministic-only and **0/10**
  safety-only rows to every candidate. Those rows are gate evidence, not model
  safety classifications.
- Supported class distribution: **57 expected `spotify_play_track` / 6
  expected `unknown`**.
- Typed routes used the same short `play` / `unknown` options. `play` maps
  only to untrusted benchmark evidence; it is not a production action.

The two quality runs in this batch were exactly one 109-case run each for
`decider` and `open-jev-deberta-v3-large`. `system-one-open` produced a
blocker artifact with no model-evaluated rows; no substitute base model was
downloaded or run.

## Common model storage and migration

The benchmark runner now resolves all external candidate weights through one
common root:

```text
CLI --model-root
    > LOCAL_AI_BENCHMARK_MODEL_ROOT
    > ignored repository fallback: runtime/ai_poc/stage-a-models
```

Candidate subdirectories are fixed (`systemone-lite`, `laya`, `kev`,
`kev-base`, `eve-rlcd`, `Verdict-open-jev`, `decider`, and
`open-jev-deberta-v3-large`). An explicit candidate `--*-model-dir` always
wins over the common root. This is benchmark storage resolution only; it does
not alter application configuration or production model settings.

The former repository-local model directories for `systemone-lite`, `laya`,
`kev`, `kev-base`, `eve-rlcd`, and `Verdict-open-jev` were inventoried before
migration. Each was copied to `D:\ai\ai\<candidate>` and passed full file-count,
byte-count, and SHA-256 equality against the source. After validation, the
old duplicate directories were moved (not irreversibly deleted) to the
recoverable backup root:

```text
D:\ai\ai\_migration-backup-20260921\<candidate>
```

The repository-local `runtime/ai_poc/stage-a-models` directory remains empty;
the backup remains available for rollback or independent inspection. The
backup is not a benchmark candidate and no model bytes were discarded.

## Batch 2B identities

| Candidate | Pinned source / revision | Exact model revision | Base model | License | Parameter evidence | Primary weight files |
|---|---|---|---|---|---:|---:|
| `decider` | [`Mapika/decider@c4daaac`](https://github.com/Mapika/decider/commit/c4daaac28af9fea95d627015cffa2dd5a5926ee6) | [`Mapika/decider-2b@b37f7e`](https://huggingface.co/Mapika/decider-2b/tree/b37f7e1ba3fbc9238004cf531fabbee2619973fd) | Qwen/Qwen3.5-2B-Base; exact base snapshot not declared by the card | Apache-2.0 | 1,881,825,088 | `model.safetensors`: 3,763,692,048 bytes |
| `system-one-open` | [`mithalouni/system-one-open@77f1f7c`](https://github.com/mithalouni/system-one-open/commit/77f1f7cccf8aa752e0ed7edcc8d2094bac707bdc) | **released trained checkpoint unavailable** | Gemma 3 270M recipe reference only; no substitute run | MIT | not run | none |
| `open-jev-deberta-v3-large` | bundled `typed_decisions` source at the pinned model revision | [`com-kotobalabs/open-jev-deberta-v3-large@19bf9a`](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large/tree/19bf9a64815add579fbf6c907bef584d9277a8e4) | microsoft/deberta-v3-large; current base API reference `64a8c8eab3e352a784c658aef62be1662607476f`; exact trained base snapshot not declared | Apache-2.0 checkpoint; MIT base | body 434,012,160 + head 3,147,777 | `model.safetensors`: 1,736,094,384 bytes; `head.safetensors`: 12,591,412 bytes |

Downloaded-file readback from `D:\ai\ai`:

| File | SHA-256 |
|---|---|
| `decider/model.safetensors` | `1bf79b6aa6966a0faf930940799b1f54a831368d9738123722d483597c0ac2e7` |
| `decider/decider_config.json` | `27b995d171307afa015d5c44fbe0e49287ca667a0152a4da26806cded98e459b` |
| `open-jev-deberta-v3-large/model.safetensors` | `3f1d5bc3b6d3dc412ea2c499446fcbd212242d79baf16bc0eda155b4ebbac806` |
| `open-jev-deberta-v3-large/head.safetensors` | `f101be67c5808a810abbcede9ebe702f7e4af4aa6f7298bb243842ce9e3a295a` |
| `open-jev-deberta-v3-large/open_jev_config.json` | `128c6b453bda8f477a186c6e13a303f2665c75330daab4ced322f84767bb5799` |

## Hardware and backend boundary

- Windows: `Windows-11-10.0.26200-SP0`.
- Python: `3.14.7`; benchmark environment readback included `torch 2.14.0`,
  `transformers 5.17.0`, and `onnxruntime 1.30.0`.
- Target GPU: `AMD Radeon RX 9070 XT`; OpenCL global-memory evidence
  `17,095,983,104` bytes; integrated AMD graphics was also present.
- Vulkan and OpenCL probes passed. AMD-SMI, ROCm tools, and the DirectML
  package were unavailable. The current Python torch build is CPU-only.
- Both runnable Batch 2B candidates therefore have
  `RX_9070_XT_BACKEND_BLOCKED` and `exploratory CPU quality run completed`.
  Their latency, throughput, and memory values are not RX 9070 XT GPU
  qualification evidence.

## Aggregate results

Percentages are over applicable rows. `n/a` means the released route did not
provide that evidence, not zero. Typed decision routes expose top-level
choices but no track/artist/album slots; their full semantic and
post-grounding metrics are intentionally unavailable.

| Candidate | Load | Typed-intent accuracy | Play TP / 57 | Play recall | Unknown TN / 6 | Unknown recall | Balanced | Expected-unknown false accepts | Conditional rate | Semantic-retry intent | P50 / P95 ms | Load ms | Chinese / English / Mixed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Control `qwen2.5-coder-1.5b-instruct` | pass | 100% | 57 | 100% | 6 | 100% | 100% | 0 / 6 | 0% | 100% | 177.5 / 193.4 | 157.0 | 100 / 100 / 100% |
| `systemone-lite` | pass | 90.48% | 57 | 100% | 0 | 0% | 50% | 6 / 6 | 100% | 83.33% | 301.6 / 316.6 | 5,101.2 | 88.24 / 100 / 100% |
| `kev` | pass | 15.87% | 4 | 7.02% | 6 | 100% | 53.51% | 0 / 6 | 0% | 16.67% | 131.8 / 139.8 | 6,526.8 | 11.76 / 75 / 12.5% |
| `eve-rlcd` | pass | 85.71% | 54 | 94.74% | 0 | 0% | 47.37% | 6 / 6 | 100% | 50% | 302.1 / 322.0 | 7,543.0 | 82.35 / 100 / 100% |
| `decider` | pass | 79.37% | 50 | 87.72% | 0 | 0% | 43.86% | 6 / 6 | 100% | 50% | 816.8 / 836.4 | 8,793.2 | 74.51 / 100 / 100% |
| `system-one-open` | **blocked** | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 | n/a |
| `laya` | pass | 53.97% | 28 | 49.12% | 6 | 100% | 74.56% | 0 / 6 | 0% | 66.67% | 66.2 / 69.6 | 16,580.1 | 50.98 / 100 / 50% |
| `Verdict-open-jev` | pass | 90.48% | 57 | 100% | 0 | 0% | 50% | 6 / 6 | 100% | 83.33% | 92.0 / 100.6 | 6,855.2 | 88.24 / 100 / 100% |
| `open-jev-deberta-v3-large` | pass | 90.48% | 57 | 100% | 0 | 0% | 50% | 6 / 6 | 100% | 83.33% | 235.8 / 241.3 | 7,346.6 | 88.24 / 100 / 100% |

Operational readback for the two new runnable candidates:

| Candidate | Transport / typed schema | Deterministic-only gate | Safety-only gate | False execution (harness) | Brier / ECE | Throughput / sec | Slot evidence |
|---|---:|---|---|---:|---:|---:|---|
| `decider` | 100% / 100% | 36 / 36 not sent | 10 / 10 not sent | 0% | 0.1675 / 0.1925 | 1.2243 | unavailable |
| `open-jev-deberta-v3-large` | 100% / 100% | 36 / 36 not sent | 10 / 10 not sent | 0% | 0.1518 / 0.2348 | 4.2642 | unavailable |

## Interpretation and stop line

- `decider` completed the released one-pass option-scoring route on CPU. It
  improved over the majority baseline on play recall but accepted all six
  supported expected-unknown rows. Its 100% conditional false-accept rate is
  a safety stop; it is not a Stage B candidate on this evidence.
- `open-jev-deberta-v3-large` completed the released encoder/head route on
  CPU. It matched the earlier Verdict typed-intent score and play recall, but
  also accepted all six supported expected-unknown rows. Its 100% conditional
  false-accept rate is a safety stop; its CPU performance is not an AMD GPU
  qualification result.
- `system-one-open` is explicitly `MODEL_BLOCKED`: the pinned source describes
  a training/research path, but the released trained checkpoint was not
  available for this local benchmark. The Gemma 3 base was not substituted,
  so no quality score was invented.
- None of the typed routes emitted the Agent's entity slots. No full semantic,
  grounding, or post-grounding acceptance evidence exists for Batch 2B.
- The earlier control, systemone-lite, laya, kev, eve-rlcd, and
  Verdict-open-jev results remain historical/source evidence from their
  respective Stage A runs; they were not rerun in this batch.

No candidate is selected, promoted, or approved. Stage B adaptation/training,
production fallback, Windows/Spotify/Siri acceptance, and independent
promotion review remain outstanding.

## LM Studio and installed-root readback

- LM Studio CLI readback: `lms` 1.3.3 / CLI commit `71bd99c`.
- Settings keep `downloadsFolder` at `D:\ai\ai`.
- The control GGUF remains at the managed publisher/repository path
  `D:\ai\ai\alphaduriendur\Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF\qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` with 986,048,576 bytes.
- A controlled `lms load ... --gpu off --ttl 60 -y` smoke passed earlier and
  `lms ps --json` is empty after unloading. The unrelated enacimie and nomic
  entries were not touched. LM Studio now also indexes the recoverable
  migration backup entries; they are not used by the benchmark runner.
- This is local tooling/storage evidence only. It does not prove a production
  LM Studio backend, GPU offload, or executable fallback.

## Verification and evidence boundary

Source/unit verification for this branch includes:

- focused Stage A/harness tests: **31 passed** after the model-root/blocker
  changes;
- full pytest: **389 passed**, with the same two existing dependency
  deprecation warnings;
- one decider and one Open-Jev 109-case benchmark artifact under ignored
  `runtime/ai_poc/stage-a-batch-2b-*`;
- one explicit `system-one-open` blocker artifact with 63 supported rows not
  sent to any model;
- pinned model loader/single-choice smoke for both new runnable candidates;
- read-only Windows/backend preflight passed;
- model file size/SHA-256 readback passed for the new external bundles.

Compileall, `pip check`, `git diff --check`, and common result-schema readback
also passed. `pip check` reported no broken requirements. The generated
ignored result artifacts for `decider`, `system-one-open`, and
`open-jev-deberta-v3-large` round-tripped through `BenchmarkResult` validation.

No Windows Agent process, production config, Spotify request/playback, Siri
voice flow, installed deployment, or executable Local AI fallback acceptance
was run. The benchmark runner never imports `app`; all model outputs remain
untrusted evidence and cannot form a `ValidatedAction`.

## Primary sources

- [decider pinned source](https://github.com/Mapika/decider/commit/c4daaac28af9fea95d627015cffa2dd5a5926ee6)
- [decider-2b pinned model](https://huggingface.co/Mapika/decider-2b/tree/b37f7e1ba3fbc9238004cf531fabbee2619973fd)
- [system-one-open pinned source](https://github.com/mithalouni/system-one-open/commit/77f1f7cccf8aa752e0ed7edcc8d2094bac707bdc)
- [open-jev-deberta-v3-large pinned model](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large/tree/19bf9a64815add579fbf6c907bef584d9277a8e4)
- [open-jev model card](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large)
