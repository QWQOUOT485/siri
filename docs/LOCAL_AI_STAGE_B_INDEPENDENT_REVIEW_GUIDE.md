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

## Frozen source identity

The validator fails closed unless all four reviewed PR #48 identities match:

| artifact | SHA-256 |
| --- | --- |
| candidate corpus | `c7e0a44b69d4033c960a8a1af20b0f4c71ad5674ece4b9a44953a1bea40e68d2` |
| entity catalog | `5deb5bd5a5c7d02b0f2eb864d0bfc4063161c62697d19fc2363f9d3e458b502a` |
| generator config | `d263bd9ec97a897134e9fc5bf1121f16b86a84ff9a361d7046c68f10670d4435` |
| candidate manifest | `a2ceef6205a3bf1a92c31a6ad12d34ac5a1d9aee467ace101532ba9ddfae074f` |

The source files are read-only inputs. A regenerated corpus cannot silently
reuse this review manifest or an old decision file.

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
decision is never copied to the other five. A group is `fully_accepted` only
when every one of its rows has a direct accept decision. Otherwise the report
may show `partially_rejected`, `needs_correction`, or `unreviewed`; those are
reports, not propagated decisions.

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
reviewed: 0
accepted: 0
rejected: 0
needs_correction: 0
pending: 3600
```

The current workflow keeps `LOCAL_SEMANTIC_MEMORY_ENABLED=false` and
`LOCAL_AI_FALLBACK_APPROVED=false`. It has no network, subprocess, model,
Spotify, Windows, Siri, LM Studio, production-parser, RAG, vector, or
embedding authority path.
