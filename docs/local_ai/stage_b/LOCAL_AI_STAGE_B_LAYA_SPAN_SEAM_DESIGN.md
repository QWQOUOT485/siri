# Laya span-seam design: tokenizer/gold-label oracle only

## Recommendation and review boundary

**Propose S3: strict slot isolation plus outer Unicode-whitespace tightening.**
Result: `LAYA_SPAN_SEAM_DESIGN_S3_FEASIBLE`.
This is a design proposal, not an accepted decoder implementation or learned
quality result. PR #81 is merged and its structural blocker remains valid for
the unchanged current decoder. No model weights, checkpoint, model compute,
training, held-out rows or Stage A rows were used. PR #79 is not rescored.

The [oracle evidence](evidence/LOCAL_AI_STAGE_B_LAYA_SPAN_SEAM_DESIGN_2026-09-26.md)
records all split/slot rates, identities, exact rejection causes and boundary
histograms. The simulation helper is disconnected from app and existing
research runners. Independent design review is the next gate; runtime changes
and any future training each require separate authorization.

## Candidate definitions

| Variant | Structural decoder | Boundary rule |
| --- | --- | --- |
| S0 | Exact unchanged PR #79 strict decoder | Current raw offsets |
| S1 | S0 whole-row rejection retained | Tighten decoded spans by outer `str.isspace()` only |
| S2 | Proposed independent slot validation | Whole-token raw boundaries |
| S3 | S2 | Outer `str.isspace()` only |
| S4 | S2 plus bounded boundary residuals | Gold residuals only in a conditional theoretical simulation |

Every variant receives identical current renderer gold BIO labels, mask and
offsets, with oracle typed play and validity 1.0. Neither model output nor
loss influences selection. The current renderer, current decoder and PR #81
script/results remain unchanged. S0 exactly reproduces every PR #81 train and
validation current-label exact count.

S3 validation: TRACK **297/300**, ARTIST **126/126**, ALBUM **203/204**.
The integer requirements are respectively **285, 120, 194**; all pass.
S1 fails TRACK and ALBUM; S2 fails all three. S4 is not evaluated or preferred
because S3 passes the predeclared validation gates. Larger architectures and
a tokenizer replacement are unnecessary for this feasibility question.

Train S3 is TRACK886/900, ARTIST612/612, ALBUM 549/582. The last is **94.33%**,
below 95%; it remains an explicit limitation. The task's acceptance gates are
validation-specific. This proposal does not promise universal representability
or final model quality; punctuation-containing token overhangs remain untouched.

## S3 structural contract

1. Preserve existing eligibility, bounded typed play/unknown and validity gate
   upstream. TRACK is required; no TRACK means unknown and all slots null.
2. Validate sequence lengths, tag domain, user-state mask and raw bounds.
   Non-user-state labels/offsets are rejected. Invalid unselected raw offsets
   reject the row because their geometry cannot be trusted.
3. For each slot, require exactly one B followed only by contiguous same-slot I
   tokens. Orphan I, duplicate B, discontinuity or multiple spans invalidate that
   slot. Invalid TRACK fails final play; invalid optional slots become null.
4. Do not sort, merge, clip or repair invalid offset order. All token pairs are
   checked. Any overlap/reversal involving selected slot tokens invalidates the
   affected selected owners. Cross-slot conflict with TRACK fails final play;
   optional-only conflict nulls both affected optional slots.
5. **Explicit O/O geometry exception:** valid positive offsets of unselected O
   tokens may overlap when both starts and ends are nondecreasing. They produce
   no span. Decreasing O/O starts or ends reject the row. This is not arbitrary
   recovery from invalid token order, nor a waiver for selected token overlap.
6. A surviving coarse slot span is exactly the first selected token's start to
   the last selected token's end, inside the original user utterance.
7. Tighten only while the outer character satisfies Python `str.isspace()`.
   Empty results invalidate the slot. No punctuation, letter, digit or CJK
   character is removed. No normalization, substitution, addition or expansion.
8. Preserve forbidden text filtering (URI/URL/path/command patterns), closed
   offset-only outputs and the downstream grounding/policy boundary. No provider
   object, execution target or authority is introduced.

Why the O/O exception matters: the exact current whole-row rejection in all
34 affected validation rows is `pair[0] < last_end`, on prefix offsets `[0,1]`
then `[0,2]`, both labelled O. These are valid monotonic overlapping tokenizer
mappings outside every predicted slot. The first failure erases 57 present-slot
outputs (34 TRACK, 5 ARTIST, 18 ALBUM). No selected TRACK safety error is being
suppressed. Tests explicitly retain failure for reversed unselected offsets,
selected overlap, malformed TRACK and optional conflicts.

The construction gives a direct bound: tightening starts at coarse [a,b), then
only increments a or decrements b while removing whitespace; every nonempty
result satisfies original_a <= a < b <= original_b. Output is always the literal
original substring. The 24 adversarial fixtures exercise the specified cases;
passing finite fixtures is not a universal security certification.

## Future training compatibility (not implemented)

For S3, keep the current token-overlap BIO targets and frozen raw-character gold
spans. The oracle demonstrates that deterministic tightening aligns those
labels in >=95% of each validation present-slot category. Do not teach whitespace
prediction or alter the frozen corpus. Token-level masked span CE can remain;
any changed objective requires separate review. Typed/validity objectives,
eligibility and closed intent schema are outside this design change.

A future implementation review must port this exact contract, test the O/O
geometry exception and all malformed-slot cases, and demonstrate no change to
execution authority before any model training is proposed. Oracle labels do not
measure whether a learned head will supply valid BIO labels.

## S4 fallback design (not implemented or evaluated)

Retain BIO coarse spans. For each present slot, define two nonnegative integer
residuals: `left = gold_start - first_token_start` and
`right = last_token_end - gold_end`. Require left < first-token width and right
< last-token width; zero is valid. Decode only as
`[first_start + left, last_end - right)`, and require a nonempty result within
the coarse span. Invalid/missing residuals invalidate the slot; invalid TRACK
means unknown, invalid optional slots mean null. Structural rejection is never
repaired by residuals.

If later needed, a bounded categorical design could use two shared per-token
classifiers with K+1 integer classes each. K must be fixed in a separate design
review, with width-dependent illegal classes masked; wider boundaries without a
representable residual fail closed. Added outputs are 2(K+1); added linear-head
parameters are 2(K+1)(H+1), e.g. 66(H+1) for an illustrative K=32 (not selected
here). Boundary-only masked cross entropy would supervise the first/last slot
tokens; weighting relative to BIO CE would need review. No residual heads,
losses, tensors or optimizer are implemented in this task.

## Distribution diagnosis and remaining limits

Validation contains mixed/English play families; train contains Traditional,
Simplified and mixed families. The frozen row metadata and exact offsets show
that first-token overhangs track this family composition. For example, train
TRACK first starts exactly in459/462 Hant and144/144 Hans rows; all96 English
validation TRACK rows start one whitespace character before gold. Mixed
`play_mixed_code_switch` is exact at start in49/49 train and34/34 validation;
the other five mixed TRACK families start one character early in every row
(245 train,170 validation). See complete sanitized family/language histograms
in the JSON. This explains the observed geometry difference without claiming
corpus leakage or inferring unobserved generation/assignment intent.

Whitespace tightening deliberately leaves non-whitespace boundary overhangs.
Three validation TRACK and one ALBUM cases remain inexact. Independent design
review must preserve those failures, the train ALBUM limitation, and all six
false authority flags. Full head-only adaptation remains unauthorized.
