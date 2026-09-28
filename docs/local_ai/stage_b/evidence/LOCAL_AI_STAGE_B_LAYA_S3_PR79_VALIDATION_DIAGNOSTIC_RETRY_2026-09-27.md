# Laya PR79 checkpoint / S3 validation diagnostic retry — 2026-09-27

**Current result:** `LAYA_PR79_CHECKPOINT_S3_VALIDATION_DIAGNOSTIC_PASSED`.

**NON_ACCEPTANCE_DIAGNOSTIC_ONLY.** This PASS establishes one trustworthy, safety-preserving diagnostic. It is not model-quality acceptance, model selection, production authorization, or permission for further training or compute.

## Provenance and frozen execution

- Main / PR #87 merge: `144dc020344936c017f13ccf9253902d5af54c44`.
- Branch: `codex/stage-b-laya-s3-pr79-validation-diagnostic-retry`.
- Pre-live frozen commit: `5a6e7c91b92e58546cf4bcfe33e4730daa9d7b2a`.
- Runner SHA-256: `48c081e68255e6bb8aa86886c03b4673567f6f9666497ba9fec10e8df2c1a567`.
- Task-only authorization: `pr79-checkpoint-s3-validation-diagnostic-retry-v1`.
- Independent pre-live review completed before freeze/dispatch; clean checkout, exact main, absent scratch and absent durable result verified. Runner and tests unchanged after the one live invocation.

The [canonical structured result](LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_RETRY_2026-09-27.json) contains all 540 prediction pairs, shared decisions, exact batches, eligibility IDs, transitions, failure IDs, offsets, audit events and immutable identities. Its canonical SHA-256 (excluding its self-hash field) is `babb424a086de8bbf83ff5ab68a91dcea39cb5ae1e1247dc5347a1cd40f6a42b`. PR #79 accepted evidence, PR #86 blocker evidence and all historical source/report files remain unchanged.

## Boundaries, scratch and data

One base load, one checkpoint deserialization, one validation pass, 34 forward batches (33 × 16 + 12), 540 shared decisions, and 540 calls to each decoder. No second-decoder forward, training step, backward, optimizer or scheduler. Model and both project heads were placed in eval mode and frozen before validation; every forward used no_grad and the unchanged historical BF16 path. The initial residency count reflects base-load requires_grad flags before the explicit freeze, not training.

Validation SHA-256: `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`. Exactly 600 rows / 100 groups: 300 supported play, 240 supported unknown and 60 blocked before rendering. All 540 renderings matched pinned upstream IDs/markers. No live train, held-out, sealed held-out or Stage A reads.

Identity-only reads are separate from model passes: the child opened validation 4 times (pre/post schema and byte identity), and the checkpoint 3 times (pre/post SHA plus the sole torch.load). These are not repeated inference or checkpoint restores. The standalone no-compute preflight separately read validation twice and hashed the checkpoint once, with zero loads/deserializations/forward passes.

The dedicated external scratch namespace was `<diagnostic-root>/s3-pr79-v1`, absent before creation. TMP/TEMP/TMPDIR used tmp; TorchInductor used torchinductor; Triton used triton; HF_HOME/hub/transformers used hf descendants; XDG used xdg. All child writes used the unchanged PR #87 scratch policy with only exact lexical-and-resolved validation/checkpoint read exceptions. Denials latch before base load, checkpoint restore, each forward and final exit. `-B -X utf8`, offline flags, scrubbed PYTHONPATH, raw-byte transport, and GIT_OPTIONAL_LOCKS=0 were enforced.

Audit: 21 allowed scratch filesystem events, including 2 open-writes; 0 protected denials, 0 outside denials, 0 network attempts. Event counts: open 2, mkdir 13, link 1, remove 3, rmdir 1, utime 1. The link has two sanitized path-detail entries for one event. Dependency temporary probe creation/write/link/removal occurred during import; repeated TorchInductor directory probes occurred at load. Final scratch file inventory was empty; parent removed the entire task scratch directory and verified absence. No canonical artifact was written.

## Checkpoint, runtime and immutable identities

Checkpoint: `<external-adaptation-root>/6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a/final.pt`; 177,394,599 bytes; SHA-256 `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d`; read-only, exact path, no reparse/symlink/junction in any ancestor before and after. Loaded once on CPU with weights_only=True. Exact schema/key set/config/seed/selection/identity binding and completed_steps=189 verified. Only typed/span/validity states restored; optimizer payload ignored, no frozen encoder checkpoint weights.

Selected the enumerated unique `cuda:1 / AMD Radeon RX 9070 XT / gfx1201`; cuda:0 gfx1036 iGPU was not selected. Strict base load passed with all 321,908,995 parameters and 3 persistent buffer elements resident on cuda:1, cpu_fallback=false. All restored parameters were on the selected device and requires_grad=false before validation.

| Group | Restored and post-validation SHA-256 |
| --- | --- |
| act_head | 7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d |
| encoder | e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812 |
| span | 864e146331b596e2d555ecc34cd4e968a0f3ee233721f5ebd3e18f72c23afd20 |
| typed | a5c3f736e7c943ab39039eb240cf635df22521d74fe159a01f899d149816660b |
| validity | 9e339959e40062df3fda976970361f7fc53793ee5b616b6b01eea06b35bdb2aa |

| Identity | Exact value; unchanged before/after |
| --- | --- |
| Source revision / clean | 42626c348753fbb17572a813127df2278a1ec527 / true |
| Model revision | 052592a15d198d9ad47da779604259b10b47b7aa |
| Model aggregate | eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf |
| Primary weight | 9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204 |
| Venv inventory | 3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337 |
| Validation | 297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a |

Qualified Python 3.14.7; PyTorch 2.13.0+rocm10.0.0 / HIP 7.15.26333; transformers 4.57.6, safetensors 0.7.0, huggingface-hub 0.36.2, numpy 2.3.5, pip 26.2.1. Full model aggregate was recomputed by the model identity helper; the separate tokenizer-only identity subrecord accurately says it did not itself open weights.

| Historical source (scripts/) | SHA-256, pre = post |
| --- | --- |
| local_ai_stage_b_laya_adapter.py | cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e |
| local_ai_stage_b_laya_base_load_root_cause.py | 5e82645ec396509155fcb85d9d24989729be84ce81b08e550e32e5a3098f163e |
| local_ai_stage_b_laya_forward_backward_smoke.py | 80ac4a2ba4587d44e830f45bce31215517e5e3b1387167ca6725964f0a3fdd4e |
| local_ai_stage_b_laya_model_load_preflight.py | 10770d932e3c76b501e44ad77225df962d09ad86af97428649fbc9c55169acd1 |
| local_ai_stage_b_laya_s3_pr79_validation_diagnostic.py | 4b259bd9629628aeb3d25ad231521a745cfec81ac0ea6ce6786386259ef94b4f |
| local_ai_stage_b_laya_s3_research.py | b01a254db9bfb1d84023c0f9d88ff7d49ccb789ff7888961ea7e000dfa2d4388 |
| local_ai_stage_b_laya_small_adaptation.py | 85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e |
| local_ai_stage_b_laya_span_decoder.py | f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845 |
| local_ai_stage_b_laya_span_representability_audit.py | 6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087 |
| local_ai_stage_b_laya_span_seam_design.py | 7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72 |
| local_ai_stage_b_laya_span_seam_implementation_verify.py | 35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2 |
| local_ai_stage_b_laya_training_pipeline_smoke.py | 95c6d818e5b6a0db273bb4f5a1e25486f0cfa152fa7000002e7d82c3f64240e8 |

| Reviewed canonical evidence | Canonical SHA-256 |
| --- | --- |
| LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_2026-09-27.json | 962b0f0b720fd87cb21b7a22cadc228150733327e2dfcc318628de28194f5535 |
| LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json | ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd |
| LAYA_S3_RESEARCH_PATH_PREFLIGHT_2026-09-27.json | 38bdead38e5dea83cf45e522279e7280fdfa0aeb08d8d6e12984cff1d7591d87 |
| LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json | 4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8 |
| LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json | 08e8173175f5a879b7677cde2fdaedbc844ae5e4dc790b1d81bb174c46d4bcbb |

All tokenizer/config file hashes, 12 historical script hashes, 10 historical Markdown reports and five canonical result byte/canonical hashes are equal before/after in JSON. Frozen artifacts and app/ have zero diff; primary worktree edits remain untouched.

| Phase | Seconds |
| --- | --- |
| base_model_load | 12.719684400 |
| checkpoint_load_restore | 0.974232300 |
| validation_wall | 6.688399000 |

| VRAM phase | Allocated bytes | Reserved bytes | Peak allocated | Peak reserved |
| --- | --- | --- | --- | --- |
| after_base_load | 1307833856 | 1333788672 | 1307833856 | 1333788672 |
| after_restore | 1307859456 | 1333788672 | 1307859456 | 1333788672 |
| baseline | 0 | 0 | 0 | 0 |
| final | 1341413888 | 1371537408 | 1360115712 | 1371537408 |
| validation_peak | 1341413888 | 1371537408 | 1360115712 | 1371537408 |

## Exact historical reproduction and confidence disclosure

Historical output matched **540/540 complete accepted prediction objects**, with no mismatch IDs. Every quality aggregate and mixed/en slice matched PR #79 exactly. Accepted PR #79 evidence remains frozen.

Uncalibrated confidence summaries were compared separately and are **not byte-identical**. Only these two means differed; all typed min/max and all validity min/max/means were exactly equal. No threshold or metric was changed, and the cause of these tiny floating-point differences is not established by this run.

| Gold class | Field | PR79 | Retry | Delta |
| --- | --- | --- | --- | --- |
| spotify_play_track | typed_play_probability.mean | 0.5721718226869901 | 0.5721653945247333 | -6.428162256821857e-06 |
| unknown | typed_play_probability.mean | 0.5441796181102594 | 0.5441714122891426 | -8.205821116824552e-06 |

## Historical and S3 diagnostic metrics

| Metric | Historical | S3 |
| --- | --- | --- |
| supported_unknown_recall | 240/240 (100.0000%) | 240/240 (100.0000%) |
| unknown_false_acceptance | 0/240 (0.0000%) | 0/240 (0.0000%) |
| supported_play_recall | 11/300 (3.6667%) | 12/300 (4.0000%) |
| full_semantic_accuracy | 240/540 (44.4444%) | 241/540 (44.6296%) |
| track.presence_recall | 11/300 (3.6667%) | 12/300 (4.0000%) |
| track.exact_span | 0/300 (0.0000%) | 3/300 (1.0000%) |
| track.correct_null | 0/0 (N/A) | 0/0 (N/A) |
| artist.presence_recall | 0/126 (0.0000%) | 0/126 (0.0000%) |
| artist.exact_span | 0/126 (0.0000%) | 0/126 (0.0000%) |
| artist.correct_null | 174/174 (100.0000%) | 174/174 (100.0000%) |
| album.presence_recall | 0/204 (0.0000%) | 0/204 (0.0000%) |
| album.exact_span | 0/204 (0.0000%) | 0/204 (0.0000%) |
| album.correct_null | 96/96 (100.0000%) | 96/96 (100.0000%) |

Both safety gates: supported unknown 240/240; false acceptance 0/240; blocked before renderer 60/60; eligibility leakage 0; play without valid TRACK 0. Optional correct-null denominators are gold-absent play rows, not all 540 rows.

| Slice | Decoder | Play recall | Semantic accuracy | TRACK exact | Unknown recall |
| --- | --- | --- | --- | --- | --- |
| mixed | historical | 10/204 (4.9020%) | 156/360 (43.3333%) | 0/204 (0.0000%) | 156/156 (100.0000%) |
| mixed | s3 | 11/204 (5.3922%) | 157/360 (43.6111%) | 3/204 (1.4706%) | 156/156 (100.0000%) |
| en | historical | 1/96 (1.0417%) | 84/180 (46.6667%) | 0/96 (0.0000%) | 84/84 (100.0000%) |
| en | s3 | 1/96 (1.0417%) | 84/180 (46.6667%) | 0/96 (0.0000%) | 84/84 (100.0000%) |

In both decoders, mixed ARTIST presence/exact is 0/30 and correct-null 174/174; ALBUM presence/exact 0/108 and correct-null 96/96. English ARTIST and ALBUM presence/exact are each 0/96; correct-null 0/0 (N/A). False acceptance is 0/156 mixed and 0/84 en. All exact slice metric objects remain in JSON.

## Transitions and deterministic first-failure decomposition

| Across 540 supported rows | Count |
| --- | --- |
| play_to_play_offsets_changed | 10 |
| play_to_unknown | 0 |
| unchanged_play_exact_same_offsets | 1 |
| unchanged_unknown | 528 |
| unknown_to_play | 1 |

| Across 300 gold play rows | Count |
| --- | --- |
| historical_play_to_s3_play | 11 |
| historical_play_to_s3_unknown | 0 |
| historical_unknown_to_s3_play | 1 |
| unchanged_unknown | 288 |

| First-failure bucket | All 300 | Mixed 204 | English 96 |
| --- | --- | --- | --- |
| full_semantic_exact | 1 | 1 | 0 |
| s3_track_exact_optional_incomplete_or_wrong | 2 | 2 | 0 |
| s3_track_invalid_or_missing | 218 | 144 | 74 |
| s3_track_present_not_exact | 9 | 8 | 1 |
| typed_not_play | 70 | 49 | 21 |
| validity_below_threshold | 0 | 0 | 0 |

All 240 unknown rows stayed unknown. The one unknown→play transition is gold play candidate-01279, TRACK [3,9) versus gold [3,11), with optional slots null. No historical play became unknown.

## Span deltas and exact 11-play cross-reference

S3 TRACK presence 12, exact 3, null on gold play 288. Start deltas (prediction minus gold): `{"0": 6, "13": 1, "18": 1, "19": 1, "7": 3}`. End deltas: `{"-15": 1, "-2": 1, "-23": 1, "-6": 1, "-7": 2, "0": 5, "15": 1}`. ARTIST/ALBUM each have zero present spans, zero exact spans, 300 null on gold play and empty delta/non-exact-present lists. Their correct-null rates are listed above; absence when gold-present remains an error.

| Case ID | Historical TRACK | S3 TRACK | Gold TRACK | S3 exact | Changed optional slots |
| --- | --- | --- | --- | --- | --- |
| candidate-01205 | [8,31) | [9,31) | [9,31) | true | none |
| candidate-01211 | [15,26) | [16,26) | [9,26) | false | none |
| candidate-01218 | [3,10) | [4,10) | [4,33) | false | none |
| candidate-01253 | [8,31) | [9,31) | [9,31) | true | none |
| candidate-01268 | [21,25) | [22,25) | [4,32) | false | none |
| candidate-01277 | [8,18) | [9,18) | [9,33) | false | none |
| candidate-01284 | [23,27) | [23,27) | [4,12) | false | none |
| candidate-01391 | [8,24) | [9,24) | [9,24) | true | none |
| candidate-01402 | [9,20) | [10,20) | [3,20) | false | none |
| candidate-01403 | [15,19) | [16,19) | [9,26) | false | none |
| candidate-01472 | [22,26) | [23,26) | [10,32) | false | none |

All 11 stayed play; ten changed by trimming only leading whitespace, while candidate-01284 stayed unchanged. Three became TRACK-exact: candidate-01205, candidate-01253, candidate-01391. Only candidate-01391 became full-semantic-exact; the other two still lack ALBUM. JSON retains historical/S3/gold offsets for all slots and the nine remaining non-exact present TRACK cases. No utterance text is logged.

| Slot | Learned exact | Gold-BIO structural ceiling | Remaining count gap |
| --- | --- | --- | --- |
| album | 0/204 | 203/204 | 203 |
| artist | 0/126 | 126/126 | 126 |
| track | 3/300 | 297/300 | 294 |

The gold-BIO ceiling is representability evidence, not achieved model performance. The large learned gap remains even with the reviewed S3 seam. No retrospective PR #79 result was rewritten.

## Validation and preserved state

Pre-live focused Laya suites: 476 passed, 1 durable-result skip; no-compute preflight passed with zero audit events. Post-live focused/full/Windows and static checks are recorded below after completion. Ordinary regression tests are a separate authorized CPU/source/integrity scope and may read existing train/held-out/Stage A fixtures; they never invoke this live mode. This does not broaden the live validation-only boundary.

- Post-live focused Laya suites: **477 passed** (12.14 s).
- Full unit suite: **1103 passed**, two existing Starlette/httpx/AnyIO deprecation warnings (303.42 s).
- Windows integration: **5 passed** (8.75 s).
- Qualified Python compileall app/scripts/tests: passed.
- Base-to-head git diff --check: passed; 25 relative Markdown links passed.
- Frozen runner/tests unchanged after live; all 12 historical script hashes unchanged; app/artifacts zero diff.
- Issues #80/#82 body/comments/state/title/updatedAt equal before/after snapshots.
- Primary PROJECT_STATUS.md SHA 968907d1545ade5fe7be6e4958af2ccc23781a9f138fbfe1deae5bddb8e864bc, docs/SIRI_SHORTCUT.md SHA 31a6ffc09aa25a819b506157cc847c0482bb72eff96827a5bc8fc9e76e259c89, docs/SIRI_SHORTCUT_V2.md SHA 934a932464238ff3594ad90f36c4934b95a7b8b3ce59737dcc785484b01e1484 unchanged.
- All tests used the qualified Python; CPU pytest only appended existing project test dependencies without changing the qualified venv. That append was never propagated into the live child.

## Decision, non-actions and deviations

Remaining first-failure counts are dominated by invalid/missing TRACK after typed/validity gates: 218/300 (72.67%); typed-not-play is 70/300 (23.33%); validity first-fail is 0. Among 12 emitted plays, 9 have non-exact TRACK, 2 exact TRACKs still have optional-slot errors, and 1 is fully exact. This supports a separately reviewed span/BIO learning and typed-decision diagnosis/design gate before any further adaptation proposal. The current run does not establish the internal causes within the invalid/missing bucket, and does not authorize another diagnostic or full head-only adaptation.

No training, optimizer, scheduler, backward, threshold tuning, hyperparameter search, checkpoint save/mutation, encoder update, act-head update, held-out quality, Stage A live input, production app wiring, Spotify/Siri/Windows action, memory enablement or fallback enablement. No live retry. Issues #80/#82 remain unchanged; Issue #68 remains OPEN. PR #87 is merged at the exact main above. The new PR remains OPEN/UNMERGED for independent review.

All six persistent flags remain false: training_authorized, model_compute_authorized, semantic_memory_enabled, local_ai_fallback_approved, LOCAL_SEMANTIC_MEMORY_ENABLED, LOCAL_AI_FALLBACK_APPROVED.

Deviations/limitations: two uncalibrated typed probability means differ as quantified above; complete prediction objects and all quality aggregates still reproduce exactly. No execution-scope deviation or blocker occurred. This diagnostic PASS is not model-quality acceptance.
