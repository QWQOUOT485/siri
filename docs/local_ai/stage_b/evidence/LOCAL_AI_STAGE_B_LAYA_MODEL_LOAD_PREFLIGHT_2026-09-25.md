# Stage B Laya UTF-8 model-load preflight — 2026-09-25

## Current result — 2026-09-26

**`LAYA_RX9070XT_MODEL_LOAD_READBACK_PASSED`.** The one additional authorized
`-B -X utf8` load used the exact pinned local source, model, and qualified
venv. The child reported UTF-8 mode 1 and selected the unique RX 9070 XT /
`gfx1201` at `cuda:1`. Laya, all parameters, and all buffers reported
`cuda:1`; `cpu_fallback=false`. Strict checkpoint load succeeded.

| Readback | Observation |
| --- | --- |
| Parameter elements / trainable elements | 321,908,995 / 321,908,995 |
| Persistent buffer | `temperature`, 3 elements, `torch.float32` |
| Checkpoint/state elements | 321,908,998; state keys matched parameters plus persistent buffer |
| Parameter / buffer dtypes | `torch.float32` / `torch.float32` |
| Load duration | 16.048 seconds |
| Baseline allocated / reserved | 0 / 0 bytes |
| After-load allocated / reserved | 1,307,833,856 / 1,333,788,672 bytes |
| Peak allocated / reserved | 1,307,833,856 / 1,333,788,672 bytes |
| Model aggregate SHA before / after | `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` / same |
| Venv inventory SHA before / after | `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337` / same |
| Source | `42626c348753fbb17572a813127df2278a1ec527`, clean |
| Frozen seal | `5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef`, 600 rows / 100 groups |

No forward, inference, backward, optimizer, training, LoRA, calibration, or
held-out evaluation ran. This qualifies construction/load and device residency
readback only. All authority flags remain false.

## Historical first attempt

**`LAYA_MODEL_LOAD_NEW_BLOCKER`: `parameter_count_mismatch`.** The sole live
attempt passed the prior cp950 boundary and returned from the pinned Laya
loader on the RX 9070 XT. The project-owned readback stopped when the actual
parameter count differed from the historical expectation of 321,908,998.
The child stopped before emitting the actual count, so this report does not
claim a value or accept the mismatch. No second load was attempted.

## 2026-09-26 correction, before second live attempt

The old `321,908,998` expectation conflated `named_parameters()` with all
checkpoint state elements. A metadata-only `safetensors.safe_open` inspection
of the exact pinned `model.safetensors` recorded every tensor key, shape,
dtype, and element count in
[the header inventory](LAYA_CHECKPOINT_HEADER_INVENTORY_2026-09-26.json)
(SHA-256 `fc30dfebfbe91f045c46c2e5fe27996c0ef116caf7ca98e0cd374cd4b42accfe`).
It found 170 tensor keys and 321,908,998 elements. The only `temperature`
key is shape `[3]`, dtype `F32`, 3 elements. Excluding it leaves
321,908,995 elements. No tensor payload was materialized. The other keys
belong to the `encoder`, `head`, `type_emb`, `scorer`, and `act_head` modules
in pinned `laya/common.py`; the earlier strict state-dict load succeeded.
The pinned `DecisionModel` uses `self.register_buffer("temperature", torch.ones(3))`
at line 102, so temperature is persistent state rather than a parameter.

The corrected gate separately checks 321,908,995 parameter elements, 3
persistent temperature buffer elements, and 321,908,998 state elements. The
first attempt's actual parameter count remains unknown because it was not
serialized. No final residency PASS is inferred from the first attempt.

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

Those validation figures describe the first attempt and are retained as
historical evidence. The 2026-09-26 correction above supersedes its blocker.
Forward/backward, adapter smoke, training pipeline, validation and held-out
quality, latency, Decider qualification, and production fallback remain
unproven and unauthorized.

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
