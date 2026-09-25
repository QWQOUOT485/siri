# Stage B Laya UTF-8 model-load preflight — 2026-09-25

## Result

**`LAYA_MODEL_LOAD_NEW_BLOCKER`: `parameter_count_mismatch`.** The sole live
attempt passed the prior cp950 boundary and returned from the pinned Laya
loader on the RX 9070 XT. The project-owned readback stopped when the actual
parameter count differed from the historical expectation of 321,908,998.
The child stopped before emitting the actual count, so this report does not
claim a value or accept the mismatch. No second load was attempted.

The live gate ran from branch `codex/stage-b-laya-utf8-model-load-preflight`
at starting main/checkout HEAD `6175bdebd3512b843638b9008f1ee9a4bc91bff2`.
The primary worktree's existing Shortcut edits were untouched.

## Compatibility mechanism

`scripts/local_ai_stage_b_laya_model_load_preflight.py` launches its own
qualified Python with `-B -X utf8 <script> --child`. The child requires
`sys.flags.utf8_mode == 1`. The parent captures stdout and stderr as bytes,
then decodes only the structured result as UTF-8. The child sets process-local
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, passes the existing local model
directory to Laya, and performs no network download.

The prior `OTHER_DEPENDENCY_CP950` failure arose from a PyTorch Jinja template
opened with the Windows cp950 default. This attempt reported UTF-8 mode 1,
preferred/default/stdout/stderr encoding UTF-8, and did not hit that exception.
No PyTorch, Transformers, pinned Laya source, Windows locale, or model file was
modified.

## Live identities and readback

| Evidence | Observation |
| --- | --- |
| Python | `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe`, 3.14.7 |
| Stack | pip 26.2.1; torch 2.13.0+rocm10.0.0; HIP 7.15.26333; transformers 4.57.6; safetensors 0.7.0; huggingface_hub 0.36.2; numpy 2.3.5 |
| Visible devices | `cuda:0` AMD Radeon(TM) Graphics, `gfx1036`, 13,064,830,976 bytes; `cuda:1` AMD Radeon RX 9070 XT, `gfx1201`, 17,095,983,104 bytes |
| Selected load device | Explicit `cuda:1`, after unique name/architecture selection |
| Pinned source | `D:\ai\siri-spec\runtime\ai_poc\upstream-batch-2b\laya` at `42626c348753fbb17572a813127df2278a1ec527`; clean before/after |
| Pinned model | `D:\ai\ai\laya`; metadata revision `052592a15d198d9ad47da779604259b10b47b7aa` |
| Primary weight SHA-256 | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Canonical inventory | 11 files; aggregate SHA-256 before/after `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf`; byte-identical |
| Tokenizer compatibility | Pinned `_fix_tokenizer_config()` would be a no-op on the canonical config |
| Venv inventory SHA-256 | Before/after `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337`; unchanged |
| Load duration | 14.185 seconds, descriptive only |
| RX 9070 XT memory | Baseline allocated/reserved 0/0 bytes; after-load allocated 1,307,833,856, reserved 1,333,788,672 bytes; peak allocated/reserved equal those after-load values |
| Frozen Stage B seal | Read-only verification: 600 rows, 100 groups, manifest `5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef` |

The pinned loader returned, which means its source-level strict
`load_state_dict(..., strict=True)` completed. In the project-owned readback,
the Laya-reported device and every parameter/buffer device check preceded the
parameter-count check and did not raise. Because the count check raised before
the function returned, the structured result did **not** emit the device sets,
actual count, trainable count, dtype sets, or `cpu_fallback=false`. These are
not recorded as a completed residency qualification.

## Validation and remaining boundary

- Focused UTF-8 preflight tests: 6 passed.
- Existing RX 9070 XT hardware and held-out seal tests: 29 passed.
- Full unit suite: 632 passed, two existing deprecation warnings.
- Windows integration suite: 5 passed.
- `python -m compileall -q app scripts tests`: passed.
- Staged `git diff --check`: passed; changed Markdown relative links resolved.
- No Stage A or Stage B row was sent to Laya; no forward, inference, backward,
  optimizer, training, LoRA, calibration, or held-out evaluation occurred.
- Frozen source, review, split, and sealed artifacts were not modified.

The next gate requires independent review of the parameter-count discrepancy
and an explicitly authorized way to capture its exact value. This task does
not relax the expected count or retry the model load. Forward/backward,
adapter smoke, training pipeline, validation and held-out quality, latency,
Decider qualification, and production fallback remain unproven.

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
