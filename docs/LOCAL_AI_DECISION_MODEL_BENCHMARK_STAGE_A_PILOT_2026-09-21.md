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
  **10 safety-only**. Deterministic-only and safety-only rows were not sent to
  a model, matching the existing isolated PoC boundary.
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
  machine's CPU. This collected quality evidence but is **not** an RX 9070 XT
  GPU latency result. The control used the existing LM Studio loopback route;
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
semantic accuracy is intentionally not calculated.

| Candidate | Route / backend | Transport / schema | Supported intent | Full semantic / slots | Retry intent | Deterministic safe unknown | Safety safe unknown | False execution | Post-grounding false accept | P50 / P95 ms | Brier / ECE | Load ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | strict JSON / LM Studio loopback | 100% / 100% | 100% | **95.24% / available** | 100% | 100% | 100% | 0% | 0% | 177.5 / 193.4 | n/a / n/a | 157.0 |
| systemone-lite | option scoring / Python CPU | 100% / 100% | **90.48%** | n/a / unavailable | 83.33% | 100% | 100% | 0% | **5.50%** | 301.6 / 316.6 | 0.0919 / 0.0762 | 5,101.2 |
| laya multilingual | encoder classification / Python CPU | 100% / 100% | 53.97% | n/a / unavailable | 66.67% | 100% | 100% | 0% | 0% | **66.2 / 69.6** | 0.2701 / 0.4002 | 16,580.1 |

Language-slice intent accuracy for the 63 supported rows:

| Candidate | Chinese | English | Mixed |
|---|---:|---:|---:|
| Control | 100% | 100% | 100% |
| systemone-lite | 88.24% | 100% | 100% |
| laya multilingual | 50.98% | 100% | 50% |

## Interpretation and stop line

- The control is the only row with complete entity-slot evidence. It retained
  the prior strict-schema quality boundary in this aligned rerun.
- systemone-lite is the stronger typed-intent row in this pilot, but it has no
  released slot extraction path, showed 5.50% post-grounding false acceptance
  on the supported corpus, and ran CPU-only. It is not a production semantic
  replacement.
- laya multilingual is fast on CPU after load, but its unadapted typed-intent
  result and calibration are materially weaker on this Chinese/mixed corpus;
  its released route also has no entity-slot output for this Agent task.
- No finalist is promoted or selected. The remaining fixed candidates were not
  run because this task explicitly stops after the three-model Stage A pilot.
  Stage B adaptation, if later authorized, requires a separate reviewed corpus,
  held-out split, entity-slot design, and independent promotion review.

## Evidence boundary

All three model loads and all 109 sanitized case rows completed. Raw/local
artifacts remain under ignored `runtime/ai_poc/stage-a-*`; no prompts, raw model
outputs, tokens, credentials, Spotify IDs/URIs, or model weights were added to
Git. Source verification after the implementation change was **379 passed**;
compileall, `pip check`, and `git diff --check` passed, with two existing
dependency deprecation warnings.

No Windows Agent process, production config, Spotify request/playback, Siri
voice flow, installed deployment, or executable Local AI fallback acceptance
was run. The result is source/benchmark evidence only, and
`LOCAL_AI_FALLBACK_APPROVED=false` remains mandatory.
