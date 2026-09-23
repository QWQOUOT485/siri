# Stage B Independent Review Guide

This guide is for an independent human or external reviewer of the frozen
Stage B candidate pool. The generator author is not an independent label
reviewer. Passing unit tests, the production-alignment audit, or a packet
construction check is supporting evidence only; none of those checks creates a
review decision.

## Current review boundary

The workflow covers only:

```text
frozen candidate corpus
  -> deterministic review packets
  -> empty decision schema
  -> offline decision validation
```

It does not accept, reject, relabel, correct, select, split, seal, train, or
run inference on candidates. The final 3,000-row selection, group-aware
train/validation/held-out split, held-out sealing, and any correction workflow
are later work.

The packets are review allocations, not train/validation/held-out splits. The
current allocation is 12 deterministic packets with 300 rows each, and every
candidate appears exactly once.

Multiple independent reviewers may review the same candidate. Every raw
reviewer decision is preserved. Candidate-level progress is computed
separately, so a candidate contributes exactly once to its aggregate state:

| submitted values for one candidate | candidate aggregate state |
| --- | --- |
| none | `pending` |
| one or more `accept`, and no other value | `accepted` |
| one or more `reject`, and no other value | `rejected` |
| one or more `needs_correction`, and no other value | `needs_correction` |
| two or more values that are not identical | `conflict` |

There is no majority vote, reviewer precedence, reject-wins rule, or automatic
adjudication. Raw submission totals are exposed as `decision_count` and
`raw_decision_counts`; candidate progress and dimension reports use the
aggregate state and count each candidate once. A disagreement remains a
`conflict` and is not automatically accepted or rejected.

## Frozen source identity

The validator fails closed unless all four frozen v5 identities match:

| artifact | SHA-256 |
| --- | --- |
| candidate corpus | `658628de9659c91688415f9aa3c29292d89037954a213f6f5a49e6e6fa1258bd` |
| entity catalog | `7b0a09825cb40e046a7c27cc4f51f08aa22d42e5a5587c23710f831c3c0f15cb` |
| generator config | `ddb44af17a7f2ce81ef413ce122f8d2d5664755f0be8495b5c319e850215412e` |
| candidate manifest | `ff1e4a89524be878c9aaa491cb978c753728ef45baed1051512ec0954e838950` |

The source files are under `artifacts/local_ai/stage_b/v5/`. The v4 files
remain at `artifacts/local_ai/stage_b/` as historical audit evidence. The
v5 script inventory is separately pinned at
`0aa72c72acb984135507b72ea179cd3812c163d644ee1c03942a858aef8c0b36`.
A regenerated corpus cannot silently reuse this review manifest or a v4
decision file. No v4 decision was imported into the v5 directory.

## What to review in each row

Review the actual utterance and the provisional fields shown in the packet:

- Does the language sound plausible for the stated language tag and script?
- Is the semantic scope correct: supported play, supported semantic unknown,
  deterministic-only, or safety-only?
- Is the intent correct?
- Are the track, artist, and album spans exact, including punctuation and
  optional-slot presence/absence?
- Does a supported unknown genuinely lack a safe supported interpretation?
- Is a deterministic-only or safety-only boundary correctly preserved?
- Is the ASR/homophone/spacing/case mutation plausible rather than a generator
  artifact?
- Does the entity surface look natural and diverse instead of teaching a
  shortcut?

Unit tests do not replace this semantic review. Do not use the catalog or
production Spotify data to invent a better label for a row; review the row as
it is presented and record the problem when the provisional label is wrong.

## Review decisions

Decision JSONL contains one object per line with exactly these required fields:

```json
{
  "candidate_id": "candidate-00001",
  "record_sha256": "<matching packet record hash>",
  "reviewer_role_id": "independent-reviewer-a",
  "decision": "accept",
  "reason_codes": [
    "label_correct",
    "natural_language_ok",
    "span_correct",
    "scope_correct",
    "entity_surface_ok"
  ]
}
```

`reviewer_note` is optional and bounded. `reviewer_role_id` must be an opaque
role identifier such as `independent-reviewer-a`, `independent-reviewer-b`, or
`human-reviewer-1`; do not use an email, username, account ID, credential, or
private identity.

Allowed decisions are exactly:

- `accept`
- `reject`
- `needs_correction`

There is no submitted `pending` decision. `accept` requires all five positive
codes:

```text
label_correct
natural_language_ok
span_correct
scope_correct
entity_surface_ok
```

`reject` and `needs_correction` each require at least one negative code. The
closed reason-code set is:

```text
label_correct
natural_language_ok
span_correct
scope_correct
entity_surface_ok
unnatural_language
wrong_intent
wrong_scope
wrong_negative_reason
wrong_track_span
wrong_artist_span
wrong_album_span
wrong_optional_slot_status
implausible_asr
language_tag_mismatch
traditional_simplified_mismatch
entity_surface_artifact
duplicate_semantics
safety_boundary_problem
other_review_blocker
```

Use `needs_correction` when the row may be repairable but cannot be accepted
as written. Such rows remain excluded from later accepted selection until a
separate reviewed correction workflow exists. Do not silently rewrite the
utterance or spans.

## Group reporting

Decisions are row-level. A source group contains six variants, and one row's
decision is never copied to the other five. Group health is based on each
row's candidate aggregate state. The reportable states are:

- `unreviewed`: every row is `pending`
- `partially_reviewed`: at least one row is reviewed and no higher-priority
  health state applies
- `fully_accepted`: all six rows are `accepted`
- `partially_rejected`: at least one row is `rejected`, with no conflict or
  needs-correction row
- `needs_correction`: at least one row is `needs_correction`, with no conflict
- `review_conflict`: at least one row is `conflict`

Multiple agreeing reviewers for a row still produce one `accepted`,
`rejected`, or `needs_correction` candidate state. These are reports, not
propagated decisions. Conflict resolution and adjudication are not implemented.

## Offline validation

Build or rebuild the packets from the exact reviewed source:

```text
.venv\\Scripts\\python.exe scripts\\local_ai_stage_b_independent_review.py
```

Validate an external decision JSONL without writing a ledger:

```text
.venv\\Scripts\\python.exe scripts\\local_ai_stage_b_independent_review.py --validate-decisions <decisions.jsonl>
```

The validator rejects unknown candidate IDs, record-hash mismatches, duplicate
decisions from one reviewer for one candidate, invalid decision or reason
codes, empty/non-opaque reviewer roles, extra fields, missing positive accept
evidence, negative decisions without a negative reason, and source identity
mismatches.

The initial workflow state is deliberately empty:

```text
total candidates: 3600
decision_count: 0
raw decision counts: accept=0, reject=0, needs_correction=0
reviewed: 0
accepted: 0
rejected: 0
needs_correction: 0
conflict: 0
pending: 3600
```

The current workflow keeps `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false`. It has no network, subprocess, model,
Spotify, Windows, Siri, LM Studio, production-parser, RAG, vector, or
embedding authority path.
