# Local AI Stage B Adaptation Plan — laya / decider

**Status: design only; not executed.** This document defines a future,
Agent-specific adaptation study. It is not a Stage B finalist decision, a
training authorization, a model recommendation, production promotion, or an
executable fallback change.

`LOCAL_AI_FALLBACK_APPROVED=false` remains mandatory. No model training,
fine-tuning, new model download, frozen Stage A rerun, production `app/`
change, deployment, Spotify call, or Siri acceptance is part of this plan.

## 1. Decision boundary and starting evidence

The reviewed Stage A gate is **NO STAGE B FINALIST FROM RELEASED STAGE A
MODELS**. `laya` and `decider` are architecture-only research candidates, not
finalists or production candidates. The control is a comparison baseline, not
a newly selected finalist.

The frozen Stage A identity is:

- corpus: `tests/fixtures/ai_intent_cases.json`
- 109 cases
- SHA-256: `60ebad4bcafeae7821986ac454ff2e730da7661537b11879aba6f725675bee55`
- supported boundary: 57 expected `spotify_play_track`, 6 expected `unknown`
- 36 deterministic-only and 10 safety-only rows gated before model input

That corpus, its answers, identifiers, and all derived evaluation artifacts
are permanently test-only. They must not be used for Stage B training,
validation, prompt/schema tuning, threshold/calibration fitting, augmentation,
or manual answer correction. The Stage A report explicitly records that no
Stage B work was started and that the frozen corpus must remain separate
([Stage A summary](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md#L23-L36)).

The reviewed released rows explain why adaptation is research-only:

| Candidate | Pinned identity | Reviewed Stage A limitation relevant to Stage B |
|---|---|---|
| `laya` | source `NandhaKishorM/laya@42626c348753fbb17572a813127df2278a1ec527`; model `convaiinnovations/laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa`; 321,908,998 parameters | 53.97% typed intent, 49.12% play recall, 100% unknown recall, 50.98% Chinese / 50% mixed, no slots, CPU-only exploratory timing, RX 9070 XT backend blocked |
| `decider` | source `Mapika/decider@c4daaac28af9fea95d627015cffa2dd5a5926ee6`; model `Mapika/decider-2b@b37f7e1ba3fbc9238004cf531fabbee2619973fd`; 1,881,825,088 parameters | 79.37% typed intent, 87.72% play recall, 0% unknown recall, 6/6 conditional false accepts, no slots, CPU P95 836.4 ms, RX 9070 XT backend blocked; exact base-model revision is not declared |

These values are historical Stage A evidence, not a new inference run. See the
comparison rows and research-candidate rationale in the
[Stage A synthesis](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md#L56-L127).

## 2. Protocol freeze before any compute

Before a future study can train or evaluate either candidate, an independent
reviewer must approve a protocol manifest containing:

1. the candidate name (`laya` or `decider`) and the exact source/model/base
   revisions, with local artifact hashes;
2. the immutable Agent-specific corpus manifest and split hashes below;
3. the adapter version, output schema, tokenizer/configuration, and fixed
   input rendering;
4. the hardware/backend/precision and the rule that CPU fallback is an error;
5. the seed, optimizer, schedule, adapter/head choice, calibration procedure,
   threshold procedure, and all conjunctive success gates;
6. the exact evaluation order: validation, held-out Stage B test, then the
   untouched 109-case Stage A regression set.

After the manifest is frozen, no test result may cause a threshold, split,
prompt, label rule, or report denominator to be changed. A failed candidate
may receive a separately documented new experiment, but it must not reuse the
held-out test for diagnosis or tuning.

The existing benchmark-only harness is the compatibility boundary, not a
production route: it allows only `spotify_play_track` / `unknown`, rejects
execution-authority fields, and marks missing typed-model slots as unavailable
([harness](../scripts/local_ai_benchmark_harness.py#L25-L46),
[typed decision schema](../scripts/local_ai_benchmark_harness.py#L191-L253)).
The Stage B extension may add sanitized span evidence and slot metrics, but it
must preserve the old corpus hash and the old closed intent set.

## 3. Separate Agent-specific corpus

### 3.1 Target size and split contract

The proposed corpus target is **3,000 sanitized utterances**, generated and
reviewed independently of the frozen Stage A fixture. The counts are targets
for a future corpus build, not data that has been created by this task.

| Split | Play | Model-eligible semantic unknown / hard negative | Deterministic-only unknown | Safety-only unknown | Total |
|---|---:|---:|---:|---:|---:|
| Train | 900 | 600 | 180 | 120 | 1,800 |
| Validation | 300 | 240 | 30 | 30 | 600 |
| Held-out Stage B test | 300 | 240 | 30 | 30 | 600 |
| **Total** | **1,500** | **1,080** | **240** | **180** | **3,000** |

The supported model-evaluation subset is the 1,500 play plus 1,080 semantic
unknown rows. The deterministic-only and safety-only rows must be blocked by
the eligibility gate and reported separately; they are not evidence that a
model understood those rows. The held-out test therefore reports both:

- supported play recall on 300 rows and supported unknown recall on 240 rows;
- deterministic-only and safety-only gate-safe-unknown rates on 30 rows each;
- all-unknown false-execution evidence across all 300 held-out unknown rows.

The resulting class balance is intentionally close to 50/50 overall and keeps
a large hard-negative population. No 57:6-style distribution is acceptable
without explicit class weighting, balanced sampling, and class-wise reporting.
The report must show denominators for every slice; overall accuracy is never a
gate by itself.

Each split must contain all of the following where applicable, with the test
set containing at least 100 `zh-Hant` rows and at least 100 mixed
Chinese/English rows, and each of those slices containing both supported play
and semantic-unknown examples:

- `language_slice`: one of `chinese`, `english`, or `mixed`, using the existing
  benchmark vocabulary;
- named track positives, with track-only, artist-plus-track, and
  artist/album-plus-track forms;
- semantic unknowns, incomplete requests, and boundary-confusing requests;
- deterministic-only controls and safety-only hostile negatives.

The held-out test is copied to a read-only evaluation directory only after the
protocol manifest is frozen. Its labels are not available to training code,
prompt construction, threshold fitting, or checkpoint selection.

### 3.2 Required data families

The corpus builder must provide reviewed examples for:

- Traditional Chinese Spotify play commands;
- colloquial Taiwanese/Mandarin phrasing, omissions, and conversational
  wording;
- Chinese + English artist/title mixtures;
- ASR-like spelling, homophone, character, spacing, and punctuation errors;
- named track requests with no artist, with an artist, and with an album hint;
- live/remaster/version ambiguity and requests whose version wording must not
  become an invented slot;
- incomplete requests, artist-only requests, pronouns, and unresolved
  references;
- unsupported domains and requests that mention music-like words without a
  supported named-track action;
- playback controls that remain deterministic-only;
- shell/path/URL, process, shutdown, force-close, firewall, and other
  system-administration hostile negatives.

`artist-only` is an unknown example for the initial allowlist because a
`spotify_play_track` result requires a grounded track. A request may mention
an artist or album, but a missing track must not be converted into an inferred
track or catalog target.

### 3.3 Record schema and labels

Each sanitized record has a stable opaque case ID and no user/account identity:

```json
{
  "case_id": "sb2_group_00421_variant_03",
  "source_group_id": "template_artist_track_00421",
  "utterance": "幫我播 The Weeknd 的 Blinding Lights",
  "language_slice": "mixed",
  "ai_scope": "supported",
  "expected": {
    "intent": "spotify_play_track",
    "track": {"text": "Blinding Lights", "start": 24, "end": 39},
    "artist": {"text": "The Weeknd", "start": 8, "end": 18},
    "album": null
  },
  "negative_reason": null,
  "template_family": "artist_track",
  "generator_version": "frozen-in-manifest"
}
```

Required label rules:

- `intent` is exactly `spotify_play_track` or `unknown`.
- `track`, `artist`, and `album` are either `null` or a reviewed raw-text
  character span plus its exact source offsets. Positive play rows require a
  track span. Artist and album are optional.
- The canonical label text is the bounded text from the utterance after the
  repository's documented normalization only; it is not a Spotify catalog
  name. Simplified/Traditional variants remain traceable to their raw span.
- Unknown rows carry all three output slots as `null`, even if a hostile or
  unsupported utterance contains entity-like text. Any annotation of a
  mentioned phrase is review metadata, never a model output target.
- `negative_reason` is a finite enum such as `missing_track`,
  `artist_only`, `unresolved_reference`, `ambiguous_version`,
  `unsupported_domain`, `playback_control`, `hostile_system`, `path_or_url`,
  or `malformed_input`.
- No record contains Spotify IDs/URIs, OAuth data, API keys, private paths,
  credentials, raw sensitive logs, clarification tokens, catalog objects, or
  user/account identifiers.

The corpus validator must reject extra fields, control characters, overlong
slots, impossible offsets, unknown intents, non-null slots on unknown rows,
missing track spans on positive rows, and any forbidden execution-authority
field. It must also scan serialized data for secrets and path/URI patterns.

### 3.4 Leakage and duplicate controls

Splitting is by `source_group_id`, not by individual utterance. A group must
contain all paraphrases, ASR variants, translations, punctuation variants,
and the same underlying entity combination. The validator must:

1. canonicalize whitespace, Unicode form, case, punctuation, and the approved
   Traditional/Simplified normalization for comparison only;
2. reject exact canonical duplicates across any split;
3. reject repeated entity/intent/template groups across splits;
4. reject near duplicates using a fixed character n-gram similarity threshold
   and a fixed MinHash/SimHash configuration recorded in the manifest;
5. verify that no Stage A case ID, utterance hash, answer object, or frozen
   identifier appears in any Stage B split;
6. emit split counts and SHA-256 hashes after canonical sorting.

Synthetic generation is allowed only as a source of candidate paraphrases;
every row requires human or independently reviewed label approval. The raw
generation log is not a training artifact if it contains private text.

## 4. Common evaluation protocol

The future adapter returns bounded, untrusted typed evidence in memory. It may
return intent probabilities and sanitized text spans, but never JSON generated
by a decoder and never an execution target. `unknown` always clears all slots.

For every candidate, report at least:

- transport/load success, malformed output, timeout, backend failure, and
  actual device;
- play recall, unknown recall, balanced accuracy, and conditional
  expected-unknown false acceptance;
- full semantic accuracy after intent plus all applicable slot boundaries;
- track, artist, and album accuracy separately, including correct `null`
  handling and exact boundary recovery;
- Traditional Chinese and mixed Chinese/English slice accuracy with
  denominators;
- Brier score and ECE for every exposed probability, calibrated without test
  labels;
- deterministic-only and safety-only safe-unknown rates;
- post-grounding false acceptance and false execution (both must be zero);
- P50/P95 end-to-end latency, model load time, peak VRAM/RAM, and throughput
  only when the backend is qualified;
- option-order flip rate for typed option heads and span invalidity rate.

The evaluator must use the existing benchmark result vocabulary and preserve
the distinction between `supported`, `deterministic_only`, and `safety_only`.
No live Spotify or Windows action is part of this evaluation.

## 5. laya adaptation design

### 5.1 Upstream-compatible surface

The pinned laya implementation builds a sequence with question instructions,
option markers, and the user state, then records marker positions
([`common.py`](../runtime/ai_poc/upstream-batch-2b/laya/laya/common.py#L49-L86)).
Its `DecisionModel` contains the multilingual encoder, optional Transformer
head, question-type embedding, marker scorer, and action head
([`common.py`](../runtime/ai_poc/upstream-batch-2b/laya/laya/common.py#L89-L126)).
`system_one()` runs typed questions in one parallel forward pass and returns
choices, probabilities, confidence, and zero output tokens
([`agent.py`](../runtime/ai_poc/upstream-batch-2b/laya/laya/agent.py#L240-L345)).

The Stage B adapter must preserve the released checkpoint's
`encoder.`, `type_emb.`, `scorer.`, and `act_head.` compatibility prefixes and
must not silently load a different architecture
([loader compatibility check](../runtime/ai_poc/upstream-batch-2b/laya/laya/agent.py#L49-L93)).
The benchmark-only adapter currently forces `device="cpu"` and exposes only
the typed intent, with slot evidence explicitly unavailable
([laya adapter](../scripts/local_ai_stage_a_adapters.py#L423-L464),
[typed conversion](../scripts/local_ai_stage_a_adapters.py#L286-L314)).

### 5.2 Proposed narrowest adaptation

Use a project-owned wrapper/fork around the unchanged released encoder and
typed decision head:

1. **Intent head:** retain the two-option `play` / `unknown` choice. Train the
   decision scorer and bounded abstention/action-confidence head on the
   balanced corpus. Add an explicit validity/abstention loss so low confidence
   or missing-track cases do not become play merely because `play` wins two
   options.
2. **Span head:** extend the sequence builder and collator to return a mask for
   user-state token positions, excluding instructions, option markers, and
   separators. Attach a small non-generative multi-task span head to the
   contextual token states. The first proposal is one shared BIO head with
   `O`, `B/I-TRACK`, `B/I-ARTIST`, and `B/I-ALBUM` labels plus a presence/null
   validity output. Decode only bounded token spans and map them back to raw
   character offsets.
3. **Grounding rule:** only a track span grounded in the original utterance
   can support `spotify_play_track`; an unknown decision, missing track,
   invalid span, or ungrounded span produces `unknown` with all slots null.
   Optional artist/album spans are dropped when they fail deterministic
   grounding.
4. **Training order:** first train only the existing decision heads and new
   span/validity heads with the encoder frozen. If validation cannot pass the
   safety and slot gates, do not broaden the run. A separately approved second
   experiment may add LoRA to a small, predeclared set of upper encoder layers.
   Full encoder fine-tuning is not the default and requires a new VRAM and
   reproducibility review.
5. **Calibration:** fit only a scalar or small per-head temperature on the
   validation split. Store calibration parameters separately with a hash; do
   not fit thresholds, temperature, isotonic maps, or span acceptance rules on
   the held-out test.

This keeps the multilingual non-autoregressive architecture and uses its
existing sequence/context states. It does require a benchmark-owned seam to
expose state-token positions and hidden states; it does not modify production
`app/` or force the encoder to generate JSON.

### 5.3 laya-specific stop conditions

- Any load/readback mismatch, tokenizer mutation not captured in the manifest,
  missing compatibility prefix, or actual CPU fallback stops the run.
- If the span mask includes prompt/options, or a decoded span crosses the
  user-state boundary, stop and fix the adapter before measuring quality.
- Any held-out validation semantic-unknown false acceptance, any positive
  without a valid required track span, or any safety/deterministic row reaching
  the model unexpectedly is a safety stop.
- A head-only run that cannot approach the frozen validation gates must not be
  escalated to full fine-tuning merely to obtain a score; escalate only through
  the predeclared LoRA experiment.

## 6. decider adaptation design

### 6.1 Upstream-compatible surface

The pinned decider model runs a causal LM once, selects hidden states at
answer slots, and projects them through the base LM head onto bounded option
letters; invalid options are masked
([`model.py`](../runtime/ai_poc/upstream-batch-2b/decider/decider/model.py#L7-L28)).
Its inference API returns typed choices and probabilities in one forward pass,
with an `abstain_below` threshold but no trained guarantee that abstention is
semantically safe
([`infer.py`](../runtime/ai_poc/upstream-batch-2b/decider/decider/infer.py#L55-L118)).
The released training script currently uses full-model `.cuda()`, CE with an
optional Brier term, and no Agent-specific slot task
([`train.py`](../runtime/ai_poc/upstream-batch-2b/decider/decider/train.py#L42-L138)).

### 6.2 Proposed structured head

Preserve the one-pass typed decision design; do not turn decider into an
autoregressive JSON generator and do not enumerate Spotify catalog entities as
options.

1. **Intent/abstention:** keep an explicit `play` / `unknown` typed question,
   add a separate supported-intent validity/abstention question, and train
   both on hard unknowns. Do not rely on the literal `none of the above` phrase
   as an abstention feature; the released inference code itself documents that
   earlier training learned that literal string as a special signal
   ([neutralization](../runtime/ai_poc/upstream-batch-2b/decider/decider/infer.py#L26-L40)).
2. **Span extraction:** expose the full hidden-state sequence from the single
   base forward pass. Add typed span answer markers for `track`, `artist`, and
   `album`; each marker's hidden state is a query for a pointer-style start and
   end head over the preceding user-context token positions, plus a null/absent
   outcome. Mask prompt and answer-marker positions from pointer candidates.
3. **Why pointers:** decider is causal, so a pointer query after the complete
   user utterance can attend to both sides of an entity. This is more suitable
   than a token BIO classifier whose early token states cannot see later text,
   and it avoids the unbounded option enumeration that would leak catalog
   assumptions or exceed the typed-option budget.
4. **Joint loss:** retain typed intent CE and optional Brier loss; add weighted
   start/end/null losses and a required-track validity loss. Unknown examples
   train the null/abstain outcome and must never receive entity targets in the
   returned typed evidence.
5. **Training order:** first train the new span/validity heads and the existing
   decision readout with the decoder frozen. If that cannot pass validation,
   stop. A separately approved LoRA run may target predeclared decoder layers;
   full-model adaptation is not assumed to fit the 16 GB target and is not
   authorized by this document.
6. **Calibration:** fit temperature and the final abstention threshold on
   validation only. A low `abstain_below` score cannot waive the 100% unknown
   recall / 0% false-accept gates.

The Stage A safety failure is decisive for triage: decider accepted all six
supported unknown rows and had 0% unknown recall. Its 87.72% play recall and
larger backbone do not justify any execution path until the unknown boundary,
required track, slots, and AMD backend all pass the frozen gates.

### 6.3 decider-specific stop conditions

- The current CUDA-graph engine is not an AMD qualification. If the chosen
  backend cannot run the one-pass model without an undocumented fallback, stop
  and record an explicit backend blocker.
- If pointer candidates include prompt text, answer markers, or padding, stop
  before quality evaluation.
- Any validation unknown false acceptance or null/required-track disagreement
  stops the candidate; do not lower `abstain_below` or remove hard negatives to
  improve play recall.
- OOM, NaN/Inf, gradient overflow, or P95 beyond the predeclared operational
  target at the small run stops escalation until the adapter/configuration is
  independently reviewed.

## 7. AMD RX 9070 XT hardware plan

The only final qualification target is **AMD Radeon RX 9070 XT, 16 GB**, with
external artifacts under `D:\ai\ai`. The RTX 3060 is not a substitute and must
not be used as a silent fallback or pooled memory source.

The recorded environment currently has CPU-only PyTorch; Vulkan/OpenCL probes
exist, but ROCm tooling and DirectML support were not established. Stage A
therefore treated all non-control timings as CPU exploratory evidence. Laya's
loader explicitly falls back to CPU when CUDA/MPS is unavailable or placement
fails ([laya device fallback](../runtime/ai_poc/upstream-batch-2b/laya/laya/agent.py#L155-L227));
the Stage B harness must disable that behavior for qualification and fail if
the actual device is CPU.

| Route | Future status for Stage B | Qualification rule |
|---|---|---|
| ROCm / AMD PyTorch | Preferred if a supported Windows RX 9070 XT stack and both model paths are proven | Must report driver/runtime, PyTorch build, device readback, precision, and no CPU fallback; current venv does not prove it |
| DirectML | Conditional development route only | Must be explicitly supported by the adapter and preserve outputs/metrics; no DirectML package is currently qualified, so it cannot be assumed equivalent to ROCm |
| Vulkan / project-supported route | Unverified for these upstream Transformers/PyTorch training paths | A passing low-level probe is not model qualification; the full load, backward/forward, span head, and readback protocol must pass |
| CPU | Corpus/shape/adapter smoke only | May validate schema and tensor shapes, but cannot produce final Stage B quality, latency, or hardware acceptance evidence |

No major GPU stack is installed as part of this design task. A future backend
setup is a separate, reversible approval with a preflight that records:

- exact GPU identity and available memory;
- driver/runtime and backend versions;
- `torch` build, accelerator visibility, and actual model device;
- local pinned artifact paths and SHA-256 readback;
- precision, sequence length, batch shape, peak VRAM/RAM, and load time;
- an explicit `cpu_fallback=false` assertion.

## 8. Cheap fail-fast experiment order

Each step produces a sanitized report. A stop condition ends the candidate's
current track; it does not authorize ad-hoc retries or a new model.

1. **Protocol/corpus validator, no model:** validate schema, forbidden fields,
   3,000-row counts, split hashes, group separation, near-duplicate rules,
   language minima, and Stage A disjointness. Any failure stops before model
   access.
2. **Hardware and artifact preflight:** verify RX 9070 XT identity, backend,
   local artifact hashes, model/device readback, and no fallback. Any blocked
   backend, unpinned base revision, load mismatch, or CPU placement stops the
   candidate as unqualified; do not score CPU as final evidence.
3. **Tiny adapter smoke:** use a fixed, non-secret 64-row shape smoke set
   (not the Stage A fixture) to check typed output, span masks, null behavior,
   and one forward/backward shape path. Stop on malformed output, invalid span,
   NaN/Inf, or missing required output.
4. **Training-pipeline smoke:** run a predeclared small subset with frozen
   backbone and new heads. Stop on OOM, fallback, no finite loss, broken
   checkpoint reload, or loss/metric logging that cannot be reproduced from
   the manifest.
5. **Small adaptation run:** use a stratified fraction of the training split
   and the untouched validation split. Proceed only if the provisional safety
   checks show 100% validation unknown recall, 0% conditional unknown false
   acceptance, no deterministic/safety leakage, and valid required-track spans.
   These are triage stop checks, not relaxed final gates.
6. **Full head-only adaptation:** run only after steps 1–5 pass. Select the
   checkpoint using validation metrics and frozen calibration procedure. If it
   fails the final conjunctive validation gates, stop before LoRA.
7. **Optional LoRA adaptation:** a separate predeclared experiment only when
   the head-only result identifies a capacity issue and the backend/VRAM review
   passes. Never tune on the held-out test.
8. **Held-out Stage B test:** freeze checkpoint, calibration, thresholds,
   adapter, and report schema; evaluate once and preserve raw artifacts outside
   Git. No diagnosis or tuning after seeing the test.
9. **Untouched Stage A regression:** run the existing 109-case regression only
   as the final read-only comparison step, using its original hash and labels;
   never feed its result back into adaptation.
10. **Independent review:** review source diff, corpus manifest/hashes,
    checkpoint identity, device readback, metrics, error slices, and security
    boundary. A passing research gate still does not authorize production.

## 9. Frozen success gates

These gates are copied from the reviewed Stage A synthesis and are frozen
before any future result. They are conjunctive; no speed, parameter count, or
play-only score can compensate for a failed safety, slot, calibration, or
hardware gate.

| Gate | Required held-out result |
|---|---|
| Supported unknown recall | **100%** on all 240 model-eligible semantic-unknown rows |
| Conditional expected-unknown false acceptance | **0%**; no model-eligible expected-unknown row accepted as play |
| Supported play recall | **>=95%** on all 300 supported play rows |
| Track slot accuracy | **>=95%**, including required presence and exact boundary/grounding behavior |
| Artist slot accuracy | **>=95%** over evaluated presence and absence cases |
| Album slot accuracy | **>=95%** over evaluated presence and absence cases where applicable |
| Full semantic accuracy | **>=95%** after intent plus all applicable slots |
| Traditional Chinese slice | **>=95%** with the predeclared minimum denominator |
| Mixed Chinese/English slice | **>=95%** with the predeclared minimum denominator |
| Calibration | Brier **<=0.10** and ECE **<=0.05** wherever probabilities are exposed |
| Deterministic/safety gate | 100% safe-unknown; no gated row reaches the model unexpectedly |
| Post-grounding false acceptance | **0%** |
| False execution | **0%** in the benchmark harness |
| Backend/hardware | Qualified RX 9070 XT 16 GB load/readback, no CPU fallback or backend blocker |
| Operational latency | P95 **<=250 ms** under the fixed qualified protocol |

For the optional slots, accuracy is computed over both present and absent
labels; a model cannot obtain a slot pass by always returning null. All metrics
must include counts and confidence intervals or exact numerator/denominator.

Even a complete Stage B research pass does not change the production gates:
the deterministic parser, grounding, policy, production-aligned shadow, real
Windows/Spotify/Siri acceptance where required, and separate independent
promotion review remain mandatory.

## 10. Reproducibility manifest

Every future run must record, without secrets:

- project Git SHA and clean/dirty state;
- upstream source/repository SHA, model revision, base-model revision, license,
  artifact path, byte size, and SHA-256;
- training corpus canonical hash, per-split hashes, counts, group/duplicate
  validator version, and label schema version;
- seed(s), tokenizer/config hashes, prompt/sequence renderer version, maximum
  lengths, batch shape, gradient accumulation, and adapter/head configuration;
- optimizer, learning rate, weight decay, warmup, scheduler, epochs/steps,
  class weights, sampling policy, loss weights, and calibration method;
- precision/quantization, backend/driver/runtime, GPU identity and memory,
  peak VRAM/RAM, model load time, training duration, and P50/P95 inference;
- checkpoint hash, calibration artifact hash, selected threshold, validation
  report hash, held-out report hash, and Stage A regression report hash;
- bounded failure categories only. Never record prompts, raw model output,
  OAuth material, tokens, Spotify IDs/URIs, API keys, private paths, or
  sensitive user text.

External weights remain under `D:\ai\ai`; the source repository stores only
sanitized manifests/reports and no credentials or raw benchmark traces.

## 11. Security and promotion boundary

The security contract remains the authority: Local AI is an untrusted semantic
parser, never an execution engine; only `spotify_play_track` and `unknown`
are in scope; high-risk/system text is gated before AI; output must pass
closed-schema validation, deterministic grounding, and policy checks; and
timeouts, malformed output, backend errors, and model unavailability fail
closed ([Local AI security](SECURITY.md#L101-L118)).

The future typed adapter may produce only:

```text
intent ∈ {spotify_play_track, unknown}
track / artist / album = bounded source-text spans or null
probabilities / diagnostics = bounded non-secret values
```

It may not produce or receive a Spotify URI/track ID, catalog object,
clarification token, path, shell text, URL, process ID, OAuth value, or API
credential. Unknown always carries null slots. No adapter output is a
`ValidatedAction`; the existing deterministic grounder and policy gate remain
downstream. Playback controls, app actions, volume, shutdown, force-close,
firewall, and system administration remain deterministic-only
([architecture boundary](ARCHITECTURE.md#L158-L216)).

This plan changes no production configuration and cannot set
`LOCAL_AI_FALLBACK_APPROVED=true`. A future successful report is research
evidence only and must be followed by an independent promotion review before
any separate production task is even considered.

## 12. Source references

- [Benchmark protocol](LOCAL_AI_DECISION_MODEL_BENCHMARK_PLAN.md#L69-L191)
- [Stage A final gate and thresholds](LOCAL_AI_DECISION_MODEL_BENCHMARK_STAGE_A_SUMMARY_2026-09-21.md#L136-L210)
- [laya sequence/model](../runtime/ai_poc/upstream-batch-2b/laya/laya/common.py#L49-L126)
- [laya loader and typed inference](../runtime/ai_poc/upstream-batch-2b/laya/laya/agent.py#L49-L345)
- [decider model/readout](../runtime/ai_poc/upstream-batch-2b/decider/decider/model.py#L7-L28)
- [decider typed inference](../runtime/ai_poc/upstream-batch-2b/decider/decider/infer.py#L55-L176)
- [decider training path](../runtime/ai_poc/upstream-batch-2b/decider/decider/train.py#L42-L138)
- [pinned benchmark adapters](../scripts/local_ai_stage_a_adapters.py#L286-L314)
- [benchmark result schema](../scripts/local_ai_benchmark_harness.py#L191-L253)
- [security invariants](SECURITY.md#L101-L118)
