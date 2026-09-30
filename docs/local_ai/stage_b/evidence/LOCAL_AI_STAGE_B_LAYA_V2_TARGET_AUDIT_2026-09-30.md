# Laya v2 train-only target audit — 2026-09-30

Result: **`LAYA_V2_PROTOCOL_TARGET_AUDIT_READY`**. This is a tokenizer/target
audit and protocol proposal, not model-quality acceptance or compute/training
authorization. Base: `b0491a5f76ca0b614d3718edbd887717b2c32b28`; PR #94 merged.

The [sanitized JSON](LAYA_V2_TARGET_AUDIT_2026-09-30.json) has canonical SHA-256
`cc4737c3b36edb7e6e16aae6d9bcdce6d0bf5cab7a64905cad59bc6435dbcf50`.
It contains complete language/family token counts, span-length histograms,
target mappings, source/tokenizer identities and process boundaries. It logs
no utterances, token text, provider identities, secrets or arbitrary local paths.
The [v2 protocol](../LOCAL_AI_STAGE_B_LAYA_ADAPTATION_V2_PROTOCOL.md) selects
the next objective/readout family but leaves numeric tunables unset.

## Identity, eligibility and supervision

Only `final_v1/train.jsonl` supplied rows: byte SHA
`54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2`,
1,800 rows / 300 groups, six rows per group. Exact case membership and canonical
train hash agree with the pinned split assignment and corpus manifest.
Schema uses the existing StageBRecord parser; targets use the existing
adapter.render_row. No whole-corpus/seal verifier was invoked because it would
open forbidden row sources; this audit verifies train and manifest identities,
not a new cross-split leakage certification.

1,500 supported rows rendered; 180 deterministic-only and 120 safety-only rows
were excluded before rendering. Supported play=900, supported unknown=600,
play fraction=60%. All 900 play rows have (intent_label,validity_label)=(0,1);
all 600 unknown rows have (1,0). Thus validity is exactly 1-intent_label for
every eligible row, a duplicate binary semantic target. This is not independent
predicted-span correctness supervision, and does not prove the cause of prior
near-constant validity scores. The V1 small subset's 306/498 prior differs from
the full eligible train prior; the two denominators must not be confused.

## BIO targets and lengths

Counts include supported unknown O-only targets. Only user-state positions
are counted; prompt/options/special/padding labels are excluded.

| Label | Tokens |
|---|---:|
| O | 11,672 |
| B-TRACK | 900 |
| I-TRACK | 2,323 |
| B-ARTIST | 612 |
| I-ARTIST | 1,356 |
| B-ALBUM | 582 |
| I-ALBUM | 1,526 |
| **Total** | **18,971** |

| Slot | Spans | Mean tokens | Min–max | One-token rows | Multi-token rows | B/I ratio |
|---|---:|---:|---|---:|---:|---:|
| TRACK | 900 | 3.5811 | 1–7 | 8 | 892 | 0.38743 |
| ARTIST | 612 | 3.2157 | 1–5 | 12 | 600 | 0.45133 |
| ALBUM | 582 | 3.6220 | 1–7 | 41 | 541 | 0.38139 |

Span-length histograms, written as token length:count:

- TRACK: 1:8, 2:276, 3:190, 4:179, 5:118, 6:116, 7:13.
- ARTIST: 1:12, 2:82, 3:300, 4:198, 5:20.
- ALBUM: 1:41, 2:114, 3:124, 4:145, 5:73, 6:73, 7:12.

Starts are structurally less frequent than interiors, by approximately
2.58× for TRACK, 2.22× for ARTIST and 2.62× for ALBUM. This justifies making
start errors visible separately; it does not establish that imbalance alone
caused the learned failures, or that the proposed objective will fix them.

| Supported language | Rows | Play | Unknown | User tokens | O | B/I TRACK | B/I ARTIST | B/I ALBUM |
|---|---:|---:|---:|---:|---:|---|---|---|
| zh-Hant | 762 | 462 | 300 | 9,060 | 5,537 | 462/1,204 | 234/558 | 282/783 |
| zh-Hans | 240 | 144 | 96 | 2,668 | 1,666 | 144/325 | 84/204 | 84/161 |
| mixed | 498 | 294 | 204 | 7,243 | 4,469 | 294/794 | 294/594 | 216/582 |

The 20 template-family entries in JSON contain full counts and histograms:
six Hant play families with 77 rows each, six Hans play families with 24 each,
six mixed play families with 49 each, and artist-only/missing-track unknown
families with 300 each. This audit does not infer categories from utterance text.

## Manifest-only language coverage

The pinned corpus manifest already records all-row train coverage as Hant882,
Hans288, mixed630, en0; validation coverage is mixed408/en192/Hant0/Hans0.
These are quoted existing manifest facts, not new validation-derived statistics.
No validation file was opened. Keep the pure-English coverage mismatch visible;
these counts alone do not establish the cause of a learned generalization gap.

## Selected v2 mechanics and checks

- BIO family: existing seven-class token CE plus per-slot start-vs-rest BCE
  on the same logits, with positive/negative strata reduced separately.
  No target edits or new head parameters. Coefficients are unset.
- Validity: existing duplicate binary target and gate retained; replace CLS
  with user-state-only masked arithmetic-mean encoder representation. It
  remains diagnostic rather than an independent semantic truth signal.
- Typed: architecture unchanged; separately report gold-play→play,
  gold-unknown→unknown and gold-unknown→play. TRACK rejection cannot hide typed
  failure in the report. Any final supported-unknown false acceptance stops.
- S3 remains unchanged. Model/objective improvement cannot be attributed to
  decoder relaxation. Slot-presence extras, validity removal/redefinition and
  LoRA are excluded from the first proposal.

Focused tests: **34 passed** (1.83 s), using ordinary project Python with
`-B -X utf8`, `--noconftest`, and pytest cache disabled. Invented rectangular
CPU numeric tensors show the start-loss response, token-average dilution,
false-start penalty and empty-stratum handling. They also prove selected-only
pooling, equivalent-padding invariance, determinism and empty-mask rejection.
No synthetic test loads the real tokenizer or uses autograd/backward.
A floating-point shift-invariance check initially detected cancellation from
large common logit offsets; subtracting the per-token maximum before evaluating
the terms resolved it. This was a CPU math correction, not a model retry.

The pinned CPU tokenizer audit ran with qualified Python, `-B -X utf8`,
offline flags and USE_TORCH/USE_TF/USE_FLAX=0. The user explicitly permitted
A-section tokenizer-only analysis; B-section synthetic checks remain isolated.
The audit guard denies non-train corpus/fixtures, weights/checkpoints, writes,
network/subprocess and model-framework imports. Two independent complete audit
results were equal, including canonical SHA. Train/tokenizer/manifests/source
identities were checked unchanged before/after. Transformers' notice that model
frameworks are unavailable is expected under this tokenizer-only configuration.

Syntax checks passed for both new Python files without writing bytecode;
canonical/source hash and language/family sum checks passed; 35 Markdown
relative links passed; git diff --check passed. Protected app/artifacts/fixtures,
V1 runner, renderer and S3 have zero diff. Primary worktree hashes for its three
existing Shortcut/status edits remain unchanged. No broad model/GPU/test suite is needed for this
isolated no-model change. No old evidence, V1 runner, S3, app or frozen artifacts
changed. No issue comment/update is part of this task.

## Authority and next gate

All six persistent flags remain false: training_authorized,
model_compute_authorized, semantic_memory_enabled, local_ai_fallback_approved,
LOCAL_SEMANTIC_MEMORY_ENABLED and LOCAL_AI_FALLBACK_APPROVED.

No model/checkpoint load, GPU, inference, training, backward, optimizer step,
validation row input, held-out row access, Stage A row access or production
action occurred. Next gate is independent protocol/audit review. Any later
implementation/compute task must freeze the outstanding numeric configuration,
selection/checkpoint/evaluation rules and meaningful-improvement criteria.
No automatic full adaptation or retry follows. Leave this PR open and unmerged.
