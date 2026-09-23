# Independent review decisions

This directory starts empty: no independent reviewer decision has been
submitted. `review_manifest.json` records `decision_count=0`, `reviewed=0`,
`conflict=0`, and `pending=3600`. Raw reviewer submissions are preserved;
candidate progress is aggregated separately.

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
decision to the frozen v6 source identities and rejects duplicate
decisions from the same reviewer for the same candidate.

Multiple reviewers may review the same candidate. For each candidate, the
aggregate state is `pending` when there is no submitted decision, the matching
state (`accepted`, `rejected`, or `needs_correction`) when all submitted
decisions have the same value, and `conflict` when submitted values disagree.
There is no majority vote, reviewer precedence, reject-wins rule, or automatic
adjudication. Raw decisions remain available in `decision_count` and
`raw_decision_counts`; aggregate progress counts each candidate once.

Do not add provider IDs, credentials, OAuth data, private paths, user IDs,
clarification tokens, production authority data, or split labels. Do not edit
the candidate corpus or silently rewrite a candidate. `needs_correction`
rows remain excluded from later selection until a separate reviewed correction
workflow exists.

`conflict` remains unresolved and is ineligible for any future final selection
until a separately reviewed adjudication workflow exists. This PR does not
implement adjudication, a final acceptance ledger, or a final 3,000-row
selector.

This is a human/external-reviewer input boundary. Passing unit tests or the
production-alignment gate is supporting evidence only and never creates an
accept decision.

To validate a local JSONL submission without writing a ledger:

```text
.venv\Scripts\python.exe scripts\local_ai_stage_b_independent_review.py --validate-decisions <decisions.jsonl>
```

The validator is offline-only and fails closed if the candidate artifact
identity differs from the frozen v6 hashes in the review manifest.
