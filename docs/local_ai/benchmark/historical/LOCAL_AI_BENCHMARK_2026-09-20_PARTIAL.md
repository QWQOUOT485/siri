# Local AI Shadow Benchmark — Partial Run 2026-09-20

This is an interrupted, sanitized record of a loopback-only Local AI shadow
benchmark. It is not a production acceptance result, model recommendation, or
fallback-promotion approval. No production AI setting was changed and no model
output was allowed to execute an action.

## Run identity

- Source commit: `aecc6ddb13624bb06c587242aa5dbe833d3741bc`
- Benchmark inputs were unchanged from the earlier reviewed source commit
  `718a5449366031ff43bd283ed7e3d1d97a7873db`
- Fixture: `tests/fixtures/ai_intent_cases.json`
- Fixture SHA-256: `c5fb156fb3384a6777a9533bec1b837136170ba198bb508dadcc5df9cce7fbb1`
- Prompt/schema evidence hash: `12b29cfd557bb119506ee00444677b5d149beb9ea2fab7002dde03caf0b83318`
- Cases: 109 total; 63 supported; 36 deterministic-only; 10 safety-only
- Endpoint: same-host loopback `http://127.0.0.1:1234/v1`
- Settings: temperature `0`, max completion tokens `256`, timeout `5s`,
  unchanged LM Studio server context settings, prompt and strict-schema modes
- Run result: intentionally paused before `qwen3-4b` strict-schema mode
- Raw JSONL/CSV output remains in ignored `runtime/ai_poc/2026-09-20/` and is
  not committed.

## Models observed in the local LM Studio catalog

All model IDs below were read from the local `lms ls --json` result; they were
not inferred from filenames.

| Model ID | Parameters | Quantization | File size |
|---|---:|---|---:|
| `qwen3.5-0.8b` | 0.8B | Q4_K_M | 529,297,312 bytes |
| `qwen2.5-coder-1.5b-instruct` | 1.5B | Q4_K_M | 986,048,576 bytes |
| `qwen3-4b` | 4B | Q4_K_M | 2,497,280,800 bytes |

## Completed results

All completed rows used the same 109-case fixture. `P95` is inference latency
for eligible cases. The two false-acceptance columns stayed at zero in every
completed mode.

| Model | Mode | Transport | JSON | Supported semantic | Semantic-retry | Deterministic safe-unknown | Safety safe-unknown | P95 ms | False execution | Post-grounding false accept |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `qwen3.5-0.8b` | prompt | 100% | 0% | 0% | 0% | 100% | 100% | 880.2 | 0% | 0% |
| `qwen3.5-0.8b` | schema | 100% | 0% | 0% | 0% | 100% | 100% | 919.3 | 0% | 0% |
| `qwen2.5-coder-1.5b-instruct` | prompt | 100% | 100% | 95.24% | 100% | 100% | 100% | 202.2 | 0% | 0% |
| `qwen2.5-coder-1.5b-instruct` | schema | 100% | 100% | 95.24% | 100% | 100% | 100% | 208.8 | 0% | 0% |
| `qwen3-4b` | prompt | 100% | 30.16% | 28.57% | 16.67% | 100% | 100% | 1717.3 | 0% | 0% |

## Observed limits

- `qwen3.5-0.8b` returned transport-successful but non-JSON content for all
  63 eligible cases in both modes; the guarded evaluator safely reduced these
  cases to `unknown`.
- `qwen2.5-coder-1.5b-instruct` reproduced the earlier 95.24% supported
  semantic result. The remaining supported errors are still the documented
  album/artist-role cases.
- `qwen3-4b` prompt mode completed all 109 cases but produced only 30.16% JSON
  parse success and 28.57% supported semantic accuracy. Its strict-schema mode
  was not completed.
- The partial run does not justify selecting a model. In particular, the
  benchmark does not authorize `LOCAL_AI_FALLBACK_APPROVED=true`.
- No Windows Agent, real Spotify playback, Siri voice, or production fallback
  acceptance was performed in this run.

## Verification at pause

- AI unit/security tests: `34 passed`, with 2 existing dependency deprecation
  warnings.
- `compileall` for `app`, `scripts`, and `tests`: passed.
- The benchmark worker processes were stopped after the user requested a pause.

## Smallest next action

Resume only the missing row with the same endpoint, fixture, settings, and
source commit:

```powershell
.\.venv\Scripts\python.exe scripts\ai_model_poc.py `
  --base-url http://127.0.0.1:1234/v1 `
  --model qwen3-4b `
  --mode schema `
  --timeout 5 `
  --output-dir runtime\ai_poc\2026-09-20-resume
```

After that single mode is complete, perform a separate review of the combined
evidence. Keep the runtime mode `off` or `shadow` until the documented
production-loopback, real Windows/Spotify/Siri, and independent promotion gates
are all satisfied.
