# Stage B Laya training-pipeline smoke — 2026-09-26

## Result

**`STOP_LAYA_TRAINING_PIPELINE_DATA_BOUNDARY`**:
`fixed_strata_incomplete_or_duplicate`. The exact frozen 1,800-row train
split contains **zero** supported unknown rows labeled
`negative_reason=unresolved_reference` and **zero** labeled
`negative_reason=ambiguous_version`. The task requires four of each.
The prescribed 40-row source subset cannot be constructed.

This is a read-only data preflight result. **No live child invocation, model
load, rendering, forward/backward, Laya optimizer step, or checkpoint occurred.**
The one live GPU invocation was not attempted. No substitute rows or strata
were selected. No partial subset is presented as the required manifest.

Base `origin/main` was fetched and verified as
`57a07b11f8ae322d39be9379f7423b924880aa0b`. Work uses isolated branch
`codex/stage-b-laya-training-pipeline-smoke`; the final head is in the PR
metadata. The primary worktree's existing status and Shortcut edits were
preserved.

## Authorization and implementation boundary

The task authorized one bounded RX 9070 XT smoke with exactly four AdamW
steps, including step-2 checkpoint save/reload/resume and cleanup, only after
the fixed train identity, schema, corpus/seal, and subset gates pass. It did
not authorize changing the frozen data or substituting another selection
rule. The data gate failed before model access.

The [project-owned preflight](../../../../scripts/local_ai_stage_b_laya_training_pipeline_smoke.py)
reuses the authoritative corpus and held-out-seal verifier. The retained
implementation has no PyTorch, Laya, tokenizer, subprocess, or training
dependency. An initial unexercised training draft was removed when this
blocker was established; it is not part of the PR. The
[unit tests](../../../../tests/unit/test_local_ai_stage_b_laya_training_pipeline_smoke.py)
exercise the selector on explicitly synthetic records and prove that the
actual frozen train file fails closed. Synthetic records never enter a model.

MiniMind remains only the
[training-engineering reference](../../training/LOCAL_AI_MINIMIND_TRAINING_REFERENCE.md)
for future seeding, mixed precision, optimizer/scheduler, clipping,
checkpoint, and logging work. No MiniMind runtime or causal-LM objective was
introduced.

## Exact source and selection rule

Only `artifacts/local_ai/stage_b/final_v1/train.jsonl` supplies selectable
rows. Its byte SHA-256 and 1,800-row count pass before subset selection:

`54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2`

Algorithm `canonical-file-first-four-per-stratum-v1` scans the canonical
file order once, retains the first four matching rows for each fixed stratum,
and preserves their file order. Successful selection requires exactly 40
distinct case IDs, 32 supported IDs, eight blocked IDs, and four consecutive
eight-ID eligible batches. It returns no manifest on an incomplete stratum.

The closed schema is `StageBRecord`. Play requires
`ai_scope=supported`, `expected.intent=spotify_play_track`, a valid track
span, and the exact `optional_slot_status.artist/album` values below.
Unknown requires `ai_scope=supported`, `expected.intent=unknown`, all
slots null, and the exact `negative_reason` value below. No text-based
reinterpretation or relabeling occurs.

| Requested stratum | Available train rows | Required |
| --- | ---: | ---: |
| play: artist present, album present | 408 | 4 |
| play: artist present, album absent | 204 | 4 |
| play: artist absent, album present | 174 | 4 |
| play: artist absent, album absent | 114 | 4 |
| supported unknown: missing_track | 300 | 4 |
| supported unknown: artist_only | 300 | 4 |
| supported unknown: unresolved_reference | **0** | **4** |
| supported unknown: ambiguous_version | **0** | **4** |
| ai_scope=deterministic_only | 180 | 4 |
| ai_scope=safety_only | 120 | 4 |

These counts sum to 1,800. The 40 selected case IDs/source-group IDs, subset
manifest SHA, 32 eligible IDs, eight blocked IDs, and four batch memberships
are **unavailable because selection failed**. The synthetic unit test proves
the intended 40/32/8 and 4×8 partitions when all ten strata exist; that is
source evidence only.

## Corpus and seal checks

`verify_seal()` runs the existing authoritative `validate_protocol_corpus`
and frozen-source checks: closed schema, exact split identities/counts,
whole source-group assignment, reviewed v6 provenance, Stage A leakage,
and the frozen exact near-duplicate policy. It also verifies the read-only
600-row/100-group seal and persistent source/seal authority flags.

The verifier internally reads final train/validation/held-out files, the
sealed held-out bytes, Stage A fixture, and reviewed v6 source/review
artifacts **solely for integrity**. Those other files supply no selectable
rows, rendering inputs, optimizer batches, or quality measurements.

All corpus/split/selection/provenance/seal identities in the structured record
below passed unchanged before/after this read-only preflight. The canonical
corpus SHA is `a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13`.
The byte split hashes differ intentionally from canonical-record split hashes.

## Compute fields not reached

PR #75's reviewed head-only shape smoke remains valid prior evidence.
This task made no new renderer-equivalence, strict-load/residency, GPU, dtype,
VRAM, gradient, parameter-freeze/mutation, loss, LR, or checkpoint claim.

The prescribed values remain unexecuted task configuration: seed 1729;
encoder and act_head frozen; allowed typed decision `type_emb`, optional
non-encoder `head`, and `scorer`, plus project span and validity heads;
AdamW LR 1e-4, weight decay 0, betas (0.9, 0.999), eps 1e-8;
four fixed batch-8 steps; LR factors 1, 0.75, 0.50, 0.25;
gradient clip max norm 1.0; unit-weight intent CE + masked BIO CE +
validity BCE; qualified AMD Radeon RX 9070 XT / gfx1201.

No checkpoint/task directory was created, so checkpoint path, SHA, reload,
resume, cleanup, and parameter hashes are not applicable. No new model
artifact was written under canonical `D:\ai\ai\laya`.

The task supplied these qualified identities; they were **not requalified
by a live child** because the data boundary stopped first:

| Identity | Task-supplied value |
| --- | --- |
| Qualified Python | `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe` |
| Laya source revision | `42626c348753fbb17572a813127df2278a1ec527` |
| Model revision | `052592a15d198d9ad47da779604259b10b47b7aa` |
| Primary weight SHA | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Model aggregate SHA | `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` |
| Venv inventory SHA | `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337` |

## Sanitized structured result

Reproduce the data preflight with the ordinary project test Python:

```powershell
& D:/ai/siri-spec/.venv/Scripts/python.exe -B -X utf8 scripts/local_ai_stage_b_laya_training_pipeline_smoke.py
```

Exit code 1 is the expected fail-closed result. This command contains no model
compute. Canonical SHA-256 uses UTF-8 JSON with sorted keys, ASCII escaping,
compact separators, and nonfinite JSON values rejected; the hash excludes
only the `canonical_report_sha256` field itself. It is a **data-preflight
report hash**, not a successful training-run-summary hash.

```json
{
  "authority_flags": {
    "LOCAL_AI_FALLBACK_APPROVED": false,
    "LOCAL_SEMANTIC_MEMORY_ENABLED": false,
    "local_ai_fallback_approved": false,
    "model_compute_authorized": false,
    "semantic_memory_enabled": false,
    "training_authorized": false
  },
  "available_per_stratum": {
    "deterministic_only": 180,
    "play_artist_absent_album_absent": 114,
    "play_artist_absent_album_present": 174,
    "play_artist_present_album_absent": 204,
    "play_artist_present_album_present": 408,
    "safety_only": 120,
    "unknown_ambiguous_version": 0,
    "unknown_artist_only": 300,
    "unknown_missing_track": 300,
    "unknown_unresolved_reference": 0
  },
  "blocker": "fixed_strata_incomplete_or_duplicate",
  "canonical_report_sha256": "8c489efb27475c90aec4fce9f1d5ad18cf1e5557505bf4ab4ee5968792357eda",
  "checkpoint_created": false,
  "data_identity_after": {
    "authoritative_schema_groups_leakage_near_duplicates": "passed",
    "canonical_corpus_sha256": "a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13",
    "canonical_split_sha256": {
      "test": "6c9d960bd299c3c4cc07aa5f341b775d408d2b2f4191954512f588519d683594",
      "train": "c3793a6b8e4bb5068f5bd1d027c1b967be5fd18b88992db2b363270a4a832964",
      "validation": "9f3028c83e0c3f7e5402c239abe9f194a3e06309b43f3cd9344fb3475fdf21cd"
    },
    "corpus_manifest_sha256": "297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c",
    "provenance_manifest_sha256": "d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d",
    "seal_manifest_sha256": "5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef",
    "selection_manifest_sha256": "973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a",
    "split_assignment_sha256": "84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37",
    "split_file_sha256": {
      "held_out.jsonl": "de392544b7a294cdf850ce2706509684b05c4ca346402c7ec60cf9031f979946",
      "train.jsonl": "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2",
      "validation.jsonl": "297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a"
    },
    "train_rows": 1800,
    "train_sha256": "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"
  },
  "data_identity_before": {
    "authoritative_schema_groups_leakage_near_duplicates": "passed",
    "canonical_corpus_sha256": "a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13",
    "canonical_split_sha256": {
      "test": "6c9d960bd299c3c4cc07aa5f341b775d408d2b2f4191954512f588519d683594",
      "train": "c3793a6b8e4bb5068f5bd1d027c1b967be5fd18b88992db2b363270a4a832964",
      "validation": "9f3028c83e0c3f7e5402c239abe9f194a3e06309b43f3cd9344fb3475fdf21cd"
    },
    "corpus_manifest_sha256": "297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c",
    "provenance_manifest_sha256": "d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d",
    "seal_manifest_sha256": "5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef",
    "selection_manifest_sha256": "973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a",
    "split_assignment_sha256": "84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37",
    "split_file_sha256": {
      "held_out.jsonl": "de392544b7a294cdf850ce2706509684b05c4ca346402c7ec60cf9031f979946",
      "train.jsonl": "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2",
      "validation.jsonl": "297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a"
    },
    "train_rows": 1800,
    "train_sha256": "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"
  },
  "deficient_strata": {
    "unknown_ambiguous_version": 0,
    "unknown_unresolved_reference": 0
  },
  "live_invocations": 0,
  "model_loads": 0,
  "optimizer_steps": 0,
  "repo_base": "57a07b11f8ae322d39be9379f7423b924880aa0b",
  "required_per_stratum": {
    "deterministic_only": 4,
    "play_artist_absent_album_absent": 4,
    "play_artist_absent_album_present": 4,
    "play_artist_present_album_absent": 4,
    "play_artist_present_album_present": 4,
    "safety_only": 4,
    "unknown_ambiguous_version": 4,
    "unknown_artist_only": 4,
    "unknown_missing_track": 4,
    "unknown_unresolved_reference": 4
  },
  "schema": "laya-training-pipeline-data-preflight-v1",
  "status": "STOP_LAYA_TRAINING_PIPELINE_DATA_BOUNDARY"
}
```

## Validation

- Focused new preflight tests: 17 passed.
- Focused preflight/shape/load/hardware/corpus/seal regression: 101 passed.
- Full unit suite: 663 passed, two existing deprecation warnings (288.72 s).
- Windows integration: 5 passed.
- `python -m compileall -q app scripts tests`: passed.
- `git diff --check`: passed; 27 Markdown relative links resolved.
- Frozen `artifacts/`, `tests/fixtures/`, and production `app/`: zero diff.
- Primary `PROJECT_STATUS.md`, `docs/SIRI_SHORTCUT.md`, and
  `docs/SIRI_SHORTCUT_V2.md` SHA-256 values match their starting identities.
- No quality benchmarks were run.

The initial draft's test run exposed the absent strata (four fixture setup
errors) and an unused wrong hardware test import (one failure). That draft
also ran one four-step AdamW CPU unit test on a tiny randomly initialized
toy module and invented tensors, with no Laya weights or corpus examples.
Those four toy unit steps are not a Laya training-pipeline result. No GPU
or Laya model was used. The draft training code/tests were removed; the
retained narrow suite passes and performs no optimizer operations. There
was no live Laya attempt or retry. The structured report's zero optimizer
count describes the retained data-preflight invocation.

## Status and remaining gates

`PROJECT_STATUS.md` records this exact dataset blocker. Issue #68 remains
OPEN. The PR remains OPEN and UNMERGED for independent review.

The smallest next action is a separately approved revision to the
predeclared subset rule using strata actually present in the frozen train
file, or a separately reviewed future corpus revision. This task does
neither. The training-pipeline smoke remains unproven; small adaptation is
still separately unauthorized. Validation/held-out quality, Stage A model
regression, latency, Decider qualification, and production promotion remain
separate gates.

No validation/held-out/Stage A/synthetic-fixture Laya input, Laya optimizer step,
model retry, quality evaluation, threshold/hyperparameter tuning, encoder or
act-head training, LoRA, distillation, RL, Spotify/Siri/Windows action,
production app change, frozen artifact change, or network model call occurred.
All six persistent authority flags remain false:

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
