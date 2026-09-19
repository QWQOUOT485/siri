# Local AI Sanitized Benchmark Evidence — 2026-09-19

This is a compact, reproducible evidence summary for the guarded Local AI
shadow path. It contains no prompts, raw model output, tokens, credentials, or
Spotify identifiers.

## Evidence identity

- Reviewed source commit: `718a5449366031ff43bd283ed7e3d1d97a7873db`
- Fixture: `tests/fixtures/ai_intent_cases.json`
- Fixture SHA-256: `c5fb156fb3384a6777a9533bec1b837136170ba198bb508dadcc5df9cce7fbb1`
- Case counts: 109 total; 63 `supported`; 36 `deterministic_only`; 10 `safety_only`
- Prompt/schema SHA-256: `12b29cfd557bb119506ee00444677b5d149beb9ea2fab7002dde03caf0b83318`
- Endpoint mode: same-host loopback `http://127.0.0.1:1234/v1`
- LM Studio: ProductVersion `0.4.20.0`, FileVersion `0.4.20+1`, CLI commit `71bd99c`
- Model: `qwen2.5-coder-1.5b-instruct`, GGUF `Q4_K_M`, 1.5B, 986,048,576 bytes
- Inference settings: temperature `0`, max completion tokens `256`, timeout `5s`,
  server context settings unchanged, prompt-only and strict-schema modes
- Local AI runtime mode: `off` by default; this evidence does not authorize
  fallback or executable model output.

## Results

| Mode | AI calls | Transport | JSON | Schema | Intent | Supported semantic | Semantic-retry | Deterministic safe-unknown | Safety safe-unknown | False execution | Post-grounding false accept | P50 ms | P95 ms | Max ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prompt | 63 | 100% | 100% | 100% | 100% | 95.24% | 100% | 100% | 100% | 0% | 0% | 183.1 | 203.1 | 209.4 |
| schema | 63 | 100% | 100% | 100% | 100% | 95.24% | 100% | 100% | 100% | 0% | 0% | 188.8 | 211.9 | 219.7 |

## Known limits

- Three supported cases still misclassify the album/artist role in
  `X 專輯的 Y` phrasing. The model remains behind deterministic grounding and
  the existing Spotify resolver.
- The full multi-model campaign is incomplete; this file is not a model
  recommendation or production-promotion approval.
- No claim is made here about Windows Agent, real Spotify playback, Siri, or
  production fallback acceptance. Those require a separate runtime gate.
- The ignored JSONL/CSV run artifacts remain local; this committed summary is
  the auditable sanitized record for the exact source/model/configuration above.
