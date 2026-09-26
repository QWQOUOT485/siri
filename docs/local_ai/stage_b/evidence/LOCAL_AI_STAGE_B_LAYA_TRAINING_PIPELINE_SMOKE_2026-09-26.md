# Stage B Laya training-pipeline smoke — 2026-09-26

**Current result: `LAYA_RX9070XT_TRAINING_PIPELINE_SMOKE_PASSED`.**

The corrected authorized smoke completed exactly four optimizer steps on
AMD Radeon RX 9070 XT / gfx1201. Encoder and act_head remained frozen and
byte-identical. Typed decision, project span, and project validity parameters
changed. Step-2 checkpoint save/recreation/reload/resume passed, and the
temporary checkpoint directory was removed and verified absent. This is
pipeline/connectivity evidence only, with no quality conclusion.

## 1. Initial task-specification blocker — historical

Initial PR #76 head `df9b460e1469fb748f6429a257810d13eef0804b` correctly
reported `STOP_LAYA_TRAINING_PIPELINE_DATA_BOUNDARY` /
`fixed_strata_incomplete_or_duplicate`. Its task-owned selector requested
four supported unknown rows for each of `missing_track`, `artist_only`,
`unresolved_reference`, and `ambiguous_version`.

The exact frozen 1,800-row train split contains 900 supported play rows,
600 supported unknown rows (300 `missing_track`, 300 `artist_only`),
180 deterministic-only and 120 safety-only rows. It contains **zero**
supported `unresolved_reference` and **zero** supported
`ambiguous_version` rows. The initial selector therefore could not form
the requested subset. Full corpus/seal checks passed; no corpus defect was
established and no labels were changed.

That initial attempt had **zero live Laya invocations, model loads, Laya
optimizer steps, and checkpoints**. Its canonical read-only report SHA was
`8c489efb27475c90aec4fce9f1d5ad18cf1e5557505bf4ab4ee5968792357eda`.
The detailed original report is preserved in that Git commit. A discarded
draft's CPU unit test exercised four AdamW steps on a tiny toy module with
invented tensors; it used no Laya weights or corpus examples.

The user's correction replaced only the impossible task-owned subset with
the exact language/group quotas and oracle below. It explicitly authorized
the **first actual live Laya training-pipeline invocation**. This was not a
retry after a model failure, an Astra escalation, or a corpus modification.

## 2. Corrected authorized pipeline-smoke result

### Repository and authorization

- Repository: `QWQOUOT485/siri`; PR #76 remains OPEN and UNMERGED.
- Fetched exact main/base: `57a07b11f8ae322d39be9379f7423b924880aa0b`.
- Starting reviewed PR head: `df9b460e1469fb748f6429a257810d13eef0804b`.
- Branch: `codex/stage-b-laya-training-pipeline-smoke`.
- Tested/live implementation commit: `61765c1aa92df279719a1d6c751e1b514f1df4f3`.
- Final evidence head is recorded in PR metadata after committing this report.
- Clean isolated worktree; primary status and Shortcut edits preserved.
- One live invocation, one Laya load, four forwards/backwards and four
  optimizer steps; no extra quality forward or live retry.

The [project-owned runner](../../../../scripts/local_ai_stage_b_laya_training_pipeline_smoke.py)
reuses the reviewed PR #75 renderer, mask/BIO labeling, tensor collator,
finite checks, exact device selector, load/residency and identity helpers.
The [tests](../../../../tests/unit/test_local_ai_stage_b_laya_training_pipeline_smoke.py)
use synthetic CPU mechanics separately from the live Laya result.
PR #75's merged head-only shape smoke remains valid prior evidence.

### Frozen data gate and exact selector

Only `artifacts/local_ai/stage_b/final_v1/train.jsonl` supplies selectable
or model-training rows. Before selection, the runner verifies byte SHA
`54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2`,
exactly 1,800 rows, and the authoritative corpus/seal checks.

The existing `verify_seal()` performs closed schema validation, exact split
identity/counts, complete source-group assignment, reviewed v6 provenance,
Stage A leakage checks, the frozen exact near-duplicate policy, and the
600-row/100-group held-out seal. Its internal validation/held-out/sealed,
Stage A, and v6 reads are **integrity-only**. None supplies model inputs.

Selection algorithm `canonical-first-unique-group-language-quota-v2`
scans canonical train file order. It takes the first row satisfying a
remaining exact stratum/language quota only if its source_group_id has not
already been selected anywhere in the subset. It then requires all quotas,
40 distinct case IDs, 40 unique groups, the exact ordered 40-ID oracle,
and the 32 eligible / eight blocked partition.

The selector reads only typed ai_scope, expected.intent, optional_slot_status,
negative_reason, language_tag, source_group_id and case_id. It does not
interpret utterance text or select from loss/model output.

| Stratum | zh-Hant | zh-Hans | mixed | Total |
| --- | ---: | ---: | ---: | ---: |
| deterministic_only | 2 | 1 | 1 | 4 |
| play_artist_absent_album_absent | 3 | 1 | 0 | 4 |
| play_artist_absent_album_present | 3 | 1 | 0 | 4 |
| play_artist_present_album_absent | 2 | 1 | 1 | 4 |
| play_artist_present_album_present | 2 | 1 | 1 | 4 |
| safety_only | 2 | 1 | 1 | 4 |
| unknown_artist_only | 4 | 2 | 2 | 8 |
| unknown_missing_track | 4 | 2 | 2 | 8 |
| **Total** | **22** | **10** | **8** | **40** |

Play rows all have supported spotify_play_track labels and valid required
track spans. The two supported-unknown strata retain all-null slots.
Observed totals: **16 play, 16 supported unknown, four deterministic-only,
four safety-only; 40 unique groups; 32 model-eligible; eight blocked before
rendering**. No row was shuffled or used twice.

Subset manifest canonical SHA:
`790837099986a8b9a4976f83e90f97b423f7d1ac4227976a33b8de8c687c82eb`.

The exact 40 case IDs and matching source-group IDs are stored, in canonical
order, in the sanitized [structured result](LAYA_TRAINING_PIPELINE_SMOKE_RESULT_2026-09-26.json).
These are the four fixed eligible batches:

- Step 1: `candidate-00151`, `candidate-00157`, `candidate-00337`, `candidate-00343`, `candidate-00433`, `candidate-00439`, `candidate-00445`, `candidate-00637`.
- Step 2: `candidate-00643`, `candidate-00649`, `candidate-00721`, `candidate-00775`, `candidate-00805`, `candidate-00835`, `candidate-00865`, `candidate-01081`.
- Step 3: `candidate-01981`, `candidate-01987`, `candidate-01993`, `candidate-01999`, `candidate-02005`, `candidate-02011`, `candidate-02017`, `candidate-02023`.
- Step 4: `candidate-02281`, `candidate-02287`, `candidate-02293`, `candidate-02299`, `candidate-02437`, `candidate-02443`, `candidate-02449`, `candidate-02455`.

Blocked before the renderer:
`candidate-03091`, `candidate-03097`, `candidate-03169`, `candidate-03193`, `candidate-03391`, `candidate-03397`, `candidate-03433`, `candidate-03457`.

### Renderer, labels, and device

All 32 eligible rows matched the pinned upstream build_sequence input IDs
and marker positions. The independent pre-live real-tokenizer audit also
matched all 32 (maximum sequence length 36). No required state was truncated.
User-state masks excluded prompt/options/special/padding positions. Play
labels included TRACK BIO; unknown labels were O-only. The deterministic
intent mapping is spotify_play_track → play, unknown → unknown; validity
targets are 1 and 0 respectively.

The same live child used the qualified Python
`D:/ai/venvs/siri-stage-b-rocm10-gfx1201/Scripts/python.exe`, Python 3.14.7,
with `-B -X utf8`, `utf8_mode=1`, HF_HUB_OFFLINE=1 and
TRANSFORMERS_OFFLINE=1. The parent removed PYTHONPATH and used raw-byte
stdout/stderr transport. A child audit hook prohibited network connect and
DNS operations.

Same-child package checks passed: pip 26.2.1, torch 2.13.0+rocm10.0.0,
HIP 7.15.26333, transformers 4.57.6, safetensors 0.7.0,
huggingface-hub 0.36.2, numpy 2.3.5.

Enumeration found AMD Radeon(TM) Graphics / gfx1036 at cuda:0 and the
unique AMD Radeon RX 9070 XT / gfx1201 at explicit **cuda:1**. The iGPU was
not selected. Strict Laya load succeeded in 12.070722 s.
Every model parameter and buffer resided on cuda:1, cpu_fallback=false:
321,908,995 parameters + three persistent temperature buffer elements =
321,908,998 state elements. This residency readback occurred before the
freeze policy and optimizer creation; its initial trainable count is not
the allowed optimizer parameter count.

### Loss, freeze policy, and optimizer wiring

- Entire encoder and upstream act_head: requires_grad=false, gradients
  absent after each backward and before/after clipping.
- Trainable: upstream type_emb, optional non-encoder head, scorer;
  project span_head (768 → 7) and validity_head (768 → 1).
- Head initialization seed: **1729**, with exact initial hashes below.
- Module eval mode disables dropout while preserving allowed-head autograd.
  No encoder layer was unfrozen, and no act-head loss was invented.
- BF16 CUDA autocast for the qualified Laya forward; project head losses,
  accumulation and logs in float32. No GradScaler.
- Total loss = intent CE + user-state-masked BIO CE + validity BCE;
  each weight is exactly 1.
- AdamW: LR 1e-4, weight_decay=0, betas=(0.9, 0.999), eps=1e-8;
  foreach=false explicitly uses the ordinary implementation.
- LambdaLR factors for step entry: 1, .75, .50, .25. Order is
  optimizer.step then scheduler.step; after the fourth step LR becomes 0.
- clip_grad_norm_ maximum norm=1.0, after backward and before optimizer.
  All outputs, losses, gradients, updated parameters and optimizer state
  passed finite/device checks. AdamW scalar step counters may remain CPU;
  parameter-shaped optimizer tensors remained on cuda:1.

MiniMind was used only as the local
[training-engineering reference](../../training/LOCAL_AI_MINIMIND_TRAINING_REFERENCE.md)
for these mechanics. No MiniMind runtime, causal-LM SFT, autoregressive
JSON, LoRA, distillation, or RL was introduced.

### Four exact step readbacks

Loss values are connectivity evidence, **not model quality**. LR decimals
below preserve the actual float readback; 0.00007500000000000001 is the
declared 1e-4 × 0.75 floating-point value.

| Step | Intent CE | Span CE | Validity BCE | Total | LR before | LR after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.943225383758545 | 3.009040355682373 | 0.21062076091766357 | 5.162886619567871 | 0.0001 | 0.00007500000000000001 |
| 2 | 1.1801034212112427 | 2.818918466567993 | 0.20615056157112122 | 4.205172538757324 | 0.00007500000000000001 | 0.00005 |
| 3 | 2.1505627632141113 | 4.029707908630371 | 1.6911464929580688 | 7.871417045593262 | 0.00005 | 0.000025 |
| 4 | 2.073721408843994 | 3.8908021450042725 | 1.6916996240615845 | 7.656222820281982 | 0.000025 | 0 |

| Step | Unclipped aggregate norm | clip_grad_norm_ returned | Measured post-clip norm | Elapsed seconds |
| --- | ---: | ---: | ---: | ---: |
| 1 | 28.811553649407067 | 28.811553955078125 | 0.9999998841898352 | 7.527861 |
| 2 | 23.608881486488645 | 23.608882904052734 | 0.9999998454574439 | 0.050907 |
| 3 | 61.45769636982578 | 61.45769500732422 | 0.9999999295516689 | 0.05253 |
| 4 | 58.76520570549477 | 58.765201568603516 | 1.0000000253052448 | 0.049627 |

Post-clip norm uses a 1.00001 numerical tolerance around the requested
maximum 1.0; the tiny step-4 rounding excess is recorded without alteration.
There were exactly four optimizer calls and no fifth step.

### Parameter-mutation proof

SHA-256 includes parameter names, shapes, dtypes and raw contiguous bytes.

| Group | Before | After | Result |
| --- | --- | --- | --- |
| act_head | `7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d` | `7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d` | unchanged |
| encoder | `e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812` | `e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812` | unchanged |
| span | `69d2c733f2cb88780070c06993fa626d9e516e438b4bdc52e49b2f7f95de89a4` | `3747f3dee97509bf4086908233ce5635ea0fc070ab4e64042d6d29ad3dc32ffa` | changed |
| typed | `2feb35a346c8cf6aa13151243f55e47ef65934cc2c8eb7062030e04b14b9fbf4` | `aa9d1d75f85daf6ab7318acecf04e5dd972cdc5e1765a123fd84e1831f31653f` | changed |
| validity | `f268d1c3a93dde50a5b1a67610ffa0dce8d8bcd1fffa1028012b36348ba85f05` | `382951fefb2fd89a7ce03a8722b97ea7ba193869408642583de8bb851133bebf` | changed |

Exact parameter-name sets are in the structured result. The changed group
hashes prove that at least one parameter changed in each required trainable
group. They establish connectivity only.

### Step-2 checkpoint save/reload/resume/cleanup

The exact task directory `D:/ai/ai/stage_b_training_pipeline_smoke/pr76/`
was verified absent before the live child; no pre-existing directory was
deleted. After optimizer step 2, the child created it exclusively and wrote
one checkpoint, sanitized path `<external-smoke-root>/pr76/step-2.pt`.

Checkpoint SHA:
`870258d801afa6348985da76a6c3e740b2aa40d5b8d22c4790ce36c3934d3953`.

It contains only allowed trainable Laya state, span/validity states,
optimizer/scheduler state, completed step 2, seed/config, subset SHA and
pinned identities. No frozen encoder or act-head weights were saved.

All trainable model/head and optimizer/scheduler objects were destroyed and
recreated using the pinned upstream model constructor and new project heads.
Frozen encoder, act_head and temperature references were retained unchanged.
After restore, exact group hashes matched step-2 state; optimizer and
scheduler state hashes matched:

- Optimizer: `bbbeb6e6cfdef26cc35561cd13994d90e9fe2af483c54540be6da23911d8955b`.
- Scheduler: `f464689c3b5f2d4054cdcd05eaf1de687a09c466bfc7a64a4c7be03e2990fcc9`.
- Completed step restored: **2**.
- Next LR restored: **0.00005**.
- Steps **3 and 4** then completed from restored state.

The child collected final evidence, verified immutable identities, deleted
the task-owned checkpoint directory, and verified that it no longer existed.
An external post-run existence check also confirmed absence. No binary
checkpoint was committed or left in canonical Laya storage.

### VRAM and immutable identities

All byte counts below refer to the selected RX 9070 XT. Timings are
descriptive smoke readbacks, not latency qualification.

| Phase | Allocated bytes | Reserved bytes | Peak allocated | Peak reserved |
| --- | ---: | ---: | ---: | ---: |
| baseline | 0 | 0 | 0 | 0 |
| after_load | 1307833856 | 1333788672 | 1307833856 | 1333788672 |
| before_step_1 | 1307859456 | 1333788672 | 1307859456 | 1333788672 |
| after_step_1 | 1554375680 | 1644167168 | 1573262336 | 1644167168 |
| after_step_2 | 1555218944 | 1644167168 | 1574105600 | 1644167168 |
| after_reload | 1493188608 | 1665138688 | 1613070336 | 1665138688 |
| after_step_3 | 1554273792 | 1665138688 | 1613070336 | 1665138688 |
| after_step_4 | 1554273792 | 1665138688 | 1613070336 | 1665138688 |
| final | 1493188608 | 1665138688 | 1613070336 | 1665138688 |

These exact identities were verified unchanged before/after in the live child:

| Identity | Before = after |
| --- | --- |
| Pinned source revision, clean | `42626c348753fbb17572a813127df2278a1ec527` |
| Model revision | `052592a15d198d9ad47da779604259b10b47b7aa` |
| Model aggregate | `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` |
| Primary weight | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Qualified venv inventory | `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337` |
| canonical_corpus_sha256 | `a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13` |
| corpus_manifest_sha256 | `297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c` |
| provenance_manifest_sha256 | `d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d` |
| seal_manifest_sha256 | `5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef` |
| selection_manifest_sha256 | `973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a` |
| split_assignment_sha256 | `84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37` |
| train_sha256 | `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2` |

The structured result also records the byte hashes of all three frozen
split files and the distinct canonical split hashes. No source, tokenizer,
model/config, venv, frozen corpus/manifest, or seal mutation occurred.

Canonical sanitized run-summary SHA:
`2f1ff9c362a132310282fd46488dbd45dbdab89dbf246a92956e354ad3ef482e`.

Hashing uses UTF-8 JSON, sorted keys, ASCII escaping, compact separators and
nonfinite JSON rejection, excluding only canonical_run_summary_sha256.
Timing and memory are measured fields; canonical serialization of the same
record is deterministic, not a claim that later hardware runs are bitwise
identical. The [complete structured record](LAYA_TRAINING_PIPELINE_SMOKE_RESULT_2026-09-26.json)
contains no utterance text, private/provider IDs, secrets, or environment dump.

### Repository validation and test environment

Only the qualified Python executable was used for this correction. It has
no pytest installation. For CPU test invocations only, the existing
D:/ai/siri-spec/.venv/Lib/site-packages directory was appended to sys.path
after qualified paths, then pytest ran through runpy. Both environments use
Python 3.14.7; qualified packages retained import precedence. No package was
installed or venv changed. That test-only path was not propagated into the
live child. CPU toy tests are separate from the one four-step Laya smoke.

- New focused selector/pipeline suite: **24 passed**.
- Combined selector/pipeline/shape/load/hardware/corpus/seal suite:
  **108 passed**.
- Full unit suite: **670 passed**, two existing deprecation warnings (273.07 s).
- Windows integration: **5 passed**.
- Compileall and git diff --check: passed; **29 Markdown relative links** resolved.
- Frozen artifacts/fixtures and production app: zero diff. All three protected
  primary status/Shortcut SHA-256 values match their starting identities.
- No quality benchmark was run.

### Current state and remaining gates

PROJECT_STATUS records the corrected PASS; the initial selector blocker is
historical only. Issue #68 remains OPEN and PR #76 remains OPEN/UNMERGED for
independent review. The next gate is the **small adaptation run, still
separately unauthorized**. Validation/held-out quality, Stage A regression,
latency, Decider qualification and production promotion remain separate.

No validation/held-out/Stage A/synthetic-shape row became a Laya optimizer
input. No threshold/hyperparameter tuning, encoder/act-head training,
persistent checkpoint, LoRA, distillation, RL, Spotify/Siri/Windows action,
production app edit, frozen artifact edit, or network model call occurred.
This one bounded task changed no persistent/global authority flag:

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
