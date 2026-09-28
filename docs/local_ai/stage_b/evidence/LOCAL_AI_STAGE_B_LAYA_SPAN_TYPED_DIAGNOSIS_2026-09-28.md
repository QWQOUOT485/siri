# Laya span/BIO and typed-decision diagnosis — 2026-09-28

**Current result: `LAYA_SPAN_TYPED_DIAGNOSIS_NEW_BLOCKER`.** The sole authorized validation-only invocation was consumed. No trustworthy PR #89 token-level diagnosis was produced. This document records the exact observable boundary; it does not reinterpret missing values as zero or rerun the model.

## Reviewed inputs and authorization

- Exact origin/main and PR #88 merge: `b6af8e4c4599647b16273c5ece6f21360b9d5e5c`.
- Branch: `codex/stage-b-laya-span-typed-diagnosis`.
- Frozen runner/tests commit: `a67802b9b2614298c0a138029ace69d272b1cb17`.
- Executed runner SHA-256: `5ec4a8ae373f4cb6923e0b0fa77e55b79df6bd5b0a9767540dbbe2fdd1faa446`; no runner/test edits after the attempt.
- Task-scoped authorization: `laya-span-typed-diagnosis-v1`. Exactly one validation-only child process permitted; no retry, training, threshold or decoder changes.
- Reviewed PR #88 canonical SHA: `babb424a086de8bbf83ff5ab68a91dcea39cb5ae1e1247dc5347a1cd40f6a42b`; reviewed PR #88 runner SHA: `48c081e68255e6bb8aa86886c03b4673567f6f9666497ba9fec10e8df2c1a567`; verified S3 decoder SHA: `f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845`; PR #79 accepted canonical SHA: `4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8`.
- Qualified Python: `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe` with `-B -X utf8`, offline flags, raw-byte subprocess transport, `GIT_OPTIONAL_LOCKS=0`. Target is the enumerated cuda:1 / AMD Radeon RX 9070 XT / gfx1201; **selection and residency during this PR #89 live child are unobserved**.

The no-compute preflight passed before the run, with exact validation 600 rows / 100 groups / 540 supported / 60 blocked and byte SHA `297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a`. It verified pinned source revision `42626c348753fbb17572a813127df2278a1ec527`, model aggregate `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf`, qualified venv inventory `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337`, and PR #79 checkpoint SHA `199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d` (177,394,599 bytes, read-only, nonredirected). It bound 13 historical Laya script hashes and six accepted canonical result identities. All six persistent flags were false. Its audit recorded zero filesystem/network/denial events. Preflight identity-only reads: validation twice, checkpoint once, PR #88 evidence three times. Its model loads, checkpoint deserializations and validation passes were all **zero**.

The frozen source predeclared the reviewed seven BIO IDs (`O`, `B/I-TRACK`, `B/I-ARTIST`, `B/I-ALBUM`), eight-category precedence for the exact PR #88 218-case set, complete 7×7 confusion, gold-span token coverage, typed distributions, structural typed-versus-span matrix, separate typed-only gate-preserving 70-row counterfactual, optional-slot analysis and sanitized per-row user-only labels/offsets. Focused pre-live tests were **513 passed / 1 expected durable-result skip**. A synthetic validity-below-0.5 case proved that structural TRACK validity is counted separately from typed-only emission. These CPU tests do **not** prove a live diagnosis.

## Sole live attempt and saved observation

The frozen parent dispatched exactly one `--validation-diagnostic` child after independently reviewed readiness, clean checkout, exact main and absent scratch/result checks. The external raw parent stdout/stderr were saved as `D:\ai\ai\pr89-live.stdout` (1,698 bytes) and `D:\ai\ai\pr89-live.stderr` (0 bytes); these are not repository artifacts. The [sanitized durable parent result](LAYA_SPAN_TYPED_DIAGNOSIS_2026-09-28.json) has canonical SHA-256 `4887b9c77210110a7b8a5311d8a5767ee858b75b1e82a34776f75d57858f3cce`.

The parent recorded `child_returncode=0`, but received no uniquely prefixed child result (`child_result_missing_or_ambiguous` at frozen runner parent line 709). It therefore emitted `LAYA_SPAN_TYPED_DIAGNOSIS_NEW_BLOCKER`. The frozen parent did not retain child stderr; outer stderr is empty. The exact child failure point and cause are **unknown**. An exception during exit-time result construction/sanitization is a possible explanation from source inspection, **not an established root cause**. No model probe, code change or second live invocation followed.

| Field | Observation |
| --- | --- |
| Live child dispatches | 1, consumed |
| Child process return code | 0 |
| Unique structured child result | Absent |
| Base-model loads/completed loads | Unknown |
| Checkpoint deserializations/restores | Unknown |
| Validation passes/forward batches | Unknown |
| PR #88 typed/validity/historical/S3 540/540 reproduction | Unknown, not established |
| BIO confusion and label metrics | Unknown, not established |
| Exact 218-case taxonomy and trace counts | Unknown, not established |
| Typed 70 counterfactual and overlap | Unknown, not established |
| Optional-slot diagnosis and mixed/en slices | Unknown, not established |
| Training/backward/optimizer/scheduler execution | Unknown from child telemetry; frozen runner contains no training path |
| Child data opens and before/after model/checkpoint/source identity | Unknown from child telemetry |
| Parent scratch file inventory | Empty |
| Parent scratch cleanup | Verified absent |

The parent transport fallback intentionally records the unobserved compute fields as `null`. The scratch directory `D:\ai\ai\stage_b_laya_diagnosis\span-typed-v1` was removed and verified absent. No binary checkpoint or model artifact was committed. The frozen runner's static call path contains one `laya.load`, one CPU `torch.load(..., weights_only=True)`, one historical BF16 forward call site, eval/no-grad/freeze and no optimizer/backward path; whether those call sites were reached is not known.

**No PR #89 quality, BIO, typed, taxonomy, counterfactual or adaptation-target conclusion is supported.** The prior PR #88 diagnostic remains valid historical evidence: play recall 12/300, TRACK exact 3/300, unknown recall 240/240, with 218 invalid/missing TRACK and 70 typed-not-play first failures. Do not present those as newly measured PR #89 results.

## Protected state, validation and next gate

The runner/test source stayed frozen after the attempt; no app/, frozen corpus, fixture or historical Laya source changes were made. The primary worktree's three protected dirty files, Issues #80/#82 and all six persistent authority flags remain unchanged. Issue #68 stays OPEN. Post-live CPU/static checks are recorded below after completion; ordinary regression fixture/integrity reads are separate from the one live child and do not establish child data access.

Post-live CPU/static validation: focused Laya suite **514 passed**; full unit suite **1,140 passed** with two existing dependency deprecation warnings; Windows integration **5 passed**; `compileall -q app scripts tests` passed. Base-to-head `git diff --check`, **26** Markdown relative links, frozen runner/test byte hashes, zero diff under `app/` and frozen artifacts, three primary dirty-file SHA-256 values, Issues #80/#82 read-only snapshots, and scratch absence passed. These tests do not recover the missing child result or establish any live model phase.

**Smallest evidence-producing next action:** a **separately authorized transport-only diagnosis** using saved source/controlled process boundary to retain child stderr or an exit-time failure marker, without loading model weights, checkpoint, or validation rows. Review that evidence before considering any new model pass. PR #90 remains **design-only** and is not started here; PR #91 is not created. Full head-only adaptation remains unauthorized. No training, threshold tuning, decoder change, held-out or Stage A quality evaluation, app wiring, production approval or model-selection claim was authorized or implemented in this PR; the child execution phases remain unknown.

All six persistent flags remain `false`: `training_authorized`, `model_compute_authorized`, `semantic_memory_enabled`, `local_ai_fallback_approved`, `LOCAL_SEMANTIC_MEMORY_ENABLED`, `LOCAL_AI_FALLBACK_APPROVED`.
