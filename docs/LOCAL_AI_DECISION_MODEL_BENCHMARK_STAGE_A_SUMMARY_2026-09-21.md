# Local AI Decision-Model Benchmark — Stage A Final Synthesis and Stage B Gate — 2026-09-21

This is the final sanitized synthesis of the reviewed Stage A evidence. It is
evaluation-only documentation. It is not a production model selection,
executable fallback approval, Windows acceptance, Spotify acceptance, Siri
acceptance, deployment authorization, or Stage B execution.

`LOCAL_AI_FALLBACK_APPROVED=false` remains unchanged. Production Local AI
authority remains the deterministic path and the existing guarded/shadow
boundary.

## Gate result

**Formal Stage B gate: NO STAGE B FINALIST FROM RELEASED STAGE A MODELS.**

No released candidate passes the normal Stage B gate. The control remains the
only row with complete semantic-slot evidence and a safe full-semantic result;
it is a comparison baseline, not a newly selected Stage B finalist. Every
typed-decision candidate either fails the supported `unknown` safety boundary,
fails supported play/Chinese quality, lacks the required slots, lacks a
released checkpoint, or has an unresolved hardware/identity boundary.

This conclusion is based on the already-reviewed artifacts only. No model
inference, download, training, fine-tuning, corpus construction, or benchmark
rerun was performed while preparing this synthesis.

## Protocol and evidence identity

- Source/base reviewed for this synthesis: `ebdc257d2884649285418018c3d8c7493517bb91`.
- Frozen corpus: `tests/fixtures/ai_intent_cases.json`, 109 cases, SHA-256
  `60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`.
- The reviewed reports state the supported boundary as 63 rows: 57 expected
  `spotify_play_track` and 6 expected `unknown`; 36 deterministic-only and 10
  safety-only rows were gated before model input.
- The benchmark harness is benchmark-only, does not import production `app`,
  and has no path from model output to `ValidatedAction`.

## Control baseline

`qwen2.5-coder-1.5b-instruct` is kept separate because it uses the existing
strict-schema semantic path rather than a typed-intent-only decision route.
The reviewed control result is **95.24% full semantic accuracy**, complete
track/artist/album slot evidence, 100% play recall, 100% unknown recall, and 0%
conditional expected-unknown false acceptance. Its typed-intent accuracy is
100% on the 63 supported rows. Typed rows below are not directly equivalent to
this full-semantic control.

## Final Stage A comparison

Percentages are from the applicable reviewed rows. `n/a` means the released
route did not expose or establish that evidence; it is not zero. P50/P95 for
the non-control rows are CPU exploratory timings because the RX 9070 XT Python
backend was blocked. They are not GPU qualification results. `Conditional
unknown FA` uses the six supported expected-unknown rows only.

| Row | Architecture / method | Parameters | Exact model revision | Hardware-aligned status | Quality-run status | Typed intent | Full semantic | Play recall | Unknown recall | Balanced intent | Conditional unknown FA | Slots | True post-grounding | Chinese / mixed | Brier / ECE | P50 / P95 context | Model/blocker state | Stage B eligibility |
|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|
| **Control — qwen2.5-coder-1.5b-instruct** | Qwen2.5-Coder 1.5B autoregressive strict-schema JSON | 1.5B | `alphaduriendur/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | `LMSTUDIO_LOCAL_BACKEND_GPU_OFFLOAD_UNQUALIFIED` | control loopback quality run complete | 100% | **95.24%** | 100% | 100% | 100% | **0%** | complete | 0% | 100% / 100% | n/a / n/a | 177.5 / 193.4 ms; LM Studio control, backend offload unqualified | available control baseline; not a new finalist | comparison baseline only |
| systemone-lite | Qwen2.5-0.5B frozen/SFT option-restricted next-token scoring + prefix KV | 494,032,768 | `dwidlee/systemone-lite-0.5b@06b28ed3c5da1d94a6abc015df566ae6408dc5be` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 90.48% | n/a | 100% | **0%** | 50% | **100%** | unavailable | n/a | 88.24% / 100% | 0.0919 / 0.0762 | 301.6 / 316.6 ms; CPU exploratory, not GPU | released route; majority-play behavior and safety stop | **No — unknown recall collapse, 6/6 false accepts, no slots** |
| kev | Qwen2.5-0.5B LoRA + trained pointer/readout decision head | 494,032,768 | `jaredpalmer/kev-0.5b@2679c20e6dde32fb3c4f97ecdad2e6e92bb88a06` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 15.87% | n/a | **7.02%** | 100% | 53.51% | 0% | unavailable | n/a | 11.76% / 12.50% | 0.4325 / 0.5806 | 131.8 / 139.8 ms; CPU exploratory, not GPU | released route; severe supported-play failure | **No — play and language quality fail** |
| eve-rlcd | Qwen3-0.6B supervised warmup + RLCD-style calibrated decision training | 596,049,920 | `anthonym21/qwen3-0.6b-rlcd-decision@b327ec5efb5fdbf8bfafa3b369720ac5f6434b05` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 85.71% | n/a | 94.74% | **0%** | 47.37% | **100%** | unavailable | n/a | 82.35% / 100% | 0.1221 / 0.0923 | 302.1 / 322.0 ms; CPU exploratory, not GPU | released route; high play recall but unsafe unknown behavior | **No — 6/6 false accepts and unknown collapse** |
| decider | Qwen3.5-2B one-pass typed decision with trained label projection | 1,881,825,088 | `Mapika/decider-2b@b37f7e1ba3fbc9238004cf531fabbee2619973fd` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 79.37% | n/a | 87.72% | **0%** | 43.86% | **100%** | unavailable | n/a | 74.51% / 100% | 0.1675 / 0.1925 | 816.8 / 836.4 ms; CPU exploratory, not GPU | released route; trained decision architecture, but base revision is not declared and safety fails | **No released finalist — unknown collapse, 6/6 false accepts, no slots** |
| system-one-open | Gemma Jev-style trained decision model; Gemma 3 270M recipe reference | 270,000,000 reference only | **released trained checkpoint unavailable** | `MODEL_BLOCKED` | explicit blocker; no model rows evaluated | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a; no inference | no released checkpoint; no Gemma base substitute was run | **No — no released checkpoint / no quality evidence** |
| laya | multilingual mmBERT-class non-autoregressive encoder + decision head | 321,908,998 | `convaiinnovations/laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 53.97% | n/a | 49.12% | **100%** | 74.56% | **0%** | unavailable | n/a | 50.98% / 50% | 0.2701 / 0.4002 | 66.2 / 69.6 ms; CPU exploratory, not GPU | released route; safest typed boundary among non-control rows, but weak play/Chinese and no slots | **No released finalist — adaptation research only** |
| Verdict-open-jev | ModernBERT ~151M non-autoregressive encoder decision engine | 151,378,176 | `heman10x/rlcd-modernbert-151m@8af2496eb63c7fa66d7d234e1f62629380030eb4` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 90.48% | n/a | 100% | **0%** | 50% | **100%** | unavailable | n/a | 88.24% / 100% | 0.1130 / 0.1637 | 92.0 / 100.6 ms; CPU exploratory, not GPU | released route; play-majority behavior and safety stop | **No — unknown collapse, 6/6 false accepts, no slots** |
| open-jev-deberta-v3-large | DeBERTa-v3-large encoder + typed option scoring + probabilities | 437,159,937 | `com-kotobalabs/open-jev-deberta-v3-large@19bf9a64815add579fbf6c907bef584d9277a8e4` | `RX_9070_XT_BACKEND_BLOCKED` | exploratory CPU quality run complete | 90.48% | n/a | 100% | **0%** | 50% | **100%** | unavailable | n/a | 88.24% / 100% | 0.1518 / 0.2348 | 235.8 / 241.3 ms; CPU exploratory, not GPU | released route; high play score does not offset unsafe unknown behavior or no slots | **No — unknown collapse, 6/6 false accepts, no slots** |

### How the gate was applied

- The control is the only direct full-semantic comparison: it has slots,
  grounding evidence, and the reviewed 95.24% full-semantic result. A typed
  intent score cannot be called better than that control without slot and
  safety parity.
- `systemone-lite`, `eve-rlcd`, `decider`, `Verdict-open-jev`, and
  `open-jev-deberta-v3-large` all accepted 6/6 supported expected-unknown
  rows. Their 100% conditional false-accept rates are safety stops regardless
  of their play recall, speed, or calibration values.
- `kev` has zero conditional false accepts but only 7.02% play recall and
  very weak Chinese/mixed slices; it does not establish a useful released
  semantic route.
- `laya` is the only non-control released route with both 100% unknown recall
  and 0% conditional false acceptance. Its 49.12% play recall, 50.98% Chinese
  slice, 50% mixed slice, poor calibration, unavailable slots, and blocked
  backend prevent released-model advancement.
- `system-one-open` has no released trained checkpoint. The benchmark did not
  substitute a base model, so it has no invented quality score.

## Architecture-only adaptation candidates

Because no released candidate passes the normal gate, the following are at
most **research candidates for a future Agent-specific adaptation study**. They
are not Stage B finalists, are not selected for training by this change, and
cannot authorize production fallback.

### 1. laya — multilingual encoder safety-first research candidate

- **Released Stage A failure:** 53.97% typed intent, 49.12% play recall,
  50.98% Chinese and 50% mixed slice, no entity slots, Brier/ECE
  0.2701/0.4002, and RX 9070 XT backend blocked.
- **Why the architecture remains interesting:** it is a multilingual,
  non-autoregressive decision-head route and is the only non-control released
  row with 100% unknown recall and 0% conditional expected-unknown false
  acceptance. That is a safety-positive starting boundary, not a quality pass.
- **What adaptation must fix:** learn Agent-specific play/unknown boundaries,
  Traditional Chinese and mixed-language phrasing, track/artist/album spans,
  ambiguity and incomplete requests, calibration, and a qualified AMD backend.
- **Required outcome:** it must meet every predeclared Stage B threshold below;
  unknown safety cannot be traded for its current speed or multilingual design.

### 2. decider — typed-decoder architecture research candidate

- **Released Stage A failure:** 79.37% typed intent, 87.72% play recall,
  0% unknown recall, 6/6 conditional false accepts, no slots, P95 836.4 ms
  on CPU, RX 9070 XT backend blocked, and the model card does not declare the
  exact Qwen base revision.
- **Why the architecture remains interesting:** its one-pass trained label
  projection on a larger Qwen3.5-2B-class backbone is a plausible route for
  learning the Agent's narrow semantic decision boundary without forcing JSON
  generation. It also provides a complementary decoder architecture to the
  multilingual encoder candidate.
- **What adaptation must fix:** unknown rejection/calibration first, then
  Agent-specific Traditional Chinese and mixed-language semantics, bounded
  track/artist/album extraction, latency, model identity completeness, and
  AMD backend support. The current 100% false-accept rate makes it unsuitable
  for any execution path.
- **Required outcome:** it must meet every predeclared Stage B threshold below;
  its larger backbone and typed score do not waive any safety or slot gate.

No other released row has a stronger architecture-only case on the reviewed
evidence. In particular, high play-majority scores from systemone-lite,
Verdict, or Open-Jev-DeBERTa do not justify adaptation when all six supported
unknown rows are accepted and no slots are exposed. `system-one-open` cannot be
recommended until a released checkpoint with a complete, reviewable identity
exists.

## Future Stage B plan — proposal only, not executed

If a separately approved Stage B study is opened, it must use a new
Agent-specific corpus that is disjoint from the frozen 109-case evaluation
corpus. The corpus must have explicit train, validation, and held-out test
splits; frozen-evaluation answers and identifiers must not be copied into
training data or tuning prompts.

The proposed corpus should include:

- Traditional Chinese commands and colloquial Siri phrasing;
- mixed Chinese/English artist names and titles;
- ASR-like substitutions, omissions, spacing, and homophone mistakes;
- hard `spotify_play_track` vs `unknown` negatives;
- ambiguous, incomplete, and entity-boundary-confusing track requests;
- track, artist, and album slot boundaries, including absent/optional slots;
- malformed, adversarial, unsupported-domain, URL/path, shell-like, and
  high-risk requests that must stay unknown or be rejected before AI.

It must contain no secrets, OAuth data, Spotify IDs/URIs, private paths,
sensitive logs, user credentials, or frozen-evaluation answer leakage. The
corpus must remain outside production configuration and must not be used as a
reason to enable Local AI.

### Predeclared Stage B success gates

These thresholds are defined before any future training or tuning and may not
be relaxed after seeing results:

| Gate | Required result |
|---|---|
| Supported `unknown` recall | **100%** on the held-out supported expected-unknown set |
| Conditional expected-unknown false acceptance | **0%**; no expected-unknown row may be accepted as play |
| Supported play recall | **≥95%** on the held-out supported expected-play set |
| Track / artist / album slots | **≥95% per evaluated slot**, with correct absence handling and entity boundaries |
| Full semantic accuracy | **≥95%** after slot and semantic evaluation |
| Traditional Chinese slice | **≥95%** |
| Mixed Chinese/English slice | **≥95%** |
| Calibration, where probabilities are exposed | **Brier ≤0.10 and ECE ≤0.05** |
| Safety and grounding | 0% post-grounding false acceptance; no execution-authority fields; fail closed on malformed/timeout/backend errors |
| Local hardware fit | Qualified RX 9070 XT 16 GB backend, successful load/readback, no CPU-only fallback or backend blocker; proposed operational target P95 **≤250 ms** under the fixed protocol |

All gates are conjunctive. A model that is fast, small, or high-scoring on
typed play alone fails if any safety, slot, grounding, calibration, or
hardware gate fails.

## Storage and machine boundary

The final external-weight policy is:

```text
D:\ai\ai
```

- External Stage A weights were migrated under `D:\ai\ai\{candidate}`.
- File-count, byte-count, and SHA-256 migration verification passed.
- The old copies remain recoverable under
  `D:\ai\ai\_migration-backup-20260921`; this task does not delete them.
- The LM Studio-managed control remains under its
  `D:\ai\ai\alphaduriendur\...` publisher/repository path.
- This machine-specific storage policy is separate from portable source
  configuration and does not change production model/backend settings.

## Evidence boundary and next action

Stage A is complete as an evidence inventory: the control plus all eight fixed
candidates have a reviewed run, a reviewed historical result, or an explicit
blocker. Stage B is **not started**. No model was promoted, no production app
code changed, and no Windows, Spotify, Siri, deployment, Semantic Memory, or
Local AI fallback acceptance was run for this synthesis.

The next safe action is independent review of this synthesis and its source
reports. Any future Stage B work requires a separately approved task and must
revalidate model identity, hardware support, corpus separation, and every
predeclared gate.

## Source reports

- [Benchmark plan](LOCAL_AI_DECISION_MODEL_BENCHMARK_PLAN.md)
- [Stage A pilot](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_PILOT_2026-09-21.md)
- [Stage A Batch 2A](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_BATCH_2A_2026-09-21.md)
- [Stage A Batch 2B](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_BATCH_2B_2026-09-21.md)
- [Candidate manifest](../scripts/local_ai_benchmark_manifest.py)
- [Benchmark harness and result schema](../scripts/local_ai_benchmark_harness.py)
