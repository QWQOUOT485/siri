# Local AI Decision-Model / Jev-Style Benchmark Plan

This is the dedicated plan for the P2.5 Local AI decision-model benchmark.
It is **evaluation-only research**. It is not production promotion, executable
fallback approval, or an expansion of Local AI authority.

The production boundary remains unchanged:

```text
benchmark winner
≠ production approval
≠ executable authority
```

`LOCAL_AI_FALLBACK_APPROVED=false` must remain unchanged. Benchmark results,
including a strong result or a benchmark winner, do not authorize executable
fallback. Any future promotion still requires the separate grounding, policy,
fail-closed, production-aligned shadow, real Windows/Spotify/Siri, and
independent review gates recorded below.

This document preserves the existing benchmark design and candidate set from
`TASKS.md`. It records a future research protocol only; no benchmark is run by
this documentation relocation.

## P2.5 — Open System One / Jev-like local model benchmark

Build a reproducible local benchmark for open Jev-like / System-One-style
decision models. This is an evaluation task only. It must not expand Local AI
authority, enable executable fallback, or set
`LOCAL_AI_FALLBACK_APPROVED=true`.

The goal is not to find the largest model. The goal is to determine which
architecture best fits this Agent's narrow Chinese Siri semantic-recovery task
under the existing deterministic grounding and policy boundary.

### Control baseline

Keep the current generative baseline as the control row:

- `qwen2.5-coder-1.5b-instruct` in the existing prompt / strict-schema path.
- Preserve the current frozen 109-case results as historical evidence; rerun
  only when the benchmark harness, prompt/schema, model build, or comparison
  protocol requires an exact aligned run.

### Fixed eight-candidate set

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

### Stage A — Run released models / inference methods as-is

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

### Stage B — Agent-specific adaptation of finalists

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

### Benchmark protocol

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

### Hardware protocol

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

### Fairness rules

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

### Output artifact

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

### Research success criteria

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
