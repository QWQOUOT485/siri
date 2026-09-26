# Stage B Laya small adaptation and untouched validation triage — 2026-09-26

**Result: `LAYA_RX9070XT_SMALL_ADAPTATION_TRIAGE_PASSED`.**

All four predeclared safety triage checks passed. Diagnostic quality remains
poor: supported play recall is 11/300, track exact-span accuracy is 0/300,
and full semantic accuracy is 240/540. This is a Step-5 safety triage result,
not a final Stage B quality pass or production authorization.

## Authorization and repository

- Exact fetched main/base: `6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a`.
- Branch: `codex/stage-b-laya-small-adaptation`.
- Frozen implementation/live commit: `839f977b10aebc01dfdbf4b73be394d7ca4b9ece`.
- Final evidence head and new PR number are recorded in GitHub PR metadata.
- Prior strict load, PR #75 shape smoke, and PR #76 pipeline smoke remain
  reviewed, merged prior evidence. They were not rerun as this task's result.
- One task-authorized live child completed one small adaptation, one final
  checkpoint, fresh trainable-object reload, and one untouched validation pass.
- No second run, retry, calibration, threshold tuning, checkpoint selection,
  full adaptation, held-out evaluation, Stage A regression, LoRA, distillation,
  RL, Decider qualification, or production action occurred.

The [runner](../../../../scripts/local_ai_stage_b_laya_small_adaptation.py)
reuses the reviewed renderer, collator, identity/device/finite checks and
parameter-group helpers. The new [CPU tests](../../../../tests/unit/test_local_ai_stage_b_laya_small_adaptation.py)
exercise toy mechanics separately. The [complete sanitized JSON](LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json)
is the durable source for all IDs, permutations, per-step values, hashes,
validation counts and decoded offset-only proposals. It contains no utterance
text, provider identity, secret, token or private local user path.

## Frozen data boundary and selection

Only frozen `final_v1/train.jsonl` supplied training rows. Its exact byte SHA
is `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2`,
with 1,800 rows in 300 complete six-row source groups.
Only frozen `final_v1/validation.jsonl` supplied validation rows: 600 rows,
100 groups, byte SHA
`297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`.

The existing seal verifier performed schema, exact split/group assignment,
source provenance, Stage A leakage and frozen exact near-duplicate checks.
Its held-out/sealed, Stage A fixture and v6 review-artifact reads were
**integrity-only**, never model inputs. Frozen artifacts were not modified.

The selector constructs a six-row signature in canonical file order. Each
row retains only ai_scope, nested expected.intent, language_tag,
negative_reason and nested optional_slot_status.artist/album; missing values
are JSON null. It serializes sorted-key compact ASCII-escaped UTF-8 JSON.
For each signature, floor(n/3) gives a total of **89 base groups**. The
remaining **11 seats** go by descending n modulo 3, then ascending signature
bytes. It takes the first quota groups per signature and merges selected
groups back into canonical train-group order. It does not inspect model
output, loss or utterance meaning. All 100 groups match the supplied oracle.

### Exact 100 selected groups

```text
source-group-0026
source-group-0027
source-group-0028
source-group-0029
source-group-0030
source-group-0031
source-group-0032
source-group-0033
source-group-0057
source-group-0058
source-group-0059
source-group-0060
source-group-0061
source-group-0073
source-group-0074
source-group-0075
source-group-0076
source-group-0077
source-group-0078
source-group-0079
source-group-0080
source-group-0107
source-group-0108
source-group-0109
source-group-0110
source-group-0111
source-group-0121
source-group-0122
source-group-0123
source-group-0130
source-group-0131
source-group-0135
source-group-0136
source-group-0140
source-group-0141
source-group-0145
source-group-0146
source-group-0147
source-group-0148
source-group-0149
source-group-0150
source-group-0151
source-group-0152
source-group-0153
source-group-0154
source-group-0155
source-group-0156
source-group-0181
source-group-0182
source-group-0183
source-group-0184
source-group-0331
source-group-0332
source-group-0333
source-group-0334
source-group-0335
source-group-0336
source-group-0337
source-group-0338
source-group-0339
source-group-0340
source-group-0341
source-group-0342
source-group-0343
source-group-0344
source-group-0345
source-group-0346
source-group-0381
source-group-0382
source-group-0383
source-group-0384
source-group-0407
source-group-0408
source-group-0409
source-group-0410
source-group-0411
source-group-0412
source-group-0413
source-group-0414
source-group-0415
source-group-0416
source-group-0417
source-group-0418
source-group-0516
source-group-0517
source-group-0522
source-group-0525
source-group-0527
source-group-0529
source-group-0533
source-group-0534
source-group-0535
source-group-0536
source-group-0544
source-group-0566
source-group-0567
source-group-0573
source-group-0577
source-group-0578
source-group-0579
```

Selection manifest SHA: `fd69f3280becca6e12225d36960b016bd8e6e4bf9e3962e393c4bef0e0ff2c1d`.

All six rows of each selected group are retained: exactly 600 source rows,
498 supported training rows and 102 rows blocked before rendering
(66 deterministic-only, 36 safety-only).
The exact 498 eligible and 102 blocked case-ID arrays are in JSON at
`selection.eligible_case_ids` and `selection.blocked_case_ids`; the 600 ordered
source IDs are at `selection.case_ids`.

| Selected aggregate | Count |
| --- | --- |
| groups | 100 |
| intent | {"spotify_play_track": 306, "unknown": 294} |
| language | {"mixed": 216, "zh-Hans": 90, "zh-Hant": 294} |
| play_slots | {"absent/absent": 42, "absent/present": 60, "present/absent": 66, "present/present": 138} |
| rows | 600 |
| scope | {"deterministic_only": 66, "safety_only": 36, "supported": 498} |
| supported_unknown | {"artist_only": 96, "missing_track": 96} |

### Order, epochs and renderer

Each epoch independently shuffles the canonical 498 eligible IDs using
`random.Random(1729 + epoch_index)`, with indexes 0, 1, 2. There are 62 batches
of eight and one final batch of two per epoch: exactly 63 steps each,
**189 total**, every eligible row once per epoch, no drop-last or fourth epoch.
All batch memberships are retained in `steps[].case_ids`.

| Epoch index | Permutation SHA |
| --- | --- |
| 0 | b44dc6d3b17bcc1111682ec12fc9d0fd7117f0d603c792bb5a4e9846520153ce |
| 1 | d7319a20f58f3eb61f64541a4a2971771b0ad7bd9ef57b24ec5b37e2ff69eb7e |
| 2 | f0e81e0981617e35c986974182adb548dfc6d35a07e4465a0bf74bcbf592e127 |

Before adaptation, all 498 training and 540 supported validation renderings
matched the pinned upstream build_sequence input IDs and marker positions.
The independent offline real-tokenizer check found maximum lengths 47/40.
User-state masks exclude prompt/options/special/padding; target offsets are
in the original utterance. Play labels require TRACK; supported unknowns have
O-only BIO/all-null slots. The intent mapping remains spotify_play_track to
bounded play, unknown to unknown. No blocked row reached rendering/model.

## Model, training configuration and finite checks

Seed 1729 sets Python and Torch CPU/CUDA random states. Project-owned heads
are Linear(768,7) for BIO and Linear(768,1) for validity. NumPy random sampling
is not used. The model uses training mode, while encoder and act_head are
explicitly frozen and in eval mode. Project heads train; the native nonencoder
Transformer head uses its training/dropout behavior. Seed alone does not
establish bitwise GPU reproducibility. This task does not test stochastic
mid-run resume.

Only type_emb, nonencoder head, scorer, project span_head and validity_head
train. Encoder and act_head receive no gradients and retain byte hashes.
No act_head loss or extra model head is introduced.

- AdamW: constant LR 1e-4 for all 189 steps, weight decay 0, betas
  (0.9,0.999), eps 1e-8, foreach=false; no scheduler.
- BF16 autocast for Laya forward; project heads/loss and epoch loss
  accumulation are float32, no GradScaler.
- Loss: intent CE + user-state-masked BIO CE + validity BCE, unit weights.
- Backward is followed by finite/device checks, frozen-gradient absence,
  clip_grad_norm_ max_norm=1.0, then optimizer step and parameter/state
  finite/device checks. Scalar AdamW step counters may reside on CPU;
  parameter-shaped optimizer state remains on the selected device.
- Every step passed. Maximum unclipped aggregate norm: 36.136926713009686.
  Maximum measured postclip norm: 1.0000001411800767, within
  the declared 1.00001 numerical tolerance. No NaN/Inf, OOM, wrong gradient,
  CPU fallback, extra step or validation feedback occurred.

| Epoch | Intent CE | Span CE | Validity BCE | Total | Seconds |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.8478220105171204 | 1.8783668279647827 | 0.7013053894042969 | 3.4274942874908447 | 10.691374100000758 |
| 1 | 0.6870280504226685 | 1.009154200553894 | 0.6681823134422302 | 2.3643646240234375 | 4.151692899999034 |
| 2 | 0.6537912487983704 | 0.8256992101669312 | 0.667643129825592 | 2.1471331119537354 | 4.069006100000479 |

Epoch losses are example-weighted averages of batch scalar losses, accumulated
in float32. The span batch scalar itself averages user-state tokens; this
report does not relabel that as a corpus-wide token-weighted loss.

MiniMind served only as the local
[training-engineering reference](../../training/LOCAL_AI_MINIMIND_TRAINING_REFERENCE.md)
for seeding, mixed precision, optimizer structure, clipping, checkpoint
serialization and structured logs. No runtime dependency, causal-LM SFT,
autoregressive JSON, LoRA, distillation or RL was adopted.

### Parameter hashes

| Group | Before SHA | After SHA |
| --- | --- | --- |
| act_head | `7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d` | `7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d` |
| encoder | `e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812` | `e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812` |
| span | `69d2c733f2cb88780070c06993fa626d9e516e438b4bdc52e49b2f7f95de89a4` | `864e146331b596e2d555ecc34cd4e968a0f3ee233721f5ebd3e18f72c23afd20` |
| typed | `2feb35a346c8cf6aa13151243f55e47ef65934cc2c8eb7062030e04b14b9fbf4` | `a5c3f736e7c943ab39039eb240cf635df22521d74fe159a01f899d149816660b` |
| validity | `f268d1c3a93dde50a5b1a67610ffa0dce8d8bcd1fffa1028012b36348ba85f05` | `9e339959e40062df3fda976970361f7fc53793ee5b616b6b01eea06b35bdb2aa` |

Encoder/act_head hashes are unchanged. Each typed/span/validity group changed.
Hashes include names, shapes, dtypes and raw contiguous parameter bytes.
The exact parameter names are retained in JSON.

## Final research checkpoint and fresh reload

The entire exact task directory was absent before the child started. No
unknown pre-existing directory was removed. After exactly step 189, the run
created one checkpoint at sanitized path:

`<external-adaptation-root>/6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a/final.pt`

- SHA-256: `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d`.
- Size: 177394599 bytes.
- Schema: `laya-small-adaptation-final-v1`.
- Fields: schema, typed trainable state, span state, validity state,
  optimizer state, completed_steps=189 and binding containing config/seed,
  complete selection manifest/hash and pinned identities.
- No encoder or act_head weights were serialized.

All trainable Laya decision objects and project heads were destroyed and
recreated. Canonical frozen encoder/act_head references remained bound to
the pinned load. The serialized final checkpoint was loaded into new
trainable modules; exact group hashes matched post-training values. Every
module was switched to eval, frozen gradients/identities and selected-device
placement were rechecked, and only then validation began. Training never
resumed. Validation did not change any parameter hash.

The checkpoint and task directory remain with verified Windows **ReadOnly
attributes** for independent research review. These attributes are recorded,
not claimed to be an immutable security ACL. The checkpoint is not an
approved production artifact or initialization for another training run,
held-out/Stage A evaluation or Local AI fallback. It must not be reused
without separate review/authorization. No checkpoint bytes entered Git.

## Exactly one untouched validation pass

The full frozen 600-row validation split was accounted for once:
300 supported play + 240 supported semantic unknown reached the model;
30 deterministic-only + 30 safety-only rows were blocked before rendering.
The 540 supported rows were evaluated once, in canonical order, in batches
of 16 (last batch 12). Exact IDs and gate composition are in JSON. No
validation between epochs, second validation pass, feedback, threshold
change, data edit or alternative checkpoint selection occurred.

The frozen decoder uses bounded typed argmax, sigmoid validity >=0.5 and
BIO argmax only inside user-state tokens. Play requires one valid contiguous
grounded TRACK span with nonempty raw character bounds. Orphan/split/multiple
TRACK labels, nonuser crossings, invalid/empty/overlapping offset mappings
fail closed. Duplicate or malformed optional spans become null. Final unknown
always clears every slot. Output carries only bounded intents and raw offset
pairs; it never creates IDs, URLs, paths, tokens or executable actions.

### Predeclared safety triage

| Gate | Observed | Required |
| --- | --- | --- |
| Supported semantic-unknown recall | 240/240 | 240/240 |
| Conditional unknown false acceptance | 0/240 | 0/240 |
| Deterministic/safety blocked before model | 60/60 | 60/60, zero leakage |
| Predicted play without valid grounded track | 0 | 0 |

All four pass. The track-validity check establishes grounding/structure,
not that the span matches the expected song title. There were 11 final play
predictions, all on expected-play rows, but none had the exact expected track
span. Safety triage must not be confused with useful semantic extraction.

### Diagnostics — no tuning

| Metric | Numerator/denominator |
| --- | --- |
| Supported play recall | 11/300 |
| Full semantic accuracy | 240/540 |
| track exact_span | 0/300 |
| track presence_recall | 11/300 |
| artist correct_null | 174/174 |
| artist exact_span | 0/126 |
| artist presence_recall | 0/126 |
| album correct_null | 96/96 |
| album exact_span | 0/204 |
| album presence_recall | 0/204 |

| Slice | Play recall | Unknown recall | Full semantic | Track exact |
| --- | --- | --- | --- | --- |
| en | 1/96 | 84/84 | 84/180 | 0/96 |
| mixed | 10/204 | 156/156 | 156/360 | 0/204 |

Uncalibrated confidence summaries (float32 output probabilities; Python
summary arithmetic, no probability fitting):

| Expected class | Probability | Min | Mean | Max |
| --- | --- | --- | --- | --- |
| spotify_play_track | typed_play_probability | 0.26817411184310913 | 0.5721718226869901 | 0.786786675453186 |
| spotify_play_track | validity_probability | 0.6160678863525391 | 0.6179475325345993 | 0.6199832558631897 |
| unknown | typed_play_probability | 0.2939108908176422 | 0.5441796181102594 | 0.8007699251174927 |
| unknown | validity_probability | 0.616004467010498 | 0.6182121515274048 | 0.6207619309425354 |

Exact count metrics use integer accumulators and explicit denominators.
Absent optional slices with a zero denominator are recorded as null rates,
not scored as successes. Full semantic accuracy is over the 540 supported
rows; blocked rows do not inflate model metrics. No final >=95% Stage B,
calibration, capacity, latency or production claim is made.

## Process, device and immutable identities

The qualified Python used `-B -X utf8`, UTF-8 mode=1, offline HF/Transformers
flags, scrubbed PYTHONPATH and raw-byte parent/child result transport. A
child audit hook rejected network connect and DNS. Before optimizer creation,
the same child rechecked exact packages, source/cleanliness, model artifacts,
train/validation/protocol/seal identities and GPU inventory.

Enumeration found the iGPU at cuda:0 and uniquely selected AMD Radeon
RX 9070 XT / gfx1201 at **cuda:1**. Strict load and all-parameter/buffer
residency passed, cpu_fallback=false. Initial parameter count 321,908,995
plus three persistent temperature elements equals 321,908,998 state elements.
The residency count is taken before freezing, not the optimizer group count.

All source/model/venv/train/validation/held-out/manifests/seal identities were
identical before/after. Held-out identity was read only for integrity.

| Identity | Before = after |
| --- | --- |
| model_aggregate_sha256 | eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf |
| model_revision | 052592a15d198d9ad47da779604259b10b47b7aa |
| primary_weight_sha256 | 9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204 |
| source_clean | True |
| source_revision | 42626c348753fbb17572a813127df2278a1ec527 |
| venv_inventory_sha256 | 3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337 |
| authoritative_schema_groups_leakage_near_duplicates | passed |
| canonical_corpus_sha256 | a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13 |
| corpus_manifest_sha256 | 297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c |
| provenance_manifest_sha256 | d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d |
| seal_manifest_sha256 | 5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef |
| selection_manifest_sha256 | 973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a |
| split_assignment_sha256 | 84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37 |
| train_rows | 1800 |
| train_sha256 | 54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2 |
| validation_rows | 600 |
| validation_sha256 | 297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a |
| held_out.jsonl | de392544b7a294cdf850ce2706509684b05c4ca346402c7ec60cf9031f979946 |
| train.jsonl | 54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2 |
| validation.jsonl | 297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a |

### Operational VRAM and timing

These are observations, not latency qualification. Epoch peaks reset at each
epoch; validation peak resets before evaluation.

| Phase | Allocated bytes | Reserved bytes | Peak allocated | Peak reserved |
| --- | --- | --- | --- | --- |
| after_load | 1307833856 | 1333788672 | 1307833856 | 1333788672 |
| after_reload | 1434081280 | 1648361472 | 1575546368 | 1648361472 |
| baseline | 0 | 0 | 0 | 0 |
| final | 1434081280 | 1648361472 | 1478006272 | 1648361472 |
| first_train_batch | 1554598912 | 1646264320 | 1573485568 | 1646264320 |
| post_training | 1553218560 | 1648361472 | 1575546368 | 1648361472 |
| validation_peak | 1434081280 | 1648361472 | 1478006272 | 1648361472 |
| epoch_0 | 1553218560 | 1648361472 | 1575546368 | 1648361472 |
| epoch_1 | 1553218560 | 1648361472 | 1575546368 | 1648361472 |
| epoch_2 | 1553218560 | 1648361472 | 1575546368 | 1648361472 |

| Phase | Seconds |
| --- | --- |
| load_seconds | 12.574063699999897 |
| train_wall_seconds | 18.913234999999986 |
| validation_wall_seconds | 0.788761699999668 |

## Canonical evidence, tests and remaining gates

Canonical result SHA: `4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8`.
Canonicalization uses sorted keys, compact separators, ASCII escaping,
UTF-8 and nonfinite rejection, excluding only canonical_result_sha256.
The durable JSON was copied from raw Python process bytes and its canonical
hash revalidated; timing values do not imply repeatable GPU timing.

The required repository suites completed as follows. Only the qualified
Python executable was used. For CPU pytest only,
the existing project venv site-packages directory is appended read-only after
qualified package paths. No install or venv mutation occurred, and that path
was not propagated to the live child. Tiny CPU optimizer tests used invented
tensors and no Laya weights or corpus inputs.

- New small-adaptation suite: **33 passed** (including the final all-eligible
  pinned-renderer test).
- Combined new/prior pipeline, shape, load, hardware, corpus/seal suite:
  **140 passed** before that final renderer test was added; the added test
  then passed in the complete 33-test new suite.
- Full unit suite: **703 passed**, two existing dependency deprecation warnings,
  280.47 seconds. This includes all final tests.
- Windows integration: **5 passed**, 8.32 seconds.
- Compileall app/scripts/tests and git diff --check passed.
- **28 Markdown relative links** resolved; result/subset canonical hashes passed.
- External checkpoint SHA/size and file/directory ReadOnly attributes verified.
- Zero diff under frozen artifacts, fixtures and app; all three primary-worktree
  status/Shortcut hashes match their starting values.
- No additional quality benchmark or model invocation occurred.

PROJECT_STATUS and Issue #68 record the exact safety triage PASS and poor
diagnostic quality. Issue #68 stays OPEN; the new PR stays OPEN/UNMERGED for
independent review. Full head-only adaptation remains separately unauthorized.
Held-out Stage B, untouched Stage A, calibration, final quality/latency,
Decider and production promotion remain separate gates. No automatic next
experiment is authorized by this report.

No app, frozen corpus, canonical tokenizer/config/model or primary Shortcut
file was modified. The one bounded authorization changes none of these
persistent authority flags:

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
