# Local AI Decision-Model Benchmark — Stage A Batch 2A — 2026-09-21

This is sanitized, evaluation-only evidence for exactly three rows of the
fixed Local AI decision-model set: `kev`, `eve-rlcd`, and
`Verdict-open-jev`. It is not a production model selection, executable
fallback approval, Windows acceptance, Spotify acceptance, Siri acceptance, or
deployment authorization.

`LOCAL_AI_FALLBACK_APPROVED=false` remains unchanged. Production Local AI
authority remains the existing deterministic path / current shadow boundary.

## Protocol identity

- Run branch: `codex/local-ai-stage-a-batch-2a`.
- `main` base at task start: `698a7f17c426061c50d4257f27191b175d4606aa`.
- Fixed candidates run in this batch: `kev`, `eve-rlcd`, and
  `Verdict-open-jev` only. No remaining candidate, Stage B adaptation, or
  training run was started.
- Frozen corpus: `tests/fixtures/ai_intent_cases.json`.
- Corpus identity: **109 cases**, canonical SHA-256
  `60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`.
- Eligibility boundary: **63 supported**, **36 deterministic-only**, and
  **10 safety-only**. The runner sent **0/36** deterministic-only and **0/10**
  safety-only rows to each candidate. Those rows are gate evidence, not model
  safety classifications.
- Supported class distribution: **57 expected `spotify_play_track` / 6
  expected `unknown`**.
- The common typed question used the short `play` / `unknown` option labels.
  `play` is mapped only to untrusted benchmark evidence
  `spotify_play_track`; it is not a production action. None of these released
  typed routes emits track/artist/album slots, so full semantic and
  post-grounding metrics are intentionally unavailable.

## Pinned identities

| Candidate | Pinned upstream source | Exact checkpoint | Base / license | Parameters | Downloaded model files |
|---|---|---|---|---:|---:|
| `kev` | [`jaredpalmer/kev@e0bcf50`](https://github.com/jaredpalmer/kev/commit/e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c) | [`jaredpalmer/kev-0.5b@2679c20`](https://huggingface.co/jaredpalmer/kev-0.5b/tree/2679c20e6dde32fb3c4f97ecdad2e6e92bb88a06) | Qwen/Qwen2.5-0.5B; Apache-2.0 adapter/head and Apache-2.0 Qwen base | 494,032,768 | adapter 35,235,088 + head 1,839,295 bytes; pinned local base 988,097,824 bytes |
| `eve-rlcd` | [`anthony-maio/eve-rlcd@57a179b`](https://github.com/anthony-maio/eve-rlcd/commit/57a179b7b1bedc80f65bf42ccda129dd1888272f) | [`anthonym21/qwen3-0.6b-rlcd-decision@b327ec5`](https://huggingface.co/anthonym21/qwen3-0.6b-rlcd-decision/tree/b327ec5efb5fdbf8bfafa3b369720ac5f6434b05) | Qwen/Qwen3-0.6B-Base; MIT code and Apache-2.0 Qwen weights/base | 596,049,920 | model 2,384,233,112 + decision head 106,608 bytes |
| `Verdict-open-jev` | [`Heman10x-NGU/Verdict-open-jev@30f1556`](https://github.com/Heman10x-NGU/Verdict-open-jev/commit/30f15564821626ca5c1ad5b2638c4eb7078787dd) | [`heman10x/rlcd-modernbert-151m@8af2496`](https://huggingface.co/heman10x/rlcd-modernbert-151m/tree/8af2496eb63c7fa66d7d234e1f62629380030eb4) | ModernBERT / GLiClass; repo LICENSE text is Apache-2.0, GitHub classifier was unasserted, HF card says Apache-2.0 | 151,378,176 | PyTorch model 605,529,340 bytes; ONNX fp32 606,323,181; ONNX fp16 303,785,047 |

Downloaded-file SHA-256 readback was recorded before quality aggregation:

- Kev adapter `04facd5e97cebce2f00c6525136ff21ac96623c3a9e44b4c590e138dd7587318`; Kev head `0d59bd4608e38f32b4f86c85eb29e8187e14f2117ca99fe765e799b290c52a66`; pinned Qwen base `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342`.
- Eve model `ad0b65098a40026a9c2b763125c45ec312fa4e11205c07b5eb32ad10d392e47e`; decision head `da1328e06c64789d334350975cb3350d8d2ef7c779f133cdd5b400feb835f233`.
- Verdict PyTorch model `d252823994d47a7933217fc86449493299643af6a0c0d83d6bd5a7666d3253ef`; ONNX fp32 `4ae01f822538b000fa0e55859d4b3e6b40871d860149397e8784428b2a42ee5e`; ONNX fp16 `4db28305590c714e33c2cacb75a57ec941c72bb210e1266ba2c7d77e85ddc526`.

The last Verdict digest above is also available in the pinned upstream
[`bundle_manifest.json`](https://huggingface.co/heman10x/rlcd-modernbert-151m/raw/8af2496eb63c7fa66d7d234e1f62629380030eb4/bundle_manifest.json).

## Released routes and loader boundary

- Kev used the released `kev.model.DecisionModel` block-causal pointer-head
  implementation with the pinned original `kev-0.5b` adapter/head and local
  pinned Qwen base. The upstream `evaluate` module imports its optional
  datasets package at module import time; the benchmark imported the same
  released model implementation directly to avoid an unused evaluation-data
  dependency. No upstream source or model file was modified.
- Eve used the released `rlcd.decide.Decider.load` decision-only export with
  `fast=False`, CPU fp32 body, shared-prefix typed choice scoring, and no text
  generation. Its upstream [`MODEL_CARD.md`](https://github.com/anthony-maio/eve-rlcd/blob/57a179b7b1bedc80f65bf42ccda129dd1888272f/MODEL_CARD.md)
  describes the exported `decision.json` contract and the Qwen base lineage.
- Verdict used the released `core.engine_encoder.DecisionEngine` on CPU. The
  wrapper selected its local ONNX Runtime `CPUExecutionProvider` path; the
  PyTorch model is still instantiated by that released wrapper. Its explicit
  `__insufficient_evidence__` outcome was deterministically folded into the
  benchmark's closed `unknown` evidence bucket. No execution authority was
  introduced.

## Environment and hardware boundary

- Windows: `Windows-11-10.0.26200-SP0`.
- Hardware preflight before model inspection/download: AMD Radeon RX 9070 XT
  plus integrated AMD adapter; target OpenCL memory evidence
  `17,095,983,104` bytes; OpenCL and Vulkan probes available; AMD-SMI, ROCm,
  and the DirectML package unavailable; `torch.cuda.is_available()` and MPS
  false.
- Batch run environment: Python `3.14.7`, `torch 2.14.0+cpu`,
  `transformers 5.17.0`, `peft 0.21.0`, `gliclass 0.1.20`,
  `onnxruntime 1.30.0`, `safetensors 0.8.0`, and CPU-only supporting
  packages. These evaluation dependencies were installed only in the local
  benchmark venv; project requirements and production app imports were not
  changed.
- All three quality runs are marked
  `RX_9070_XT_BACKEND_BLOCKED` and `exploratory CPU quality run completed`.
  Their latency, throughput, and memory observations are not RX 9070 XT GPU
  qualification evidence.

## Aggregate results

The raw per-case observations and metadata remain under ignored
`runtime/ai_poc/stage-a-batch-2a-*`. The table below is sanitized readback of
those artifacts; no inference was rerun during report preparation.

| Candidate | Typed-intent accuracy | Play TP / 57 | Play recall | Unknown TN / 6 | Unknown recall | Balanced accuracy | Expected-unknown false accepts | Conditional rate | Corpus incidence | P50 / P95 ms | Brier / ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `kev` | 15.87% | 4 / 57 | 7.02% | 6 / 6 | 100% | 53.51% | 0 / 6 | 0% | 0% | 131.8 / 139.8 | 0.4325 / 0.5806 |
| `eve-rlcd` | 85.71% | 54 / 57 | 94.74% | 0 / 6 | 0% | 47.37% | 6 / 6 | 100% | 5.50% (6 / 109) | 302.1 / 322.0 | 0.1221 / 0.0923 |
| `Verdict-open-jev` | 90.48% | 57 / 57 | 100% | 0 / 6 | 0% | 50.00% | 6 / 6 | 100% | 5.50% (6 / 109) | 92.0 / 100.6 | 0.1130 / 0.1637 |

Operational and language-slice evidence:

| Candidate | Transport / typed schema | Semantic-retry intent | Chinese / English / mixed intent accuracy | Load ms | Throughput / sec |
|---|---:|---:|---:|---:|---:|
| `kev` | 100% / 100% | 16.67% | 11.76% / 75.00% / 12.50% | 6,526.8 | 7.58 |
| `eve-rlcd` | 100% / 100% | 50.00% | 82.35% / 100% / 100% | 7,543.0 | 3.29 |
| `Verdict-open-jev` | 100% / 100% | 83.33% | 88.24% / 100% / 100% | 6,855.2 | 10.84 |

Eligibility-gate readback was identical for all three candidates: 36/36
deterministic-only rows and 10/10 safety-only rows were not sent to the model;
gate safe-unknown was 100% in both groups. This is not evidence that a model
understood those inputs. False execution was 0% in the harness, with no model
output connected to an action.

## Interpretation and stop line

- Kev's original English-oriented 0.5B prototype produced valid typed output
  but only 4/57 play recall on this Chinese/mixed corpus. It is not a Stage B
  candidate on this evidence.
- Eve produced high play recall but accepted all six supported expected-unknown
  rows. Its 100% conditional false-accept rate is a safety stop, regardless of
  its lower Brier/ECE on this corpus. It is not a Stage B candidate.
- Verdict matched all 57 expected-play rows but also accepted all six expected
  unknown rows. Its 100% conditional false-accept rate is a safety stop. Its
  small CPU latency is not a GPU qualification result, and it is not a Stage B
  candidate.
- No candidate emitted the Agent's track/artist/album slots. There is no full
  semantic, grounding, or post-grounding acceptance evidence for this batch.
- No candidate is selected, promoted, or approved. `LOCAL_AI_MODE` and
  `LOCAL_AI_FALLBACK_APPROVED=false` remain unchanged.

## Evidence boundary

The run performed no Stage B adaptation or training, no remaining-candidate
benchmark, no production app import/change, no Windows adapter call, no live
Spotify request/playback, no Siri voice flow, no installed deployment, and no
executable Local AI fallback acceptance. Model weights, raw outputs, prompts,
tokens, credentials, Spotify IDs/URIs, and local source checkouts remain under
ignored runtime paths and are not committed.

Verification after this batch's source/doc changes: focused Stage A/harness
tests **26 passed**; full pytest **384 passed** with two existing dependency
deprecation warnings; compileall, `pip check`, and `git diff --check` passed.

## Primary-source links

- Kev: pinned [repository README](https://raw.githubusercontent.com/jaredpalmer/kev/e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c/README.md),
  [original model card](https://raw.githubusercontent.com/jaredpalmer/kev/e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c/docs/model-cards/kev-0.5b.md),
  and [Apache-2.0 LICENSE](https://raw.githubusercontent.com/jaredpalmer/kev/e0bcf50153f1bda4ca6a8be5e12cbd5f9ebbce1c/LICENSE).
- Eve: pinned [repository README](https://raw.githubusercontent.com/anthony-maio/eve-rlcd/57a179b7b1bedc80f65bf42ccda129dd1888272f/README.md),
  [pyproject backend requirements](https://raw.githubusercontent.com/anthony-maio/eve-rlcd/57a179b7b1bedc80f65bf42ccda129dd1888272f/pyproject.toml),
  and [MIT LICENSE](https://raw.githubusercontent.com/anthony-maio/eve-rlcd/57a179b7b1bedc80f65bf42ccda129dd1888272f/LICENSE).
- Verdict: pinned [repository README](https://raw.githubusercontent.com/Heman10x-NGU/Verdict-open-jev/30f15564821626ca5c1ad5b2638c4eb7078787dd/README.md),
  [repository LICENSE text](https://raw.githubusercontent.com/Heman10x-NGU/Verdict-open-jev/30f15564821626ca5c1ad5b2638c4eb7078787dd/LICENSE),
  and [HF model metadata](https://huggingface.co/api/models/heman10x/rlcd-modernbert-151m).
