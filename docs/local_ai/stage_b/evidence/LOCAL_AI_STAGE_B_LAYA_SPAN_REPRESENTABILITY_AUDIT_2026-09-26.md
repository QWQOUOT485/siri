# Laya exact-span representability audit — 2026-09-26

**Current result: `STOP_LAYA_SPAN_REPRESENTATION_TRACK_BELOW_GATE`.**

## Scope and identities

Tokenizer-only structural evidence at main `7c55924c7ae5f90f519c3d73889b04d0c430423b`, branch `codex/stage-b-laya-span-representability-audit`. The PR head identifies the committed implementation and evidence. PR #79 is merged; its safety triage passed while diagnostic quality was poor. It is not rescored here.

The audit reuses unchanged `render_row` and the exact PR #79 strict decoder, with gold BIO labels, typed play and validity 1.0. It does not load model weights or the research checkpoint, run inference/GPU/training, or change rendering/decoding. Transformers incidentally imported torch; no torch compute occurred. Qualified Python ran with `-B -X utf8`, both offline flags set and PYTHONPATH removed.

The runtime file/network audit guard recorded only train and validation corpus opens, zero denied attempts, no held-out or Stage A rows, and no model/checkpoint opens. The broad requested regression suites are separate: existing corpus/seal and Stage A tests may read their own integrity/fixture data. Those are not audit inputs or model inputs.

Tokenizer revision: `052592a15d198d9ad47da779604259b10b47b7aa`. Local tokenizer/config SHA and revision metadata were verified before and after:

| File | SHA-256 | Bytes |
| --- | --- | --- |
| rl_agent_config.json | `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6` | 472 |
| tokenizer/tokenizer.json | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` | 34363188 |
| tokenizer/tokenizer_config.json | `2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f` | 545 |

Full model aggregate `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` is carried from reviewed PR #79 metadata only; it was deliberately not recomputed because this task does not open weight bytes. No trained artifact was accessed.

| Frozen split | Rows | Supported plays | SHA-256 |
| --- | --- | --- | --- |
| train | 1800 | 900 | `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2` |
| validation | 600 | 300 | `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a` |

Exact byte identities, counts and authoritative per-row schema/offset/null validation passed before rendering; identical bytes were rechecked afterward. No full corpus/seal verifier was invoked because it would open protected rows.

## A/B/C and exact representability

- **A:** current gold BIO targets round-trip through the unchanged strict decoder to the exact raw character span.
- **B:** current round-trip fails, but at least one valid contiguous whole-token interval has exactly the gold start/end. This identifies a target/decoder seam discrepancy, not a claim that training alone will repair it.
- **C:** no such whole-token interval exists. Better token labels alone cannot produce the exact raw span.

The interval search uses only user-state tokens, positive in-range ordered offsets and exact endpoints. It never trims, normalizes, slices within a token, or approves a replacement decoder. The strict decoder also has row-wide validity checks and required-TRACK gating, so a slot with exact target endpoints can still be B. The audit does not attribute all B cases to one root cause.

| Split / slot | Present denominator | A | B | C | Current exact | Any-token exact |
| --- | --- | --- | --- | --- | --- | --- |
| train ALBUM | 582 | 155 | 179 | 248 | 155/582 (26.63%) | 334/582 (57.39%) |
| train ARTIST | 612 | 257 | 159 | 196 | 257/612 (41.99%) | 416/612 (67.97%) |
| train TRACK | 900 | 299 | 350 | 251 | 299/900 (33.22%) | 649/900 (72.11%) |
| validation ALBUM | 204 | 0 | 0 | 204 | 0/204 (0.00%) | 0/204 (0.00%) |
| validation ARTIST | 126 | 10 | 0 | 116 | 10/126 (7.94%) | 10/126 (7.94%) |
| validation TRACK | 300 | 0 | 34 | 266 | 0/300 (0.00%) | 34/300 (11.33%) |

Supported unknown rows were O-only: train 600, validation 240. Deterministic/safety rows were never rendered and had null targets: train 300, validation 60. Present-slot denominators exclude null slots.

## Whitespace and target-boundary diagnostics

These counts describe gold-target round-trip mismatches, not new model predictions. Unicode whitespace stripping is used only to classify diagnostics; no output or metric is repaired.

| Split / slot | Leading only | Trailing only | Both only | Non-whitespace error | Missing/multiple |
| --- | --- | --- | --- | --- | --- |
| train ALBUM | 179 | 0 | 0 | 29 | 219 |
| train ARTIST | 147 | 0 | 0 | 0 | 208 |
| train TRACK | 237 | 0 | 0 | 12 | 352 |
| validation ALBUM | 185 | 0 | 0 | 1 | 18 |
| validation ARTIST | 111 | 0 | 0 | 0 | 5 |
| validation TRACK | 263 | 0 | 0 | 3 | 34 |

| Split / slot | First start exact | Last end exact | Both exact | First before only | Last after only | Both expanded | Other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train ALBUM | 362 | 553 | 334 | 219 | 28 | 1 | 0 |
| train ARTIST | 416 | 612 | 416 | 196 | 0 | 0 | 0 |
| train TRACK | 652 | 889 | 649 | 240 | 3 | 8 | 0 |
| validation ALBUM | 0 | 203 | 0 | 203 | 0 | 1 | 0 |
| validation ARTIST | 10 | 126 | 10 | 116 | 0 | 0 | 0 |
| validation TRACK | 34 | 297 | 34 | 263 | 0 | 3 | 0 |

Sanitized case/slot/offset examples for each observed boundary category are in the JSON. No utterance, token string, provider ID or secret is persisted.

## Existing PR #79 eleven-play cross-reference

Existing canonical result SHA: `4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8`. All eleven gold TRACK spans are category C. No checkpoint was loaded and no prediction was regenerated.

| Case ID | Gold [start,end) | Recorded [start,end) | Start delta | End delta | Diagnostic |
| --- | --- | --- | --- | --- | --- |
| candidate-01205 | 9:31 | 8:31 | -1 | 0 | leading_whitespace_only |
| candidate-01211 | 9:26 | 15:26 | 6 | 0 | non_whitespace_boundary_error |
| candidate-01218 | 4:33 | 3:10 | -1 | -23 | non_whitespace_boundary_error |
| candidate-01253 | 9:31 | 8:31 | -1 | 0 | leading_whitespace_only |
| candidate-01268 | 4:32 | 21:25 | 17 | -7 | non_whitespace_boundary_error |
| candidate-01277 | 9:33 | 8:18 | -1 | -15 | non_whitespace_boundary_error |
| candidate-01284 | 4:12 | 23:27 | 19 | 15 | non_whitespace_boundary_error |
| candidate-01391 | 9:24 | 8:24 | -1 | 0 | leading_whitespace_only |
| candidate-01402 | 3:20 | 9:20 | 6 | 0 | non_whitespace_boundary_error |
| candidate-01403 | 9:26 | 15:19 | 6 | -7 | non_whitespace_boundary_error |
| candidate-01472 | 10:32 | 22:26 | 12 | -6 | non_whitespace_boundary_error |

Correction to the task premise: five recorded predictions start one character early, but only **three** also end exactly at gold and are whitespace-only. The other two end 23 and 15 characters early. The frozen saved offsets above are authoritative; PR #79 metrics are unchanged.

## Gate and next action

The validation TRACK 95% gate requires at least 285/300 exact spans. Only **34/300** are representable under the current whole-token/raw-character seam, even before learning quality. Thus the gate is structurally blocked. ARTIST **10/126** and ALBUM **0/204** are additional blockers; TRACK alone determines the requested STOP label.

Next: separately review a span representation/target/decoder seam design, with strict raw-character grounding and equivalent safety boundaries, before authorizing full head-only adaptation. This audit authorizes no trimming patch, renderer change, rescore, model run, held-out quality run or production promotion. Full head-only adaptation remains separately unauthorized; Issue #68 stays OPEN.

All persistent flags remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.

## Reproducibility and validation

Canonical JSON: [sanitized structured result](LAYA_SPAN_REPRESENTABILITY_AUDIT_2026-09-26.json). Hash uses sorted keys, compact separators, ASCII escaping, UTF-8 and no NaN, excluding only its own `canonical_result_sha256` field.

Canonical result SHA-256: `1785052a43f1e20662ce27da9d57d857b3ff132af156afc3d7f7cebf602de2f5`.

Focused audit/adapter/small-adaptation tests: **65 passed** (new audit cases: 21). Full unit suite: **724 passed**, two existing dependency deprecation warnings, 262.42 seconds. Windows integration: **5 passed**. Compileall and diff checks passed; **26 Markdown relative links** resolved. App, frozen artifacts, fixtures, adapter and small-adaptation source have zero diff. Primary status/Shortcut SHA-256 values remained unchanged. Qualified Python uses the existing primary venv test dependencies via a read-only `sys.path.append` only in CPU pytest; no dependency change or propagation to the audit child.

The first Windows test command used nonexistent `tests/integration` and collected no tests; the corrected documented `tests/integration_windows` suite is the reported result.

No app/frozen corpus/fixtures/adapter/small-adaptation changes are authorized. Primary dirty status and Shortcut hashes must remain identical.
