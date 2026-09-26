# Laya span-seam design oracle evidence — 2026-09-26

**Result: `LAYA_SPAN_SEAM_DESIGN_S3_FEASIBLE`.**

## Identity and execution boundary

Base `a69e96284280eaf2aa2b9b59b70814520edeb51d`; branch `codex/stage-b-laya-span-seam-design`. PR #81 merged reviewed head `dfec0ed6c3b214a2dc8dacf93e97f218a7279500`, canonical result `1785052a43f1e20662ce27da9d57d857b3ff132af156afc3d7f7cebf602de2f5`, verified. The new PR head binds these files.

[Design proposal](../LOCAL_AI_STAGE_B_LAYA_SPAN_SEAM_DESIGN.md); [complete canonical result](LAYA_SPAN_SEAM_DESIGN_RESULT_2026-09-26.json).

Qualified Python `-B -X utf8`, both offline flags set, PYTHONPATH scrubbed, raw-byte parent/child output. Reused PR #81 file/network guard records only train/validation corpus opens and zero protected attempts. No weights, checkpoint, held-out/Stage A rows, GPU/model/training calls, or existing decoder modifications. Transformers incidentally imports torch; no compute. Full-model aggregate is reviewed metadata only; no weight bytes were hashed. No PR #79 retrospective rescore or optional counterfactual.

Pinned tokenizer revision `052592a15d198d9ad47da779604259b10b47b7aa`; tokenizer/config identities verified before/after:

| File | SHA-256 |
| --- | --- |
| rl_agent_config.json | `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6` |
| tokenizer/tokenizer.json | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |
| tokenizer/tokenizer_config.json | `2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f` |

| Split | Rows | Plays | SHA-256 |
| --- | --- | --- | --- |
| train | 1800 | 900 | `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2` |
| validation | 600 | 300 | `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a` |

Authoritative per-row schema and exact counts/bytes checked; same split bytes afterward. Full corpus/seal verifier not invoked because protected rows are outside this audit. Broad regression suites are separate existing fixture/integrity mechanisms, not oracle or model inputs.

## S0–S3 exact raw spans

All variants use identical unchanged gold BIO targets. S0 reproduces PR #81; S1 adds whitespace only; S2 isolates slots only; S3 combines both.

| Split | Variant | TRACK | ARTIST | ALBUM |
| --- | --- | --- | --- | --- |
| train | S0 | 299/900 (33.22%) | 257/612 (41.99%) | 155/582 (26.63%) |
| train | S1 | 536/900 (59.56%) | 404/612 (66.01%) | 334/582 (57.39%) |
| train | S2 | 649/900 (72.11%) | 416/612 (67.97%) | 334/582 (57.39%) |
| train | S3 | 886/900 (98.44%) | 612/612 (100.00%) | 549/582 (94.33%) |
| validation | S0 | 0/300 (0.00%) | 10/126 (7.94%) | 0/204 (0.00%) |
| validation | S1 | 263/300 (87.67%) | 121/126 (96.03%) | 185/204 (90.69%) |
| validation | S2 | 34/300 (11.33%) | 10/126 (7.94%) | 0/204 (0.00%) |
| validation | S3 | 297/300 (99.00%) | 126/126 (100.00%) | 203/204 (99.51%) |

Validation integer gates: TRACK 297>=285; ARTIST 126>=120; ALBUM 203>=194. S3 passes all; S4 is a documented fallback, **not evaluated**. Train ALBUM 549/582=94.33% remains below95%, explicitly outside the validation-only acceptance gate. No model-quality improvement is claimed.

## Exact validation rejection causes

All **34 category-B TRACK cases** and every current missing-slot case are classified: **57 slot records / 34 unique rows** = TRACK34 + ARTIST5 + ALBUM18. All encounter the exact first current-decoder rejection `pair[0] < last_end`, at raw prefix offsets `[0,1]` then `[0,2]`, both O-labelled. No invalid offset bounds, malformed TRACK, duplicate B, orphan I, optional BIO defect, selected cross-slot conflict or unexplained invariant accounts for these cases. All sanitized case IDs, affected slots, token indices, offset pairs and reasons are retained in JSON.

These overlapping O/O mappings have nondecreasing starts and ends. S3 ignores only their unselected overlap; it rejects decreasing O/O starts/ends, invalid bounds and conflicts touching a selected slot. This explicit proposed change is tested, not silently introduced into the current decoder.

## Target-boundary distributions

Deltas are current gold target boundary minus frozen gold character boundary. Histogram notation is `delta: count`. Start0 and start-1 counts and end0 counts are explicit in each histogram.

| Split / slot | Start delta | End delta | Prefix empty / whitespace / nonwhite | Suffix empty / whitespace / nonwhite |
| --- | --- | --- | --- | --- |
| train ALBUM | -1: 220, 0: 362 | 0: 553, 1: 29 | 362 / 216 / 4 | 553 / 0 / 29 |
| train ARTIST | -1: 196, 0: 416 | 0: 612 | 416 / 196 / 0 | 612 / 0 / 0 |
| train TRACK | -1: 248, 0: 652 | 0: 889, 1: 11 | 652 / 245 / 3 | 889 / 0 / 11 |
| validation ALBUM | -1: 204 | 0: 203, 1: 1 | 0 / 204 / 0 | 203 / 0 / 1 |
| validation ARTIST | -1: 116, 0: 10 | 0: 126 | 10 / 116 / 0 | 126 / 0 / 0 |
| validation TRACK | -1: 266, 0: 34 | 0: 297, 1: 3 | 34 / 266 / 0 | 297 / 0 / 3 |

The prefix/suffix columns classify the actual characters between coarse token boundaries and gold boundaries; no token strings or utterances are persisted. Complete language and template-family histograms are in JSON.

Validation plays: mixed204 + English96. Train plays: Hant462 + Hans144 + mixed294. All96 English validation TRACK starts overhang by one whitespace character. Mixed code-switch TRACK starts are exact49/49 train and34/34 validation; each other mixed family has startdelta-1 in all rows. Hant train TRACK starts exact459/462 and Hans144/144. This directly ties observed geometry to the frozen family/language composition; it is not evidence of corpus leakage and does not infer why split assignment selected those families.

## Adversarial safety and recommendation

All **24/24** required S3 safety fixtures passed: ASCII/tab/em-space and trailing/both whitespace; punctuation/hyphen/apostrophe/CJK retention; empty result; orphan/duplicate/discontinuous/multiple TRACK; invalid bounds; non-user crossing; optional-slot isolation; malformed TRACK; selected overlaps; no expansion/nonwhite deletion; exact literal substring. Additional tests reject true O/O reversal, URI/path/command text and invalid residuals. No fixture was weakened for the rates.

Prefer S3 as the smallest demonstrated deterministic design. Existing runtime stays unchanged. Next gate is independent design review, then separately authorized seam implementation/verification before any training decision. No full head-only adaptation is authorized. Issue #68 remains OPEN; Issue #80 untouched.

Six flags remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.

## Reproducibility and validation

Canonical result SHA-256: `99bb654c9be4499054d930103416551e7583ed5c6fbf979de7ad4820274acf04`. Sorted keys, compact separators, ASCII escaping and UTF-8; exclude only its own hash field.

Focused design/audit/adapter/small-adaptation tests: **109 passed**, including 44 new tests. Full unit: **768 passed**, two existing dependency warnings, 274.43 seconds. Windows integration: **5 passed**. Compileall and diff checks passed; **28 relative links** resolve. Zero app/frozen artifacts/fixtures/existing renderer/decoder/audit diff; primary status and Shortcut hashes unchanged. Only qualified Python is used; pytest appends existing primary test dependencies read-only, without propagating paths to the oracle subprocess or changing packages.

Two tokenizer-only simulation invocations occurred: initial evidence, then final evidence after adding explicit rejection of truly decreasing O/O offsets and explicit root-cause counts. No model invocation or inference was performed.
