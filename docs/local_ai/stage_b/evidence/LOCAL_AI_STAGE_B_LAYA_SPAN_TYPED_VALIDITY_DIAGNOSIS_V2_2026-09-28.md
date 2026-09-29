# PR #91 explicit transport and span/BIO/typed/validity diagnosis

**Current result: `LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V2_NEW_BLOCKER`.**
The one authorized validation-only live invocation was consumed. The new
transport exposed an exit-stage failure, but no trustworthy model diagnosis
was emitted. PR #88 remains the authoritative model diagnostic.

## Reviewed input and pre-live freeze

- Base `origin/main`: `c1bb2a6904141aea9d606d29d60b12c80bd2b691` (PR #90 merged).
- Pre-live frozen runner/tests commit: `05142022558ee9d4dc0034c80f598557b9f4ec8a`.
- Frozen [v2 runner](../../../../scripts/local_ai_stage_b_laya_span_typed_diagnosis_v2.py) byte SHA-256: `20db77c91261aea73b61f3a6c70aad1cc25d65eeca1affbdd025f121e32ded9e`.
- Reviewed canonical results: PR #88 `babb424a086de8bbf83ff5ab68a91dcea39cb5ae1e1247dc5347a1cd40f6a42b`; PR #89 blocker `4887b9c77210110a7b8a5311d8a5767ee858b75b1e82a34776f75d57858f3cce`; PR #90 transport `607c731fce78468b4427d1f16238d8515dfa740a6a5f4450fbf57408cfd6b156`.
- Historical runner hashes: PR #89 `5ec4a8ae373f4cb6923e0b0fa77e55b79df6bd5b0a9767540dbbe2fdd1faa446`; PR #90 `750941d6e3048b8bd14ccd89b781085c5c13640418695470f003d22264e5acbe`.
- Qualified Python: `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe` with `-B -X utf8`, offline flags, raw-byte transport and child-local controlled scratch.
- No-compute preflight passed: validation 600 rows / 100 groups / 540 supported / 60 blocked, byte SHA-256 `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`; model loads, checkpoint deserializations and validation passes all zero. Preflight identity-only reads were validation twice, checkpoint once and PR #88 evidence three times.
- The PR #79 checkpoint was absent from Git, present at its reviewed external path, read-only, nonredirected, size 177,394,599 bytes and SHA-256 `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d`. Scratch and new result path were absent before dispatch.
- Pre-live synthetic transport and analysis tests: **87 passed, one expected durable-result skip** under the qualified Python with test-only pytest path. The actual v2 `emit_child_result` was exercised in healthy and failing subprocesses. No `atexit` primary result registration exists. Sanitization, canonical hash, NaN/object JSON, stdout write and flush fault injections returned nonzero with sanitized stderr envelopes; parent parser rejected missing, duplicate, malformed, bad-hash and invalid-schema markers.

## Sole live attempt and parent-observed transport facts

The frozen parent dispatched one --validation-diagnostic invocation. The
[sanitized durable JSON](LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V2_2026-09-28.json)
has canonical SHA-256:
70a1f83e18c9df42d5a7163f16c108beb01c485fdab60882310f6f95288ab310.

Directly observed by the parent:

| Fact | Observation |
| --- | --- |
| Live invocations | 1, consumed |
| Outer process | return code 1 |
| Child process | return code 2 |
| stdout | 0 bytes; 0 result markers |
| Transport | explicit-v2; primary result was not emitted from atexit |
| Child stderr | retained; 529 bytes; sanitized envelope only |
| Failure envelope | stage sanitization; exception AttributeError; message redacted |
| Scratch | inventory empty; cleanup verified |

These observations do not include child execution counters, a traceback, or
the exact object passed to the sanitizer.

## Frozen-control-flow-established live reachability

The frozen control flow places the inner sanitization_check(result, ...)
after result['diagnosis'] = diagnose(...). The deterministic sanitizer
failure at that point, followed by the observed explicit-v2 sanitization
failure from emit_child_result(...), establishes that the live child reached
and completed the preceding gates. This is source-implied reachability, not
transported child telemetry:

- Base model load path completed.
- Checkpoint deserialize and restore paths completed.
- validation_pass() completed, including all 34 forward batches.
- Post-validation parameter-hash gate completed.
- The PR #88 decision/prediction reproduction gate completed without raising.
  Frozen control flow establishes that the PR #88 decision/prediction
  reproduction gate completed before diagnosis/sanitization. The detailed
  reproduction object was not durably serialized, so its payload cannot be
  independently read back from this run.
- Historical report and reproduction completed.
- S3 report and S3 safety gate completed.
- PR #88 failure-bucket case-ID membership equality completed.
- diagnose() completed and produced the in-memory diagnosis payload.

Source-implied counts, kept separate from parent-observed telemetry:

~~~text
base_model_loads = 1
checkpoint_deserializations = 1
checkpoint_restores = 1
validation_passes = 1
validation_forward_batches = 34
~~~

The failure-bucket gate required exact equality with PR #88's
play_failure_case_ids; the S3 safety gate required prior.safety(result['s3'])
to be true. No new taxonomy counts can be recovered from those gate outcomes.
The inner exception is caught by child(), which returns its result and guard;
the emitter then sanitizes the retained result and encounters the same
non-string-key defect. The child did not reach result['status'] = PASS.

## Unavailable diagnostic payload

The diagnosis was constructed in memory but was not durably serialized.
Treat these newly computed values as **unavailable, not zero**:

- 7×7 BIO confusion matrix.
- Per-label precision, recall, and F1.
- Exact 218-item TRACK taxonomy counts and TRACK structure counts.
- Exact 70 typed-counterfactual counts.
- Typed probability/margin distributions and typed-vs-span overlap matrix.
- Validity distribution/AUROC.
- ARTIST raw BIO diagnosis.
- ALBUM raw BIO diagnosis.
- Mixed/en diagnosis.
- Decoder-interaction counts.

PR #88 remains the latest readable model-metric evidence. Its historical 218
and 70 case-set findings are not new PR #91 counts.

## Deterministic sanitizer defect and evidence limits

The frozen v2 runner contains a deterministic sanitizer defect: the diagnosis
payload contains integer-key bio_label_mapping, while the sanitizer calls
.lower() on every dictionary key. This defect is source-proven and
CPU-synthetically reproduced, and it deterministically prevents successful
sanitization of a completed diagnosis payload.

The sole source creates these keys with dict(enumerate(LABELS)); the
recursive sanitizer uses key.lower() without a string-type guard. A
CPU-only synthetic call with {0: "O"} raises AttributeError. The explicit
failure envelope did not include a child traceback or the exact live object,
so that object was not directly observed in the envelope. This does not
retroactively prove PR #89's historical inner failure.


## Boundaries, postchecks and next gate

Read-only postchecks matched pre-live identities: pinned Laya source revision
`42626c348753fbb17572a813127df2278a1ec527`, model aggregate
`eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf`,
qualified venv inventory `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337`,
validation SHA and checkpoint SHA/size/read-only state above. The frozen
runner/test bytes were not edited after dispatch. No `app/`, frozen artifact,
historical runner or fixture diff was introduced. Held-out and Stage A rows
were not authorized as inputs and the source guard excludes them; without
child telemetry, their open counts are not asserted. No training, decoder
repair, threshold search, adaptation, app wiring or quality acceptance was
authorized or added. Six persistent authority flags remain false.

Post-live CPU/static validation: focused PR #89/#90/v2 suites **87 passed / 1
expected pre-live skip**; full unit suite **1,191 passed** with two existing
dependency deprecation warnings; Windows integration **5 passed**;
`compileall -q app scripts tests`, `git diff --check`, 29 relative links,
evidence canonical hash, frozen runner SHA and zero protected-path diff passed.
The main worktree's three pre-existing file hashes stayed unchanged. These
checks do not recover the missing child payload.

Issue #68 stays OPEN; Issues #80/#82 stay unchanged. PR #91 remains
OPEN/UNMERGED. **Next gate:** independent review of this corrected evidence. Any runner repair or new model run requires separate authorization.
There is no automatic retry.
