# Versioned Laya S3 research path preflight — 2026-09-27

**Result: `LAYA_S3_VERSIONED_RESEARCH_PATH_PREFLIGHT_PASSED`.**

## Scope and provenance

Exact main/base `c3f863f006356db2e179ea7f4207ac099effa604`; branch `codex/stage-b-laya-s3-versioned-research-path`. PR #84 merged reviewed head `7eae4dbfcb2ca7f00945f187dbe8f6ed59a18332`. Preflight verifies exact origin/main and that HEAD descends from that exact branch base. No model compute or training is authorized.

- Path identity: `laya-s3-research-v1`.
- Decoder identity: `reviewed-s3-span-decoder-v1`.
- New path source SHA: `b01a254db9bfb1d84023c0f9d88ff7d49ccb789ff7888961ea7e000dfa2d4388`.
- Verified decoder SHA: `f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845`.
- Reviewed implementation canonical SHA: `08e8173175f5a879b7677cde2fdaedbc844ae5e4dc790b1d81bb174c46d4bcbb`.

Default invocation and `--preflight` are the same no-compute mode. There is **no live mode**; `--live` is rejected by argument parsing before preflight. This module does not modify or activate app or any historical runner. A future evaluation implementation remains separately reviewed/authorized.

## Historical identities

All six historical files are read-only and byte-identical before/after. Their expected hashes come from the verified canonical PR #84 implementation record, not newly assumed values.

| File | Before = after SHA-256 |
| --- | --- |
| local_ai_stage_b_laya_adapter.py | `cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e` |
| local_ai_stage_b_laya_small_adaptation.py | `85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e` |
| local_ai_stage_b_laya_span_decoder.py | `f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845` |
| local_ai_stage_b_laya_span_representability_audit.py | `6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087` |
| local_ai_stage_b_laya_span_seam_design.py | `7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72` |
| local_ai_stage_b_laya_span_seam_implementation_verify.py | `35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2` |

## Tokenizer and frozen data

Tokenizer/config files are hashed only; no tokenizer or model is loaded, and torch is not imported. Revision metadata is `052592a15d198d9ad47da779604259b10b47b7aa`; before/after identities match. Full model aggregate is reviewed metadata only; no weights opened.

| File | SHA-256 |
| --- | --- |
| rl_agent_config.json | `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6` |
| tokenizer/tokenizer.json | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |
| tokenizer/tokenizer_config.json | `2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f` |

| Split | Rows | SHA-256 |
| --- | --- | --- |
| train | 1800 | `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2` |
| validation | 600 | `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a` |

The exact bytes/counts and authoritative per-row schema are verified before selection. Only train/validation are read. The historical `verified_data()` path is not called because it would read protected files. Validation composition is checked with the non-I/O historical helper. Same bytes are checked after preflight.

## Existing selector and deterministic future schedule

The unchanged historical selector executes over the exact train file. Its entire returned manifest equals the canonical PR #79 selection, not just its aggregate counts.

- Algorithm: `six-row-signature-largest-remainder-third-v1`.
- Manifest SHA: `fd69f3280becca6e12225d36960b016bd8e6e4bf9e3962e393c4bef0e0ff2c1d`.
- 600 source rows / 100 whole groups / 498 eligible / 102 blocked.
- Three deterministic epoch permutations; 63 batches each, 62 batches of 8 plus final 2; 189 total future steps. No steps executed.

| Epoch | Existing PR #79 permutation SHA, reproduced |
| --- | --- |
| 1 | `b44dc6d3b17bcc1111682ec12fc9d0fd7117f0d603c792bb5a4e9846520153ce` |
| 2 | `d7319a20f58f3eb61f64541a4a2971771b0ad7bd9ef57b24ec5b37e2ff69eb7e` |
| 3 | `f0e81e0981617e35c986974182adb548dfc6d35a07e4465a0bf74bcbf592e127` |

## Recipe compatibility

Every intended non-decoder recipe field is compared with both the actual imported PR #79 `CONFIG` and the immutable canonical PR #79 result. A recipe value is not accepted by comparing two copies of the new declaration. Optimizer nested fields are separate comparisons; tuple/list representation is normalized through JSON. Any difference stops with `STOP_LAYA_S3_RESEARCH_PATH_RECIPE_DRIFT`.

| Field | Intended = actual runner = reviewed evidence |
| --- | --- |
| autocast | `"cuda bfloat16"` |
| batch_size | `8` |
| clip_max_norm | `1.0` |
| drop_last | `false` |
| epochs | `3` |
| grad_scaler | `false` |
| loss_metric_dtype | `"float32"` |
| loss_weights.intent | `1.0` |
| loss_weights.span | `1.0` |
| loss_weights.validity | `1.0` |
| optimizer.betas | `[0.9, 0.999]` |
| optimizer.eps | `1e-08` |
| optimizer.foreach | `false` |
| optimizer.lr | `0.0001` |
| optimizer.name | `"AdamW"` |
| optimizer.weight_decay | `0.0` |
| optimizer_steps | `189` |
| scheduler | `null` |
| seed | `1729` |
| steps_per_epoch | `63` |
| training_mode | `"trainable modules train; encoder and act_head eval"` |
| validation_batch_size | `16` |
| validation_passes | `1` |
| validity_threshold | `0.5` |

All **24 fields** match. Separate source checks inspect the actual pinned functions for encoder/act_head eval, freeze-policy invocation, allowed typed/span/validity optimizer groups, AdamW construction, clip 1.0 and BF16 autocast. The actual freeze helper restricts requires_grad to type_emb/head/scorer; canonical PR #79 parameter groups and unchanged encoder/act_head hashes corroborate it. AST checks find no scaler/scheduler construction. No mode, forward, optimizer or freeze function is executed.

Only semantic decoder provenance changes: historical `strict-grounded-bio-v1` -> `reviewed-s3-span-decoder-v1`. It is outside the training recipe and is explicitly versioned. No optimizer, scheduler or tensors are created.

## Decoder-dispatch proof

The new `validation_decode` helper accepts typed index, validity, BIO labels, mask, offsets and original utterance. It checks label/mask length, maps non-user labels to O, then returns **exactly** `s3_decoder.decode(...)`. It contains no seam implementation and has no historical fallback.

- Actual synthetic CPU call profiling: S3 decode **1**, historical decode **0**.
- Unit spy verifies every argument, user-state masking and exact returned-object propagation.
- The same test patches historical decode to raise; the new path still passes.
- AST checks reject historical decode references including renamed imports, module-global assignment, local decoder/helper definitions and copied seam while-loops; direct historical calls are limited to selector/schedule/validation-composition helpers.
- The new module never monkeypatches historical globals. Profiling restores the previous Python profiler and only observes function calls.

## Future checkpoint identity and process boundary

Future namespace (defined only): `D:\ai\ai\stage_b_laya_s3_research\laya-s3-research-v1\c3f863f006356db2e179ea7f4207ac099effa604`. Future checkpoint schema `laya-s3-research-checkpoint-v1`; result schema `laya-s3-research-result-v1`.

Lexical comparison proves distinction from PR #79 checkpoint directory/schema; neither old nor future checkpoint paths are opened or created. The guard rejects mkdir/rename/remove events, and inherited file guards reject checkpoint/model extensions and unauthorized corpus paths. There is no checkpoint load/write API in this module. No overwrite or experiment-identity reuse is possible through this preflight-only CLI.

Qualified Python ran with `-B -X utf8`, both offline flags, PYTHONPATH removed, and raw-byte parent/child transport. Guard recorded only train/validation corpus opens, zero protected attempts. No model/checkpoint/GPU/held-out/Stage A access; no torch import; no app activation. Existing broad regression fixture/integrity reads are separate test mechanisms, not preflight or model inputs.

All six flags remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.

## Validation, tracker and next gate

Focused research/decoder/verifier/design/audit/historical tests: **214 passed**, including 47 new tests. Full unit: **884 passed**, two existing dependency warnings, 282.54 seconds. Windows integration: **5 passed**. Compileall, staged/base diff checks, 26 relative links and all six source hashes passed. App/frozen artifact/fixture diffs are zero; primary dirty hashes unchanged. Qualified Python only; pytest uses the existing read-only test dependency path, never propagated to preflight. No dependencies changed.

Issue #68 current facts identify PR #84 merged and the new path PR/head while preserving useful historical implementation evidence. Issues #80/#82 were snapshotted read-only and compared unchanged; final remote verification repeats this check. Primary dirty status/Shortcut hashes are preserved.

Next, after independent review, a **separately authorized validation-only diagnostic inference using the existing PR #79 checkpoint** may be proposed. This task does not load that checkpoint, rescore PR #79, produce learned predictions, improve quality or authorize full head-only adaptation. Held-out and Stage A remain sealed/out of scope.

[Canonical sanitized JSON](LAYA_S3_RESEARCH_PATH_PREFLIGHT_2026-09-27.json). SHA-256 `38bdead38e5dea83cf45e522279e7280fdfa0aeb08d8d6e12984cff1d7591d87`, computed over sorted compact ASCII UTF-8 JSON excluding only its own hash field.

Development disclosures: the initial static guard rejected an unlisted historical hash-helper call; it was replaced with the existing audit canonical helper and the preflight passed. Final evidence was refreshed after alias-aware source checks. A mistyped qualified-Python path in a version-query command did not execute any Python; all actual Python execution used the qualified interpreter.
