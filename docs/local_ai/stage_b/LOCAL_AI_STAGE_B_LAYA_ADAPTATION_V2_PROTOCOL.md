# Laya adaptation v2 protocol — first small experiment design

Status: **protocol proposed for independent review; compute and training unauthorized**.
Reviewed base: `b0491a5f76ca0b614d3718edbd887717b2c32b28` (PR #94 merged).
Protocol version: `laya-adaptation-v2-design-v1`. This supersedes the unchanged
full head-only recipe as the next proposed experiment; historical V1 evidence
and runner remain immutable.

## Evidence and decision

The [PR92 diagnosis](evidence/LOCAL_AI_STAGE_B_LAYA_SPAN_TYPED_VALIDITY_DIAGNOSIS_V3_2026-09-29.md)
records weak B tags, orphan-I, O-heavy predictions, poor typed separation, and
nearly constant validity scores. The [S3 design](LOCAL_AI_STAGE_B_LAYA_SPAN_SEAM_DESIGN.md)
establishes high gold-label representability, not learned quality. The
[train-only target audit](evidence/LOCAL_AI_STAGE_B_LAYA_V2_TARGET_AUDIT_2026-09-30.md)
counts actual current renderer targets, without model outputs or validation rows.
Correlation between a training prior and validity scores is not causation.

The first proposed small experiment retains a frozen backbone and changes
the BIO objective and validity readout. No evidence currently establishes an
encoder feature limitation, so LoRA is excluded. Simultaneously changing two
readouts limits causal attribution: report their diagnostics separately and
do not claim an ablation result.

## Immutable inputs and implementation

- Frozen train is the only training source: 1,800 rows / 300 complete six-row
  groups, byte SHA `54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2`.
- Supported rows alone may render/reach the model. Deterministic/safety rows
  are counted and blocked before rendering. Group-based selection must retain
  exact manifest/case identities and cannot be chosen using loss or outputs.
- Keep corpus text, raw spans, seven BIO labels, overlap-to-token assignment,
  tokenizer, pinned source/model identities, input rendering, user-state mask,
  and closed play/unknown intent mapping unchanged.
- Entire encoder and upstream act_head stay frozen, in eval, with no gradients
  and unchanged parameter hashes. Existing type_emb, optional nonencoder head,
  scorer, project span head and validity head are the allowed trainable groups.
  No act_head loss, new architecture or new trainable parameter group.
- Keep S3 `local_ai_stage_b_laya_span_decoder.py` unchanged: strict BIO grammar,
  selected-offset checks, reviewed O/O exception, outer Unicode whitespace-only
  tightening, forbidden-text filtering, optional nulling, grounded required
  TRACK, and all-null unknown. No BIO/offset repair or decoder relaxation.
- The future implementation must bind source hashes, backend, precision,
  device identity, full residency, checkpoint namespace/schema and no CPU
  fallback before any model access. Reuse reviewed safety/process checks.

## Selected BIO objective family

Choose **seven-class token CE plus stratified slot-start versus rest BCE using
the same seven logits**. Preserve Linear(hidden_size, 7), current labels and
user-state-only masking; add no start-head parameters.

For each user token with logits z and current gold label y, retain CE(z,y).
For each slot s, use p_s = softmax(z)[B-s] and t_s = 1[y=B-s]. The positive
term is -log(p_s), and the negative term is -log(1-p_s). Compute these stably
from logsumexp rather than taking logs of rounded probabilities.

Normalize positive and negative strata separately for each slot, so abundant
non-start tokens cannot hide a missed start through the reduction alone.
The future total is token CE plus the reviewed coefficients multiplying each
slot's positive/negative term. **Every coefficient is UNSET here**, including
relative task-loss coefficients. A batch with an empty stratum records zero
count and no mean, skips that stratum's contribution, and does not invent a
positive label. Its handling and normalization must be frozen before compute.

The [synthetic helper/tests](../../../tests/unit/test_local_ai_stage_b_laya_v2_target_audit.py)
return separate unweighted terms, demonstrate dilution of a rare B error in
plain token averaging, and penalize false B predictions. They use invented
rectangular CPU numeric tensors, standard-library arithmetic and finite
differences; no autograd, backward, optimizer or real hidden states.
The same B logit receives direct start supervision mathematically; these
checks establish mechanical sensitivity, not training efficacy or GPU parity.
This is a boundary-sensitive reweighting of supervision, not a legal-BIO
transition model: an orphan-I prediction can still occur and S3 must reject it.

Risks: more false starts, duplicate spans, loss competition and unknown false
acceptance. Falsification: start-sensitive synthetic terms fail their checks,
or the authorized small run improves token statistics without improving legal
and exact TRACK spans. Report B/I confusion and legal structure independently.
Do not add focal loss, class-weight search, CRF, slot-presence heads, boundary
residuals or label rewriting to this first experiment.

## Selected validity representation

Keep the existing play=1 / unknown=0 target and existing gate for comparability.
It is always `validity_label = 1 - intent_label` under current label IDs;
it is **redundant diagnostic supervision**, not independent span correctness
or an independent semantic truth signal.

Replace encoder CLS `hidden[:,0]` with the arithmetic mean of frozen encoder
hidden states selected by user_state_mask, then use the existing validity
linear head. Pooling excludes prompt, options, special tokens and padding;
reject an empty mask. Mask before reduction so excluded nonfinite values cannot
contaminate the result. Preserve the head dimension and parameter policy.

Synthetic tests cover selected-only pooling, determinism, equivalent-padding
invariance, invalid masks and finite selected values. Real hidden-state
discrimination remains unproven. Mean pooling may lose order and still learn
only a prior. If the small experiment retains near-constant/non-discriminating
scores, stop expanding this readout. Do not redefine validity targets or remove
the gate. No threshold fitting/sweep is part of this first small experiment;
any later calibration needs its own versioned review.

## Typed reporting and conjunctive safety

Keep native typed architecture and bounded play/unknown targets. Separately
report, with fixed denominators, gold play classified play, gold unknown
classified unknown, and gold unknown classified play. Also report how typed,
validity and TRACK rejection combine; a final unknown produced by failed TRACK
cannot count as a correct standalone typed classification.

Improved spans can expose the existing typed unknown false positives.
**Any supported-unknown final false acceptance (>0) stops the run and prevents
full adaptation.** Grounded structure alone does not prove an exact song span.
Report legal TRACK, exact TRACK, optional presence/exact/null and full semantic
accuracy separately, preserving existing metric definitions and denominators.

## Future compute authorization manifest — mandatory, not completed here

Before implementation/live dispatch, independently approve and freeze:

| Field | Current design / outstanding freeze |
|---|---|
| Objective family | Selected above; implementation parity must be reviewed |
| Numeric loss/class weights, coefficients, normalization | UNSET |
| Learning rate, optimizer and scheduler configuration | UNSET |
| Epochs, exact step budget, batch size, seed | UNSET |
| Training subset / group and case-ID oracle | UNSET; train-only selection |
| Validity representation | User-state masked arithmetic mean |
| Validity gate value | Reviewed V1 gate retained for comparability; no tuning |
| Decoder | Exact reviewed S3 source hash; no changes |
| Checkpoint rule | Terminal checkpoint at predeclared training budget; no validation selection |
| Validation pass count and evaluation ordering | UNSET; bounded final evaluation after training, no training feedback |
| Train diagnostics / meaningful-improvement criteria | UNSET; predeclare legal/exact TRACK and typed-separation criteria |
| Hardware/precision/residency/process and immutable identities | Bind reviewed identities in new manifest |
| Stop rules / one experiment identity | Mandatory below; no automatic retries |

No numeric tunable is selected in this protocol. Existing class IDs, corpus
counts/hashes and reviewed V1 gate are compatibility identities, not newly
tuned values. A single predeclared small experiment may be separately
authorized after review; this document does not authorize it or a full run.

## Stop, LoRA and pivot

1. Integrity, data eligibility, grounding, finite/device/residency or frozen
   parameter violation: STOP. Any supported-unknown false acceptance: STOP.
2. If the small v2 run does not meet the predeclared meaningful improvement
   criteria for legal/exact TRACK **and** typed separation, stop frozen-backbone
   head-only expansion. A safety-only PASS or better token loss is insufficient.
3. No ad hoc seed changes, threshold changes, added epochs, checkpoint selection,
   alternative subsets or automatic live retry. A new proposal needs materially
   new evidence and separate review, rather than a differently worded retry.
4. Poor train fit alone is not proof of frozen-feature limits. First rule out
   target/mask errors and inadequate readout/objective/optimization. Strong train
   fit with poor validation may indicate distribution/generalization limits,
   not necessarily a backbone capacity problem.
5. Only evidence supporting a frozen-representation limitation may justify one
   separately reviewed upper-layer LoRA experiment. No LoRA settings selected
   here. If that separately approved path still cannot approach the existing
   frozen quality gates safely, stop Laya and return to another candidate/control
   under a new research authorization. Do not run another model under this task.

## Data discipline and authority

The target audit opens train rows only. Validation language coverage is quoted
from the immutable corpus manifest, not recomputed from validation data.
Train has no pure-English rows while validation contains an English slice;
keep this known distribution limitation visible. Source-group splitting is
unchanged. This protocol may use already-reviewed validation diagnosis for
design, but does not create new validation-derived statistics or tune on it.

Future development uses train plus appropriately authorized validation only.
Held-out Stage B and Stage A remain untouched until the accepted final gates;
neither may supply tuning, target construction, selection or diagnosis inputs.
No production app, Spotify/Siri/Windows action, checkpoint/model load, GPU,
training or quality-acceptance claim occurs in this task.

All persistent flags remain false: training_authorized,
model_compute_authorized, semantic_memory_enabled, local_ai_fallback_approved,
LOCAL_SEMANTIC_MEMORY_ENABLED and LOCAL_AI_FALLBACK_APPROVED.
Next gate: independent review of this protocol/audit, then a separate
implementation/compute-authorization decision with the outstanding manifest
fields fixed. Leave the PR open and unmerged.
