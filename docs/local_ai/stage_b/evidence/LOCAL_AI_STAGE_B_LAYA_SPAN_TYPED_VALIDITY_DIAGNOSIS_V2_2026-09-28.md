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

## Sole live attempt and transport observation

The frozen parent dispatched one `--validation-diagnostic` invocation. The
[sanitized durable JSON](LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V2_2026-09-28.json)
has canonical SHA-256 `b7c80272e4331d7a2ecb716aee705b8272f7c1e676408d50f5de6e501c434f83`.
The outer parent returned 1. Its child returned 2, emitted zero result markers
and zero stdout bytes, and sent 529 stderr bytes. The parent saved only a
sanitized summary: `NONZERO_CHILD_EXIT`, stage `sanitization`, exception class
`AttributeError`, message `redacted`, null errno/winerror. This is the
`explicit-v2` path; `primary_result_emitted_from_atexit=false` and
`child_stderr_retained=true`. No arbitrary traceback, path, utterance or token
text was committed. The parent scratch inventory was empty and cleanup verified
the v2 scratch root absent.

| Live child field | Trustworthy observation |
| --- | --- |
| Live dispatches | 1, consumed |
| Child exit and transport | rc 2; sanitized stderr envelope; no result marker |
| Base-model loads, checkpoint deserializations/restores | Unknown; no child result |
| Validation passes and forward batches | Unknown; no child result |
| PR #88 decision/prediction reproduction | Unknown, not 540/540 established |
| 7×7 BIO confusion, per-label scores, TRACK taxonomy/structure | Unknown |
| Typed 70 set, margin/overlap/counterfactual | Unknown |
| Validity and optional-slot raw BIO behavior | Unknown |
| GPU selection/residency and restored parameter hashes | Unknown |
| Training/backward/optimizer/scheduler | No such call path in frozen runner; execution counters unavailable |

The task's 218 TRACK and 70 typed-not-play case sets remain **PR #88
historical** findings. No new model scores, denominator-specific BIO results,
validity discrimination, or decoder-interaction result can be claimed.

## Failure candidate and evidence limits

The frozen v2 source constructs `bio_label_mapping` using integer dictionary
keys (`dict(enumerate(LABELS))`). Its recursive sanitizer calls `key.lower()`
on every dictionary key. A CPU-only call with an integer key raises
`AttributeError`, matching the live failure envelope's stage and exception
class. This is strong source-and-synthetic evidence for the v2 blocker. The
child envelope intentionally omits a traceback and arbitrary exception text,
so the exact failing object is not directly observed. PR #89's historical
inner failure remains **unknown**; the v2 observation cannot retroactively
prove it.

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
OPEN/UNMERGED. **Next gate:** independent review of this blocker, then a
separately authorized sanitizer correction and bounded model run if approved.
There is no automatic retry.
