# PR #90 child-result transport-only diagnosis

**Current result:** `LAYA_CHILD_TRANSPORT_DIAGNOSIS_COMPLETED`. This is a
synthetic subprocess lab, not a rerun of PR #89 or evidence of model quality.
PR #90 starts from main `c1a624a068beebc8c641dcd1357c526278428ac6`.
PR #89 blocker evidence is merged there; its saved result has canonical SHA
`4887b9c77210110a7b8a5311d8a5767ee858b75b1e82a34776f75d57858f3cce`.

The [durable JSON](LAYA_CHILD_TRANSPORT_DIAGNOSIS_2026-09-28.json) records all
12 subprocesses, return codes, byte counts, stage traces, sanitized exception
class/message, and classifier outcomes. Its canonical SHA-256 is
`607c731fce78468b4427d1f16238d8515dfa740a6a5f4450fbf57408cfd6b156`.
The [standalone runner](../../../../scripts/local_ai_stage_b_child_transport_diagnostic.py)
uses only Python's standard library and fixed synthetic data.

## Frozen PR #89 source binding

The [PR #89 runner](../../../../scripts/local_ai_stage_b_laya_span_typed_diagnosis.py)
was read statically at byte SHA-256
`5ec4a8ae373f4cb6923e0b0fa77e55b79df6bd5b0a9767540dbbe2fdd1faa446`.
It registers `finish_child` through `atexit`; that function sanitizes, computes
the canonical hash, then serializes and prints the prefixed result. The parent
requests `stderr=subprocess.PIPE` but does not copy child stderr into durable
evidence. No PR #89 child mode was invoked or modified.

## Synthetic scenario matrix

| Case | Injection | rc | Markers | Last stage | Classifier |
| --- | --- | ---: | ---: | --- | --- |
| A | Healthy | 0 | 1 | `atexit_completed` | `TRANSPORT_OK` |
| B | Sanitization | 0 | 0 | `sanitization_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| C | Canonical hash | 0 | 0 | `canonical_hash_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| D | NaN/Inf JSON | 0 | 0 | `json_dumps_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| E | Object JSON | 0 | 0 | `json_dumps_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| F | stdout write | 0 | 0 | `stdout_write_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| G | synthetic stdout flush | 0 | 0 | `stdout_write_completed` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |
| H | Duplicate result | 0 | 2 | `atexit_completed` | `DUPLICATE_MARKER` |
| I | Malformed JSON | 0 | 1 | `atexit_completed` | `MALFORMED_JSON` |
| J | Incorrect hash | 0 | 1 | `atexit_completed` | `BAD_CANONICAL_HASH` |
| K | Nonzero exit | 7 | 0 | none | `NO_MARKER_NONZERO_EXIT` |
| L | Exit-time exception | 0 | 0 | `stdout_write_started` | `NO_MARKER_RC0_WITH_ATEXIT_ERROR` |

`pr89_external_symptom_reproduced=true`: **atexit exception can produce rc0 + no marker + stderr-only failure**. The exact PR #89 inner failing operation remains **unknown** because its child stderr was not retained. The G injection uses a local buffer to simulate an unflushed stdout result; it does not claim a real OS flush failure occurred. Static candidates (Python containers/scalars, numpy scalar, tensor/object, nonfinite float, Path/object) are `STATIC_CANDIDATE_ONLY`; none establishes PR #89 runtime causality.

## Boundary and next gate

No model weights, checkpoint, dataset rows, tokenizer, GPU, forward/backward,
optimizer, scheduler, training, or adaptation were accessed or run. All six
persistent authority flags remain false. The [unit test](../../../../tests/unit/test_local_ai_stage_b_child_transport_diagnostic.py)
checks the matrix, transport classifier, canonical hash, static binding, and
scope. Protected model/data/app/fixture paths and the PR #89 runner are
unchanged. Issue #68 remains OPEN; Issues #80/#82 remain unchanged. PR #90 is
OPEN/UNMERGED. Stop for broad milestone review before another PR or model pass.

Verification: 3 focused CPU-only tests passed; compileall, `git diff --check`,
and four relative links passed. Broad unit and Windows integration suites were
not run because they can exercise model/data paths outside this task's strict
transport-only scope. No quality benchmark was run.
