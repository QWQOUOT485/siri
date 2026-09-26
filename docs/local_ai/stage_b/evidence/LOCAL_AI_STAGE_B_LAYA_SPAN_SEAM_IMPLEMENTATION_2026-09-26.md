# Reviewed S3 seam implementation verification — 2026-09-26

**Result: `LAYA_SPAN_SEAM_S3_IMPLEMENTATION_VERIFIED`.**

## Reviewed state and scope

Base `db987d26e7561391876de3e27afa113460efdde5`; branch `codex/stage-b-laya-s3-seam-implementation`. PR #83 merged reviewed head `88ad75bdc0ddaf7bac10ec684b2522fe7bebc3d2`; design canonical hash `99bb654c9be4499054d930103416551e7583ed5c6fbf979de7ad4820274acf04`. The final PR head binds the implementation and evidence.

This creates a reusable pure decoder with the full typed/validity gate. It imports only stdlib and the unchanged adapter, and reuses the exact `adapter.FORBIDDEN_TEXT` object. It does not import the design module. No production Laya/BIO decoder path currently exists in app; this task does not invent or wire one. Existing generic Local AI behavior is unchanged. The verifier alone imports the reviewed design helper and calls both implementations directly.

No model weights, checkpoint, GPU/model forward, learned logits, training, held-out rows or Stage A rows were used. The tokenizer-only subprocess used qualified Python `-B -X utf8`, both offline flags, PYTHONPATH removed and raw-byte output transport. The reused file/network guard recorded only train/validation corpus opens, zero protected attempts. Transformers incidentally imported torch; no compute. Full-model aggregate remains reviewed metadata only, with no weight bytes read.

Broad requested regression tests have separate existing fixture/integrity reads; those are not verifier/model inputs. No PR #79 rescore or mutation of PR #81/#83 evidence.

## Historical and new source hashes

All four historical files were hashed before and after; byte identity is required or `STOP_LAYA_S3_HISTORICAL_SOURCE_MUTATED`.

| Historical file | Before = after SHA-256 |
| --- | --- |
| local_ai_stage_b_laya_adapter.py | `cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e` |
| local_ai_stage_b_laya_small_adaptation.py | `85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e` |
| local_ai_stage_b_laya_span_representability_audit.py | `6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087` |
| local_ai_stage_b_laya_span_seam_design.py | `7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72` |

| New file | SHA-256 |
| --- | --- |
| local_ai_stage_b_laya_span_decoder.py | `7a8a8348ddbac15f8eac0b3c5c67cff24075f81db6febc49ac99b08e366cf221` |
| local_ai_stage_b_laya_span_seam_implementation_verify.py | `35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2` |

## Frozen tokenizer and input identities

Revision `052592a15d198d9ad47da779604259b10b47b7aa`; tokenizer/config identities checked before/after:

| File | SHA-256 |
| --- | --- |
| rl_agent_config.json | `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6` |
| tokenizer/tokenizer.json | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |
| tokenizer/tokenizer_config.json | `2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f` |

| Split | Rows | Supported plays | SHA-256 |
| --- | --- | --- | --- |
| train | 1800 | 900 | `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2` |
| validation | 600 | 300 | `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a` |

The verifier validates exact bytes/counts and authoritative row schema before rendering, then confirms byte identity afterward. Only supported plays are rendered; exact present-slot denominators are required. No protected corpus/seal verifier is invoked.

## Actual implementation oracle and design parity

For every supported play, the verifier renders once through the unchanged adapter, supplies the same gold BIO sequence to `design.isolated(..., trim=True)` and to the actual `implementation.decode(0, 1.0, ...)`, and compares entire output objects before counting spans. There is no duplicate decoder in the verifier and no golden-output substitution. The expected counts are equality checks, not minimum gates. Tests replace the actual decoder with wrong output and require design-drift failure.

| Split | Actual TRACK | Actual ARTIST | Actual ALBUM | Design counts | Entire-output parity |
| --- | --- | --- | --- | --- | --- |
| train | 886/900 | 612/612 | 549/582 | [886, 612, 549] | 900/900; mismatches 0 |
| validation | 297/300 | 126/126 | 203/204 | [297, 126, 203] | 300/300; mismatches 0 |

Train ALBUM **549/582 = 94.33%** remains unchanged. The **three validation TRACK** and **one validation ALBUM** non-whitespace failures remain failures; sanitized IDs and exact offsets are retained in JSON. No punctuation/non-whitespace trimming was added to improve counts. These are oracle implementation-equivalence results, not model quality improvement.

## Safety contract and tests

The typed gate accepts only the closed integer play index; unknown/invalid indices fail to all-null. Validity must be numeric, finite, inside[0,1] and at least0.5; threshold unchanged. Global malformed geometry fails the row. Exactly one contiguous B/I slot is required. Invalid required TRACK clears all; invalid optional slots null independently.

Valid positive O/O offsets may overlap only with nondecreasing starts and ends. True O/O reversals still reject the row. Any overlap/order conflict involving selected tokens invalidates affected owners. TRACK conflict means unknown; optional-only conflict nulls affected optional slots. Selected spans crossing non-user-state fail. No sort, merge, repair or offset normalization occurs.

Outer tightening removes only `str.isspace()` characters and cannot expand the coarse token span. Punctuation, letters, digits, CJK, hyphens and apostrophes remain. Empty TRACK fails all; empty optional nulls only itself. Exact adapter forbidden-text policy is reused. Output remains a closed offset-only literal-substring schema without provider/execution authority.

- Reviewed adversarial inventory: **24/24 passed against the real decoder**.
- Added implementation inventory: **28/28 passed**, including source-immutability gates.
- URL / Spotify URI / Windows path / command policy: **4/4 passed**, exact regex object reused.
- Additional tests cover threshold boundary, invalid typed/numeric values, oracle counts above or below expected, canonical hashing, actual-decoder execution, and source mutation.

## Process and authority

New decoder is not wired into app or historical research runners. No training, checkpoint reuse, residual heads, tokenizer modification, quality benchmark or production behavior change. Six persistent flags remain false: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.

Issues #80 and #82 were snapshotted read-only (title/body/state/updatedAt/comments) before work and compared unchanged after implementation. Final remote verification also checks them. Neither is modified by this task. Issue #68 remains OPEN.

## Reproducibility and validation

[Complete sanitized result](LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json). Canonical hash uses sorted compact ASCII JSON, UTF-8 and no NaN, excluding only its own hash field.

Canonical result SHA-256: `2e5962c7fc2aa88c79de97dc2f11996446f8afc4e2fb8d310c4a567ff06ee21c`.

Focused new decoder/verifier + design/audit/adapter/historical decoder suites: **176 passed**, including **67 new tests**. Full unit: **835 passed**, two existing dependency deprecation warnings, 266.02 seconds. Windows integration: **5 passed**. Compileall/diff checks and **26 relative links** passed. Historical source hashes match before/after; app/frozen artifacts/fixtures have zero diff; primary dirty hashes unchanged. Qualified Python only; pytest appends existing primary test dependencies read-only in its CPU process, never into the verifier child. No package changes.

Next gate: independent implementation review. Any later research/runtime integration and model training require separate review/authorization; full head-only adaptation remains unauthorized.

Final staged checking found one extra EOF blank line in the new decoder. It was removed without logic changes; the actual tokenizer verifier was rerun to bind the final source SHA, preserving all 1,200 parity outputs and exact counts. The 67 new tests passed again. Full-suite results above precede this whitespace-only cleanup. Final base-to-head diff check passes.
