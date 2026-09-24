# Stage B RX 9070 XT basic tensor preflight — 2026-09-24

## Result and boundary

**RX9070XT_TENSOR_SMOKE_PASSED.** This proves one small synthetic FP32 tensor
operation executed on the selected RX 9070 XT through the installed Windows
ROCm/PyTorch stack. It removes only the basic accelerator/tensor execution
blocker. It is not full Stage B hardware, model, candidate, latency, or quality
qualification.

The probe loaded no model, ran no inference, backward pass, optimizer, training,
or benchmark, and did not use Stage A or Stage B rows. The existing held-out
seal was verified through its read-only integrity command; no held-out labels
were used for diagnosis or tuning.

## Facts read and executed on this Windows machine

- Starting `origin/main`: `df4631e17b26f60170410d1cb63d15c86a22aea2`.
- Branch: `codex/stage-b-rx9070xt-hardware-preflight` in a clean sibling
  worktree. The primary worktree's Shortcut edits were not changed.
- Python: `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe`.
- The existing read-only environment preflight again identified the target:
  Windows driver `32.0.31041.1004`, Vulkan driver info `26.8.1 (LLPC)`,
  OpenCL target VRAM `17,095,983,104` bytes. Its benchmark execution and
  model-weight access fields were both `not_attempted`.
- PyTorch: `2.13.0+rocm10.0.0`; `torch.version.hip=7.15.26333`;
  `torch.version.cuda=None`. PyTorch uses its `cuda` API for this ROCm build;
  the API name does not identify an NVIDIA device.
- `torch.cuda.is_available()` returned `True`; device count was 2.

| Index | PyTorch name | Architecture | PyTorch type | Total memory bytes | Decision |
| --- | --- | --- | --- | ---: | --- |
| 0 | AMD Radeon(TM) Graphics | `gfx1036` | `cuda` | 13,064,830,976 | Rejected: integrated GPU, wrong name and architecture |
| 1 | AMD Radeon RX 9070 XT | `gfx1201` | `cuda` | 17,095,983,104 | Uniquely selected target |

No RTX 3060 or other NVIDIA device was selected or used. The script enumerates
all visible devices and requires exactly one matching name and `gfx1201` when
the architecture is exposed. It does not assume index 0 or index 1.

The selected device was `cuda:1`. The probe created a 4×4 FP32 `arange` matrix
and a 4×4 FP32 identity matrix directly on that device, multiplied them once,
synchronized `cuda:1`, and read back the 16 values:

```text
[[ 0,  1,  2,  3],
 [ 4,  5,  6,  7],
 [ 8,  9, 10, 11],
 [12, 13, 14, 15]]
```

All values were finite and matched the expected matrix; checksum was `120.0`.
All three GPU-side tensors (`a`, `b`, `c`) reported `cuda:1`. The host copy was
used solely for the tiny readback. `cpu_fallback=false`. PyTorch reported peak
allocated memory `33,555,968` bytes and peak reserved memory `35,651,584`
bytes. The final-script run took about `1.682` seconds, descriptive only and not a
latency benchmark.

The existing `scripts/local_ai_stage_b_held_out_seal.py --verify` completed
without writes: 600 sealed rows, 100 groups, seal manifest SHA-256
`5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef`.
The hardware script also calls that same read-only verifier before importing
torch and refuses to report PASS if the frozen seal or authority flags drift.
Frozen Stage B corpus, review, assignment, and seal artifacts were not modified.
The current seal records `final_split_assigned=true` and `held_out_sealed=true`.
The frozen pre-seal manifests retain their historical `held_out_sealed=false`.

## Source and mock evidence

The new hardware probe uses a closed report schema and keeps target selection
separate from the synthetic tensor operation. Offline tests cover target index
0 or 1; rejection of CPU-only, iGPU-only, NVIDIA-only, wrong-name,
wrong-architecture, and ambiguous target inventories; and report rejection of
CPU fallback, wrong tensor placement, or invalid readback. These mocked tests
do not substitute for the live result above.

- Focused hardware tests: 14 passed.
- Hardware, existing benchmark/preflight, Stage B protocol, final-selection,
  and seal tests together: 95 passed.
- Full unit suite: 626 passed; two existing dependency deprecation warnings.
- `python -m compileall -q app scripts tests`: passed.
- `git diff --check`: passed.

## Authority and unproven work

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
```

Still unproven: laya and decider load/device readback; model forward/backward;
adapter smoke; training-pipeline smoke; Stage B candidate qualification;
held-out quality; latency acceptance; training and model-compute authorization;
and production fallback approval. Each remains a separate gate.
