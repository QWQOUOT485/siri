# Independent review decisions

This directory starts empty: no independent reviewer decision has been
submitted. `review_manifest.json` records `reviewed_candidate_count=0` and
`pending=3600`.

A future submission must be JSONL with one object per line and exactly these
required fields:

```json
{
  "candidate_id": "candidate-00001",
  "record_sha256": "<the hash from the matching packet row>",
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

`reviewer_note` is optional. The only decisions are `accept`, `reject`, and
`needs_correction`; pending is not a submitted decision. An accept requires
all five positive reason codes. A reject or needs-correction decision requires
at least one negative reason code. The offline validator also binds every
decision to the reviewed PR #48 source identities and rejects duplicate
decisions from the same reviewer for the same candidate.

Do not add provider IDs, credentials, OAuth data, private paths, user IDs,
clarification tokens, production authority data, or split labels. Do not edit
the candidate corpus or silently rewrite a candidate. `needs_correction`
rows remain excluded from later selection until a separate reviewed correction
workflow exists.

This is a human/external-reviewer input boundary. Passing unit tests or the
production-alignment gate is supporting evidence only and never creates an
accept decision.

To validate a local JSONL submission without writing a ledger:

```text
.venv\Scripts\python.exe scripts\local_ai_stage_b_independent_review.py --validate-decisions <decisions.jsonl>
```

The validator is offline-only and fails closed if the candidate artifact
identity differs from the reviewed PR #48 hashes in the review manifest.
