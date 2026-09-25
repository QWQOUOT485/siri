# Local AI Sanitized Combined Benchmark Evidence — 2026-09-20

This is a sanitized combined record of the fixed-corpus loopback benchmark.
It is evaluation evidence only; it is not a model recommendation, production
acceptance, or fallback-promotion approval. No production AI setting changed,
and no model output was allowed to execute an action.

## Evidence identity

- Benchmark baseline at run start / `main`: `f1038bab2d56093a2a78f693a4cc89e8cb6c5cbc`
- Previous completed rows: `aecc6ddb13624bb06c587242aa5dbe833d3741bc`
- Missing row completed at the benchmark baseline commit: `qwen3-4b`
  strict-schema mode
- `scripts/ai_model_poc.py` and the fixture were unchanged between the two
  row-source commits; the combined table preserves each row's exact source
  commit instead of claiming that earlier requests were rerun.
- The shared branch advanced with unrelated semantic-memory commits after the
  benchmark ran; those later commits are not silently substituted for the
  row-source commits below.
- Fixture: `tests/fixtures/ai_intent_cases.json`
- Fixture SHA-256: `c5fb156fb3384a6777a9533bec1b837136170ba198bb508dadcc5df9cce7fbb1`
- Cases: 109 total; 63 supported; 36 deterministic-only; 10 safety-only
- Prompt/schema evidence hash: `12b29cfd557bb119506ee00444677b5d149beb9ea2fab7002dde03caf0b83318`
- Endpoint mode: same-host loopback `http://127.0.0.1:1234/v1`
- LM Studio: ProductVersion `0.4.20.0`, FileVersion `0.4.20+1`, CLI commit `71bd99c`
- Settings: temperature `0`, max completion tokens `256`, timeout `5s`,
  server context settings unchanged; prompt-only and strict-schema modes
- Raw JSONL/CSV remains under ignored `runtime/ai_poc/`; no raw prompts,
  model output, tokens, credentials, Spotify URIs, or Spotify IDs are committed.

## Exact model inventory

All model IDs were read from the local LM Studio catalog, not inferred from
filenames.

| Exact model ID | Parameters | Quantization | File size |
|---|---:|---|---:|
| `qwen3.5-0.8b` | 0.8B | Q4_K_M | 529,297,312 bytes |
| `qwen2.5-coder-1.5b-instruct` | 1.5B | Q4_K_M | 986,048,576 bytes |
| `qwen3-4b` | 4B | Q4_K_M | 2,497,280,800 bytes |

## Combined results

`JSON/schema` reports JSON parse success and strict schema success; they were
equal for every row. Latencies are inference latency for eligible cases.

| Exact model ID | Mode | Row source commit | Transport | JSON/schema | Supported semantic | Semantic-retry | Deterministic safe-unknown | Safety safe-unknown | False execution | Post-grounding false accept | P50 ms | P95 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `qwen3.5-0.8b` | prompt | `aecc6dd` | 100% | 0% | 0% | 0% | 100% | 100% | 0% | 0% | 822.9 | 880.2 |
| `qwen3.5-0.8b` | schema | `aecc6dd` | 100% | 0% | 0% | 0% | 100% | 100% | 0% | 0% | 878.9 | 919.3 |
| `qwen2.5-coder-1.5b-instruct` | prompt | `aecc6dd` | 100% | 100% | 95.24% | 100% | 100% | 100% | 0% | 0% | 188.0 | 202.2 |
| `qwen2.5-coder-1.5b-instruct` | schema | `aecc6dd` | 100% | 100% | 95.24% | 100% | 100% | 100% | 0% | 0% | 193.0 | 208.8 |
| `qwen3-4b` | prompt | `aecc6dd` | 100% | 30.16% | 28.57% | 16.67% | 100% | 100% | 0% | 0% | 1682.0 | 1717.3 |
| `qwen3-4b` | schema | `f1038ba` | 100% | 30.16% | 28.57% | 16.67% | 100% | 100% | 0% | 0% | 1705.9 | 1729.7 |

The safe-unknown rates include categories that the evaluator rejects before
transport by design (`inference_attempted=false`); they are gate-safety
evidence, not proof that the model understood those requests.

## Evidence review

- `qwen3.5-0.8b`: all 63 eligible cases in both modes returned transport-successful
  but non-JSON content. The evaluator safely reduced them to `unknown`.
- `qwen2.5-coder-1.5b-instruct`: both modes retained 60/63 supported semantic
  cases (95.24%) and 6/6 semantic-retry cases (100%). The remaining supported
  errors are the documented album/artist-role mistakes in album-hint phrasing.
- `qwen3-4b`: strict-schema completion is now present, but 44/63 eligible
  cases were JSON parse failures; only 18/63 supported cases were semantically
  correct and 1/6 semantic-retry cases were correct. Structured output did not
  repair the quality failure observed in prompt mode.
- Across all completed rows, observed false execution and observed
  post-grounding false acceptance were both zero. This is bounded fixed-corpus
  evidence, not a real Windows/Spotify/Siri acceptance claim.
- The benchmark does not make a final model selection. In particular,
  `qwen3-4b` is not a viable quality result under the initial benchmark
  thresholds, while the stronger `qwen2.5-coder-1.5b-instruct` row still needs
  production-aligned shadow acceptance and an independent promotion review.

## Gate status

`LOCAL_AI_MODE` remains `off` or `shadow` only, and
`LOCAL_AI_FALLBACK_APPROVED=false` remains mandatory. No Windows Agent process,
real Spotify playback, Siri voice flow, or executable fallback acceptance was
performed by this benchmark.

The next evidence gate is production-aligned loopback shadow acceptance against
the current source, exact configuration, and the candidate configuration under
review, followed by deterministic regression checks and a separate independent
promotion review.
