# Stage B Laya head-only shape smoke — 2026-09-26

## Result and boundary

**`LAYA_RX9070XT_HEAD_ONLY_FORWARD_BACKWARD_SMOKE_PASSED`.** The fixed eight-row
research batch completed one pinned Laya `agent.model(...)` forward and one
provisional total-loss backward on the RX 9070 XT. The encoder stayed frozen
and had no gradients. No optimizer was created or stepped, and no checkpoint
was saved. This is shape/connectivity evidence, not model quality or training
authorization.

The task began from exact `origin/main` / isolated branch HEAD
`0f8bb0a2f5f9a9675ba525d0cdf1d2ff5e7532aa` on branch
`codex/stage-b-laya-head-shape-smoke`. The final PR head is recorded in PR
metadata after this evidence file is committed. The primary worktree's
pre-existing Shortcut edits were untouched.

## Synthetic fixture and offline gate

The dedicated [64-row fixture](../../../../tests/fixtures/local_ai_stage_b_laya_shape_smoke_v1.jsonl)
has SHA-256 `f632172af7a0ffce4c0a315d18bb353c30720ccf60581f7ada73f2fb892195a0`.
Its eight ordered slices each contain eight rows: zh-Hant track-only play,
English track-only play, mixed track+artist play, mixed track+artist+album
play, zh-Hant semantic unknown, English semantic unknown, mixed semantic
unknown, and zh-Hant missing-track semantic unknown. The utterances and
entities were invented for this fixture; no Stage A or Stage B corpus row,
user data, provider identifier, or live catalog data became a smoke input.
The runner itself does not load frozen rows into its adapter or model. The
mandated existing read-only seal verifier internally reads frozen Stage A/B
files to check their identities; none of those values enter the smoke batch.

All 64 rows passed ID/slice/schema/raw-span checks. Using the pinned local
tokenizer and the pinned upstream `laya.common.build_sequence`, the project
renderer matched all 64 input-ID sequences and marker-position sequences.
Required spans were not truncated (maximum sequence length 36). User-state
masks excluded CLS, prompt, options, MASK/SEP, and padding; every BIO slot
label stayed inside the mask, unknown rows contained only O labels, and
repeat rendering was byte-identical. Provisional BIO IDs are O=0,
B/I-TRACK=1/2, B/I-ARTIST=3/4, B/I-ALBUM=5/6. Deterministic postprocessing
sets every slot null for unknown and returns unknown/null when play lacks a
valid grounded track. No accuracy is claimed for the untrained heads.

The fixed live IDs were `smoke-001`, `smoke-009`, `smoke-017`, `smoke-025`,
`smoke-033`, `smoke-041`, `smoke-049`, and `smoke-057`. Head initialization
seed was 1729. The result did not influence row choice or loss weights.

## Same-child identity, load, and residency

| Gate | Observation |
| --- | --- |
| Python | `D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe`, process `-B -X utf8`, `utf8_mode=1` |
| Pinned source | `NandhaKishorM/laya@42626c348753fbb17572a813127df2278a1ec527`, clean before/after |
| Pinned model | `convaiinnovations/laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa`, canonical `D:\ai\ai\laya` |
| Primary weight SHA-256 | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Model 11-file aggregate before/after | `eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf` / same |
| Venv inventory before/after | `3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337` / same |
| Stage B seal before/after | `5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef` / same; 600 rows, 100 groups |
| Visible GPUs | `cuda:0` AMD Radeon(TM) Graphics / gfx1036; `cuda:1` AMD Radeon RX 9070 XT / gfx1201 |
| Selected/current GPU | Unique RX 9070 XT, explicit `cuda:1`; no iGPU or NVIDIA selection |
| Laya / parameters / buffers | All `cuda:1`; `cpu_fallback=false`; strict checkpoint load passed |
| Parameter / persistent temperature / state elements | 321,908,995 / 3 / 321,908,998 |
| Parameter / buffer dtype | `torch.float32` / `torch.float32` |
| Load time | 12.023 seconds |

## Single forward and backward readback

The batch input shape was `[8, 36]` and encoder hidden size 768. All listed
tensors were on `cuda:1` and finite.

| Tensor | Shape | Dtype |
| --- | --- | --- |
| Typed option logits | `[8, 2]` | `torch.float32` |
| Action logits | `[8, 2]` | `torch.bfloat16` |
| Captured encoder hidden states | `[8, 36, 768]` | `torch.float32` |
| Provisional span logits | `[8, 36, 7]` | `torch.float32` |
| Provisional validity logits | `[8]` | `torch.float32` |
| User-state mask | `[8, 36]` | `torch.bool` |

The single shape-only loss used unit weights: typed-intent CE `0.7124654055`,
masked BIO CE `3.0462541580`, validity BCE `0.9377940893`, total
`4.6965136528`. Values are descriptive and were not interpreted as quality.
After one `total.backward()`, finite nonzero gradient norms were typed
decision path `4.1947693331`, span head `25.4470554964`, validity head
`15.1331829162`. Encoder gradients were absent; gradient tensors were on
`cuda:1`. Gradients were cleared afterward. No act-head target or loss was
invented.

| RX 9070 XT VRAM phase | Allocated bytes | Reserved bytes |
| --- | ---: | ---: |
| Baseline before load | 0 | 0 |
| After load | 1,307,833,856 | 1,333,788,672 |
| Pre-forward | 1,307,870,208 | 1,333,788,672 |
| Post-forward | 1,390,087,680 | 1,400,897,536 |
| Post-backward | 1,435,402,752 | 1,497,366,528 |
| Peak | 1,452,687,872 | 1,497,366,528 |

## Remaining gates

The next proposed training-pipeline smoke is **separately unauthorized**.
No Stage B train/validation/held-out row or Stage A fixture was used as model
input; the verifier's integrity-only reads are disclosed above. No optimizer,
training/fine-tuning/LoRA, quality evaluation, calibration, Spotify, Siri,
Windows action, network model call, production app change, or Decider
qualification was performed. The current one-run research authorization does
not change persistent flags:

```text
training_authorized=false
model_compute_authorized=false
semantic_memory_enabled=false
local_ai_fallback_approved=false
LOCAL_SEMANTIC_MEMORY_ENABLED=false
LOCAL_AI_FALLBACK_APPROVED=false
```
