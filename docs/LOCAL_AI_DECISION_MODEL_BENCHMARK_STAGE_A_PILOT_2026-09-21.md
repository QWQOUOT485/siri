# Local AI Decision-Model Benchmark — Stage A Pilot — 2026-09-21

This is sanitized, evaluation-only evidence for the first three rows of the
fixed Local AI decision-model pilot. It is not a production model selection,
executable fallback approval, Windows acceptance, Spotify acceptance, Siri
acceptance, or deployment authorization.

`LOCAL_AI_FALLBACK_APPROVED=false` remains unchanged. Production Local AI
authority remains the existing deterministic path / current shadow boundary.

## Protocol identity

- Pilot candidates: existing `qwen2.5-coder-1.5b-instruct` control,
  `systemone-lite`, and `laya` only.
- Benchmark-only harness commit:
  `928087d4c96fff3ef98549afb430b28f2ff2d4de`.
- Project source base at run start: `08c397fd29a8361ebd0f0b6eb23510630f58f027`.
- Frozen corpus: `tests/fixtures/ai_intent_cases.json`.
- Corpus identity: **109 cases**, canonical SHA-256
  `60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`.
- Reviewed eligibility boundary: **63 supported**, **36 deterministic-only**,
  **10 safety-only**. Eligibility-gated rows were not sent to a model:
  **36/36 deterministic-only** and **10/10 safety-only** rows were skipped.
  Candidate-model safety classification on those skipped rows is **not
  evaluated**; their safe-unknown values are eligibility-gate evidence only.
- The common typed-decision question used fixed `play` / `unknown` labels.
  `play` maps only to the benchmark evidence label
  `spotify_play_track`; it is not a production action. The short label avoids
  the released systemone `_encode_symbol` first-subtoken behavior for the
  multi-token string `spotify_play_track`.

## Pinned identities

| Candidate | Upstream source revision | Exact model revision / local identity | License | Parameters | Model file |
|---|---|---|---|---:|---:|
| Control | local LM Studio catalog | `alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | Apache-2.0 Qwen base | 1.5B | 986,048,576 bytes |
| systemone-lite | `0e3373191d3904a070f96d0ed211e6bea8d9ebf6` (`fritzprix/systemone-lite`) | `dwidlee/systemone-lite-0.5b` @ `06b28ed3c5da1d94a6abc015df566ae6408dc5be` | Apache-2.0 | 494,032,768 | 988,097,824 bytes |
| laya | `42626c348753fbb17572a813127df2278a1ec527` (`NandhaKishorM/laya`) | `convaiinnovations/laya-multilingual` @ `052592a15d198d9ad47da779604259b10b47b7aa` | Apache-2.0 | 321,908,998 | 643,835,514 bytes |

Downloaded model file readback for the two HF checkpoints:

- systemone `model.safetensors`: SHA-256
  `7eac5d8ff362df967e0f674702e68a92ac28b4a01cae81b8efca3c4f6d206d4a`.
- laya `model.safetensors`: SHA-256
  `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204`.

## Environment and backend boundary

- Windows: `Windows-11-10.0.26200-SP0`.
- Python: `3.14.7`.
- Target GPU readback: `AMD Radeon RX 9070 XT`; OpenCL memory evidence
  `17,095,983,104` bytes. The integrated AMD adapter was also present.
- Read-only tooling: Vulkan and OpenCL probes passed; AMD-SMI, ROCm tools, and
  the DirectML package were unavailable.
- Benchmark venv packages used for the released Python candidates:
  `torch 2.14.0+cpu`, `transformers 4.57.6`, `safetensors 0.7.0`,
  `huggingface_hub 0.36.2`, `accelerate 1.15.0`, and `numpy 2.3.5`.
  `torch.cuda.is_available()` and MPS were false.
- The released systemone and laya Python routes therefore ran on the same
  machine's CPU. This collected exploratory quality evidence, but the
  hardware-aligned Stage A status for both rows is
  `RX_9070_XT_BACKEND_BLOCKED`; it is **not** an RX 9070 XT GPU latency,
  throughput, or VRAM result. The control used the existing LM Studio loopback route;
  `lms ps` reported the model as `Local`, but did not expose a sufficient
  backend/offload readback to claim a precise GPU backend.
- systemone's checkpoint metadata exposed `extra_special_tokens` as a list,
  while the installed Transformers tokenizer expected a mapping. The
  benchmark loader temporarily converted that metadata during load and
  restored the original file afterward; weights and upstream source were not
  changed. This compatibility shim is benchmark-only.

## Aggregate results

Percentages are over the applicable rows. `n/a` means the released route did
not expose that evidence, not zero. The typed candidates expose top-level
choice probabilities but do not emit track/artist/album slots, so their full
semantic accuracy is intentionally not calculated for them. The metrics below
were recomputed from the preserved ignored `observations.jsonl` artifacts; no
model inference was rerun.

### Class and grounding metrics

The supported class distribution is **57 expected `spotify_play_track` / 6
expected `unknown`**. `expected-unknown false-accept rate` uses only those six
AI-eligible supported expected-unknown rows as its denominator. The separate
`corpus incidence` value retains the historical whole-corpus denominator for
continuity; it is not a conditional safety rate.

| Candidate | Hardware-aligned Stage A status | Quality evidence status | Full semantic / slot evidence | Typed-intent accuracy | Play TP / cases | Play recall | Unknown TN / cases | Unknown recall | Balanced intent accuracy | Expected-unknown false accepts / cases | Conditional rate | Corpus incidence | True post-grounding false acceptance |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | `LMSTUDIO_LOCAL_BACKEND_GPU_OFFLOAD_UNQUALIFIED` | control loopback quality run completed | **95.24% / available** | 100% | 57 / 57 | 100% | 6 / 6 | 100% | 100% | 0 / 6 | 0% | 0% | 0% |
| systemone-lite | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run completed | n/a / unavailable | **90.48%** | 57 / 57 | 100% | 0 / 6 | **0%** | **50%** | **6 / 6** | **100%** | 5.50% (6 / 109) | n/a |
| laya multilingual | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run completed | n/a / unavailable | 53.97% | 28 / 57 | 49.12% | 6 / 6 | 100% | 74.56% | 0 / 6 | 0% | 0% | n/a |

### Transport, eligibility-gate, and operational metrics

The two eligibility-gate columns are not candidate-model classifications:
they record that the listed rows were not sent to a model. `False execution`
is harness/system evidence only; it is not proof that a candidate model rejects
hostile input.

| Candidate | Transport / schema | Semantic-retry intent | Deterministic-only gate | Safety-only gate | False execution (harness) | P50 / P95 ms | Brier / ECE | Load ms |
|---|---:|---:|---|---|---:|---:|---:|---:|
| Control | 100% / 100% | 100% | 36 / 36 not sent | 10 / 10 not sent | 0% | 177.5 / 193.4 | n/a / n/a | 157.0 |
| systemone-lite | 100% / 100% | 83.33% | 36 / 36 not sent | 10 / 10 not sent | 0% | 301.6 / 316.6 | 0.0919 / 0.0762 | 5,101.2 |
| laya multilingual | 100% / 100% | 66.67% | 36 / 36 not sent | 10 / 10 not sent | 0% | 66.2 / 69.6 | 0.2701 / 0.4002 | 16,580.1 |

Language-slice intent accuracy for the 63 supported rows:

| Candidate | Chinese | English | Mixed |
|---|---:|---:|---:|
| Control | 100% | 100% | 100% |
| systemone-lite | 88.24% | 100% | 100% |
| laya multilingual | 50.98% | 100% | 50% |

## Interpretation and stop line

- The control is the only row with complete entity-slot evidence. It retained
  the prior strict-schema quality boundary in this aligned rerun, with
  **95.24% full semantic accuracy**.
- systemone-lite exposes no released slot extraction path and its typed-intent
  accuracy is **90.48%**, exactly the majority expected-play proportion
  (**57 / 63**); it is consistent with an always-play majority-class
  classifier. Its play recall is 100%, but unknown recall is **0%** and its
  six expected-unknown rows are all falsely accepted: the route-neutral
  conditional false-accept rate is **100%**. The old **5.50%** value is only
  the whole-corpus incidence (**6 / 109**). This is a safety regression and
  makes systemone-lite unsuitable for advancement or Stage B selection; true
  post-grounding evidence is **n/a** because no slots were supplied.
- laya multilingual's unadapted typed-intent accuracy is **53.97%**: play
  recall is 49.12%, unknown recall is 100%, and balanced intent accuracy is
  74.56%. Its route provides no entity-slot output for this Agent task, so
  the current accuracy and lack of slot extraction do not support Stage B
  advancement; true post-grounding evidence is **n/a**.
- systemone-lite and laya both have the hardware-aligned status
  `RX_9070_XT_BACKEND_BLOCKED` and separately have exploratory CPU quality
  runs completed. Their latency, throughput, and memory observations are
  therefore **not comparable GPU latency/throughput/VRAM evidence** and must
  not be used as RX 9070 XT GPU claims.
- This pilot is research evidence only. No model is production approved, no
  Stage B selection has been made, and no finalist is promoted. The remaining
  fixed candidates were not run because this task explicitly stops after the
  three-model Stage A pilot. Any later Stage B work requires a separate
  reviewed corpus, held-out split, entity-slot design, and independent
  promotion review.

## Evidence boundary

All three model loads and all 109 sanitized case rows completed in the
original pilot. The current metrics were recomputed from the preserved raw
observations without model inference. Raw/local artifacts remain under
ignored `runtime/ai_poc/stage-a-*`; no prompts, raw model outputs, tokens,
credentials, Spotify IDs/URIs, or model weights were added to Git. Source
verification after this semantics fix: focused Stage A/harness tests **24
passed**, full pytest **382 passed** with two existing dependency deprecation
warnings; compileall, `pip check`, and `git diff --check` passed.

No Windows Agent process, production config, Spotify request/playback, Siri
voice flow, installed deployment, or executable Local AI fallback acceptance
was run. The result is source/benchmark evidence only, and
`LOCAL_AI_FALLBACK_APPROVED=false` remains mandatory.

## Primary-source research addendum — Stage A candidate identities (2026-09-21)

This is a bounded, read-only source verification pass for the same three
Stage A candidates. It does not select a model, authorize production use, or
change runtime authority. Only repository pages, raw text/config files, and
Hugging Face metadata endpoints were read; no model weights were downloaded.

### Upstream source heads and pinned revisions

As checked on 2026-09-21, both upstream GitHub `main` heads equal the pinned
revisions used by the pilot:

| Candidate | Upstream head / pinned revision | Primary-source finding |
|---|---|---|
| systemone-lite | [`fritzprix/systemone-lite@0e3373191d3904a070f96d0ed211e6bea8d9ebf`](https://github.com/fritzprix/systemone-lite/commit/0e3373191d3904a070f96d0ed211e6bea8d9ebf) | The project describes itself as an unofficial local System One-shaped API, using shared-prefix KV caching and batched next-token scoring over option token IDs, not autoregressive JSON generation. Its default is `Qwen/Qwen2.5-0.5B-Instruct`; `dwidlee/systemone-lite-0.5b` is the optional SFT checkpoint. The upstream repository license is MIT. See the pinned [`README.md`](https://github.com/fritzprix/systemone-lite/blob/0e3373191d3904a070f96d0ed211e6bea8d9ebf/README.md) and [`infer.py`](https://github.com/fritzprix/systemone-lite/blob/0e3373191d3904a070f96d0ed211e6bea8d9ebf/src/systemone_lite/infer.py). |
| laya | [`NandhaKishorM/laya@42626c348753fbb17572a813127df2278a1ec527`](https://github.com/NandhaKishorM/laya/commit/42626c348753fbb17572a813127df2278a1ec527) | The pinned source exposes typed `choice`, `score`, and `noul` questions, scores option markers in one forward pass, and has explicit multilingual routing. The source includes automatic device fallback to CPU when the requested accelerator is unavailable or placement fails. The upstream repository is Apache-2.0. See the pinned [`README.md`](https://github.com/NandhaKishorM/laya/blob/42626c348753fbb17572a813127df2278a1ec527/README.md), [`agent.py`](https://github.com/NandhaKishorM/laya/blob/42626c348753fbb17572a813127df2278a1ec527/laya/agent.py), and [`router.py`](https://github.com/NandhaKishorM/laya/blob/42626c348753fbb17572a813127df2278a1ec527/laya/router.py). |

### Exact Hugging Face checkpoint metadata

The following values are from the official Hugging Face model metadata for
the exact revisions used by the pilot. The API and file links are revision-
qualified so that a later `main` update cannot silently change the identity.

| Candidate | Exact HF revision and metadata | Relevant config/model-card facts |
|---|---|---|
| systemone-lite | [`dwidlee/systemone-lite-0.5b` API metadata](https://huggingface.co/api/models/dwidlee/systemone-lite-0.5b) reports SHA `06b28ed3c5da1d94a6abc015df566ae6408dc5be`, `lastModified=2026-09-20T13:45:02Z`, `pipeline_tag=text-generation`, and Transformers. Revision-qualified [`README.md`](https://huggingface.co/dwidlee/systemone-lite-0.5b/raw/06b28ed3c5da1d94a6abc015df566ae6408dc5be/README.md). | The card identifies an Apache-2.0 Qwen2.5-0.5B base, mixed SFT data, 43,200 rows / 10,800 per gym, and option-alias next-token scoring. Revision-qualified [`config.json`](https://huggingface.co/dwidlee/systemone-lite-0.5b/raw/06b28ed3c5da1d94a6abc015df566ae6408dc5be/config.json) reports `Qwen2ForCausalLM`, 24 layers, hidden size 896, 14 Q heads / 2 KV heads, vocabulary 151,936, 32,768 maximum positions, tied embeddings, and `bfloat16` dtype. |
| laya multilingual | [`convaiinnovations/laya-multilingual` API metadata](https://huggingface.co/api/models/convaiinnovations/laya-multilingual) reports SHA `052592a15d198d9ad47da779604259b10b47b7aa`, `lastModified=2026-09-19T09:55:03Z`, `pipeline_tag=text-classification`, Transformers, multilingual language tags, and Apache-2.0. Revision-qualified [`README.md`](https://huggingface.co/convaiinnovations/laya-multilingual/raw/052592a15d198d9ad47da779604259b10b47b7aa/README.md). | The card describes a non-autoregressive multilingual typed-decision model with an mmBERT-base backbone, 100+ language coverage, a 1,024-token budget, and a 256-token question/option head budget. The revision-qualified [`encoder/config.json`](https://huggingface.co/convaiinnovations/laya-multilingual/raw/052592a15d198d9ad47da779604259b10b47b7aa/encoder/config.json) reports `ModernBertForMaskedLM`, 22 layers, hidden size 768, 12 heads, vocabulary 256,000, and 8,192 maximum positions; [`rl_agent_config.json`](https://huggingface.co/convaiinnovations/laya-multilingual/raw/052592a15d198d9ad47da779604259b10b47b7aa/rl_agent_config.json) points to `jhu-clsp/mmBERT-base`, sets `max_len=1024`, `head_max_len=256`, temperature values to `1.0`, and records 15,987 updates / 4 epochs / 4.97 hours. |
| Qwen2.5-Coder-1.5B-Instruct control | The exact benchmark GGUF repo’s [`alphaduriendur` API metadata](https://huggingface.co/api/models/alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF) reports SHA `9e924818f0f0ccd7869f4bfd7e443c0d94bd4768`, `lastModified=2025-09-25T01:10:02Z`, one GGUF file (`qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`), text-generation, and Apache-2.0. Its revision-qualified [`README.md`](https://huggingface.co/alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/raw/9e924818f0f0ccd7869f4bfd7e443c0d94bd4768/README.md) states that it was converted from the official Qwen checkpoint using GGUF-my-repo. | The official base model’s [`Qwen` API metadata](https://huggingface.co/api/models/Qwen/Qwen2.5-Coder-1.5B-Instruct) reports SHA `2e1fd397ee46e1388853d2af2c993145b0f1098a` and `lastModified=2025-01-12T02:05:01Z`. Its revision-qualified [`README.md`](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/raw/2e1fd397ee46e1388853d2af2c993145b0f1098a/README.md) identifies an English 1.54B causal LM with 28 layers, 12 Q heads / 2 KV heads, and 32,768-token context; the matching [`config.json`](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/raw/2e1fd397ee46e1388853d2af2c993145b0f1098a/config.json) reports hidden size 1,536, vocabulary 151,936, tied embeddings, and `bfloat16`. This is base-model metadata for the exact GGUF candidate, not a claim that the unquantized weights were benchmarked. |
